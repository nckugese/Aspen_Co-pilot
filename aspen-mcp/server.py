"""Aspen Plus MCP Server — entry point.

Every tool is registered through @tool() (tools/intercept.py): one async wrapper per tool and
a row in its classification table, checked by intercept.verify() at startup.
No dynamic activation/deactivation — every tool is always available.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import logging.handlers
import os

from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Per-user state directory. Everything this server writes goes here rather than next to
# the code: once installed, the package directory lives inside the wheel and is replaced
# wholesale on upgrade, and may not even be writable.
# ---------------------------------------------------------------------------
_USER_DATA = os.path.join(os.path.expanduser("~"), ".aspen-mcp")

# ---------------------------------------------------------------------------
# Logging setup — writes to <user data>/aspen_mcp.log, rotated at 5 MB (3 old files kept).
# Only logs from our own modules (aspen_manager, tools) go to file.
# MCP framework noise is suppressed. Level INFO; ASPEN_MCP_LOG_LEVEL (e.g. DEBUG) overrides it.
#
# Failure here must never be fatal: this runs at import time, so an unwritable home
# directory would otherwise stop the server from starting at all. Losing the log is an
# acceptable outcome; losing the server is not.
# ---------------------------------------------------------------------------
_LOG_FILE = os.path.join(_USER_DATA, "aspen_mcp.log")
_LOG_LEVEL = getattr(logging, os.environ.get("ASPEN_MCP_LOG_LEVEL", "INFO").strip().upper(), None)
if not isinstance(_LOG_LEVEL, int):
    _LOG_LEVEL = logging.INFO

try:
    os.makedirs(_USER_DATA, exist_ok=True)
    _file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
except OSError:
    _file_handler = None
else:
    _file_handler.setLevel(_LOG_LEVEL)
    _file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )

for _logger_name in ("aspen_manager", "tools"):
    _logger = logging.getLogger(_logger_name)
    _logger.setLevel(_LOG_LEVEL)
    if _file_handler is not None:
        _logger.addHandler(_file_handler)

from aspen_manager import AspenPlusManager
from tools import main_tools, flowsheet_tools, value_tools, knowledge_tools, intercept, runlog, external
from tools import brake, brake_effects, learn, codex_bridge, handoff
from tools.properties_tools import (
    get_property_method as _get_prop, set_property_method as _set_prop,
    add_component as _add_comp, remove_component as _rm_comp,
    add_side_duty as _add_side_duty, remove_side_duty as _rm_side_duty,
)
from tools.reaction_tools import (
    add_reaction_set as _add_rxn_set,
    remove_reaction_set as _rm_rxn_set,
    add_reaction as _add_rxn,
    remove_reaction as _rm_rxn,
)
from tools.chemistry_tools import create_chemistry as _create_chemistry
from tools.optimize_dispatch import run_optimize as _run_optimize
from tools import workbench_tools as _wb
from tools.error_record import record_error as _record_error
from tools.pinch_tools import pinch_analysis as _pinch_analysis, pinch_matches as _pinch_matches
from searcher.discover_ports import discover_ports as _discover_ports

# ------------------------------------------------------------------
# Core objects
# ------------------------------------------------------------------

# Docs ship with this package; user-learned knowledge is written outside it, because an
# upgrade replaces the installed directory wholesale. Both roots are announced to the
# client below so agents never have to guess a path relative to the working directory.
_DOCS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

# Kept under ~1000 characters (Claude Code cuts instructions at 4096, a Codex agent plugin at
# 1000 bytes) and one rule per line, never hard-wrapped: Codex may show only the first line.
# Anything one tool or one workflow needs lives in that tool's results or in a skill instead.
_INSTRUCTIONS = f"""\
Drives the user's own licensed Aspen Plus on Windows through its COM API.
ASPEN_DOCS_ROOT: {_DOCS_ROOT}
ASPEN_USER_DATA: {_USER_DATA}
Read knowledge from both; write it only under ASPEN_USER_DATA (the docs are replaced on upgrade).

Before building or changing a process, follow the aspen-process-workflow skill.
1. Never guess Aspen paths or parameters: look them up from aspen.md via the aspen-doc subagent (or your own doc agent), passing it both roots. Without one, read only the section you need.
2. Tools that change a model take `reason`: one sentence on why, in the user's language. In learning mode it must explain the process principle.
3. [workbench] lines (or "workbench_brief") in a result are changes the user or a program made since your last call: account for them.
4. "Not applied" means nothing changed: do not retry; do what it says.
"""

@contextlib.asynccontextmanager
async def _lifespan(_app):
    """At start: a workbench window left open by the previous server process (a /mcp
    reconnect) is served again at once, not only after the AI's first tool call."""
    task = None
    try:
        task = asyncio.get_running_loop().create_task(_wb.reconnect(manager))
    except Exception:
        logging.getLogger("tools.workbench_tools").warning("workbench: no reconnect", exc_info=True)
    try:
        yield {}
    finally:
        if task is not None:
            task.cancel()


mcp = FastMCP(name="aspen-plus", instructions=_INSTRUCTIONS, lifespan=_lifespan)

# Claude Code channels (research preview). Started with
#   ASPEN_MCP_CHANNELS=1 claude --dangerously-load-development-channels server:<this server's name>
# the client takes messages this server pushes, so an Ask AI request sent from the
# workbench reaches the running session at once. Other clients ignore both the
# capability and the notification.
_base_init_options = mcp._mcp_server.create_initialization_options


def _init_options(notification_options=None, experimental_capabilities=None):
    return _base_init_options(notification_options, {**(experimental_capabilities or {}), "claude/channel": {}})


mcp._mcp_server.create_initialization_options = _init_options
_client = {"session": None}          # the MCP session to push to, known from any tool call


def _hold(ctx: Context | None) -> None:
    if ctx is None:
        return
    try:
        session = ctx.session
    except Exception:                # outside a request (a direct call): no client to know
        return
    _client["session"] = session
    try:                             # how long a call may be held depends on the client
        _wb.note_client(session.client_params.clientInfo.name)
    except Exception:
        pass


class _ChannelMessage(BaseModel):
    """notifications/claude/channel; the SDK's own Notification type drops its params."""
    method: str = "notifications/claude/channel"
    params: dict


async def _push(content: str, meta: dict) -> bool:
    """False: no client session known yet (a fresh server process); the workbench keeps the
    request and pushes it after the next tool call, which makes the session known."""
    if _client["session"] is None:
        return False
    try:                                     # Codex drops the message: not delivered, and the
        name = _client["session"].client_params.clientInfo.name or ""   # plugin's Stop /
    except Exception:                        # UserPromptSubmit hooks hand it over instead
        name = ""
    if "codex" in name.lower():
        return False
    await _client["session"].send_notification(_ChannelMessage(params={"content": content, "meta": meta}))
    return True


async def _push_codex(content: str, meta: dict) -> bool:
    """Codex run through its app-server (tools/codex_bridge.py): the request goes into the
    conversation as the user's own message, so it names the note to answer."""
    return await codex_bridge.push(
        f"{content}\n(note_id {meta['note_id']}: answer in the workbench with "
        f"workbench_edit(note_replies=[{{\"id\": \"{meta['note_id']}\", \"reply\": ...}}]))")


_wb.channel = _push
# The window promises "the AI gets it at once" only when the user says channels are on:
# the launch recipe in docs/mcp/workbench/requests.md sets ASPEN_MCP_CHANNELS=1 beside the channels flag.
_wb.listening = os.environ.get("ASPEN_MCP_CHANNELS", "").strip().lower() in ("1", "true", "yes", "on")
if codex_bridge.url():                   # Codex started by plugin/scripts/codex-workbench.ps1
    _wb.channel, _wb.listening, _wb.listening_checked = _push_codex, True, True
manager = AspenPlusManager()

# Every tool below goes through one async wrapper (tools/intercept.py): classified, annotated,
# `reason` on the changing ones, recorded in the change journal. `lambda: manager`: the
# current global, read at call time so it can be swapped.
hooks = intercept.Hooks(hold=_hold, session_of=_wb.session_of, note_state=_wb.current_note,
                        after=lambda session, refresh: _wb.after_tool(manager, session, refresh),
                        types=_wb.block_types, external=external.pre_call,
                        gate=_wb.gate, gate_done=_wb.gate_done, late=_wb.late_apply, effects=brake_effects.hook,
                        refuse=_wb.refuse_call,
                        before=lambda: handoff.before(_wb, manager))
# The review controls: the workspace's (tools/brake.py) -- Observe, pause, confirmation cards --
# asked before each changing AI call, only while this server owns the live window; what a card
# says (tools/brake_effects.py: the window's flowsheet, a workbench_run's tab); a watch over
# the AI's own records (tools/stuck.py, journal.listen) pauses it when it looks stuck.
brake_effects.configure(manager=lambda: manager, flowsheet=_wb.flowsheet_of)
_wb.wire_brakes(lambda: manager)
tool = intercept.make(mcp, lambda: manager, hooks)
# A run record says what changed since the last run and which results moved; the result
# fingerprint reads each block type's docs result rows, product streams from the window.
runlog.configure(outputs=_wb.key_outputs(), topology=_wb.flowsheet_of)
# What the journal records is what the server knows of each model; the foreground watch
# (no COM) says when Aspen's own window may have changed it (tools/external.py). Compared
# before every AI call (hooks.external), before the window's jobs and on its sync loop; a
# session's first compare starts from each block type's docs inputs (watch_paths).
external.configure(paths_of=_wb.watch_paths)

# ==================================================================
# Main tools (6)
# ==================================================================

@tool()
def open_aspen_plus(file_path: str, visible: bool = True, mode: str = None, ctx: Context = None) -> str:
    """Open Aspen Plus and load a .bkp simulation file; the workbench opens on it too.

    Set ``visible=False`` to hide the Aspen GUI — ~5-15% faster and uses
    less memory, recommended for long optimization runs.
    mode: how the user chose to work on it, asked before opening (aspen-process-workflow
    skill) -- "workbench" (the window; recommended) or "chat" (this conversation, no window).
    Omitted: the mode recorded for the session, if any.
    """
    _hold(ctx)
    before = manager.session_names()
    res = main_tools.open_aspen_plus(manager, file_path, visible=visible)
    return res + _wb.auto_open(manager, before, manager._session_name(file_path), mode=mode)


@tool()
def set_reopen_interval(interval: int | None = None) -> str:
    """Auto-reopen the Aspen .bkp every N optimization evaluations.

    Aspen accumulates internal state (history files, solver cache, fortran
    scratch) that slows it down over long runs. Reopening resets that state
    at the cost of ~3-5 s per reopen.

    A reopen ends only the Aspen process this server started for the session;
    other Aspen instances (the user's, parallel runs) are left alone.

    Args:
        interval: Number of evaluations between reopens. Pass ``None`` or 0
            to disable. Typical values: 100-200 for heavy optimizations.
    """
    return manager.set_reopen_interval(interval)


@tool()
def create_new_simulation(project_name: str, destination_folder: str = None, mode: str = None,
                                ctx: Context = None) -> str:
    """Create a new Aspen Plus simulation from the blank template.

    Copies Blank_Simulation.bkp to <destination_folder>/<project_name>.bkp and opens it
    (the workbench opens on it too, unless mode is "chat").
    Use this when starting a brand new project instead of opening an existing file.
    If destination_folder is omitted, the file is created in the current working
    directory.
    mode: how the user chose to work, asked before creating it (aspen-process-workflow
    skill) -- "workbench" (the window; recommended) or "chat" (this conversation, no window).
    """
    _hold(ctx)
    before = manager.session_names()
    res = main_tools.create_new_simulation(manager, project_name, destination_folder)
    return res + _wb.auto_open(manager, before, mode=mode)


@tool()
def close_aspen_plus(session_name: str = None) -> str:
    """Close an Aspen Plus session"""
    return main_tools.close_aspen_plus(manager, session_name)


@tool()
def list_aspen_sessions() -> str:
    """List all active Aspen Plus sessions"""
    return main_tools.list_aspen_sessions(manager)


@tool()
def reinit_simulation(session_name: str) -> str:
    """Reinitialize the whole simulation (all blocks + convergence) to its initial state.

    Use after a failed run leaves stale results, or before a clean re-run.
    """
    return main_tools.reinit_simulation(manager, session_name)


@tool()
def run_simulation(session_name: str) -> str:
    """Run the simulation in a given session"""
    return main_tools.run_simulation(manager, session_name)


@tool()
def get_flowsheet_topology(session_name: str) -> str:
    """Show all stream connections in the flowsheet.

    Returns a list of: source_block --[stream_name]--> destination_block
    for every stream. Feed streams show (FEED), product streams show (OUT).
    """
    return main_tools.get_flowsheet_topology(manager, session_name)


@tool()
def save_simulation(session_name: str, file_path: str = None) -> str:
    """Save the session's model to its own file, or with file_path save it as that file (the session then follows it). A file about to be overwritten is backed up to ~/.aspen-mcp/checkpoints first."""
    return main_tools.save_simulation(manager, session_name, file_path)


@tool()
def check_inputs(session_name: str) -> str:
    """Check if all required inputs are complete before running.

    Per incomplete object: the form sheet Aspen marks incomplete (where the GUI's Next goes)
    and the fields empty on it. Call this before run_simulation.
    """
    return main_tools.check_inputs(manager, session_name)


@tool()
def get_value(
    session_name: str,
    aspen_path: str = None,
    paths: list[str] = None,
) -> str:
    """Read a value from Aspen Plus.

    Single:  get_value(session, aspen_path='\\Data\\Blocks\\B1\\Input\\TEMP')
    Batch:   get_value(session, paths=['\\Data\\Blocks\\B1\\Output\\B_TEMP', '\\Data\\Blocks\\B1\\Output\\QCALC'])
    """
    if paths:
        results = []
        for p in paths:
            results.append(f"{p}: {manager.get_node_value(session_name, p)}")
        return "\n".join(results)
    return value_tools.get_value(manager, session_name, aspen_path)


@tool()
def set_value(
    session_name: str,
    aspen_path: str = None,
    value: str = None,
    unit: str = None,
    basis: str = None,
    items: list[dict] = None,
) -> str:
    """Set a value in Aspen Plus.

    Single:  set_value(session, aspen_path='\\Data\\Blocks\\B1\\Input\\TEMP', value='100', unit='C')
    Batch:   set_value(session, items=[{"path": "\\...\\TEMP", "value": "80", "unit": "C"}, ...])

    Smart dispatch — provide only what you want to change:
      - value only:  changes the numeric value (keeps current unit & basis)
      - unit only:   changes the unit (keeps current value & basis)
      - basis only:  changes the basis, e.g. 'MASS' or 'MOLE'
      - any combination: changes all specified fields at once
    """
    if items:
        return value_tools.batch_set_values(manager, session_name, items)
    return value_tools.set_value(
        manager, session_name, aspen_path,
        value=value, unit=unit, basis=basis,
    )


@tool()
def get_node_attribute(session_name: str, aspen_path: str, attribute: str) -> str:
    """Read an attribute from a node by attribute name or number.

    Known attributes: VALUE(0), UNITROW(2), UNITCOL(3), OPTIONLIST(5),
    RECORDTYPE(6), ENTERABLE(7), UPPERLIMIT(8), LOWERLIMIT(9),
    VALUEDEFAULT(10), USERENTERED(11), COMPSTATUS(12), BASIS(13),
    INOUT(14), PROMPT(19).

    Example: get_node_attribute(session, '\\Data\\Streams\\FEED\\Input\\FLOW', 'BASIS')
    """
    return main_tools.get_node_attribute(manager, session_name, aspen_path, attribute)


@tool()
def set_node_attribute(session_name: str, aspen_path: str, attribute: str, value: str) -> str:
    """Write an attribute on a node by attribute name or number.

    Use this to change basis, unit settings, or other node attributes
    without changing the node's value. Works on container nodes too.

    Example: set_node_attribute(session, '\\Data\\Streams\\FEED\\Input\\FLOW', 'BASIS', 'Mass-Flow')
    """
    return main_tools.set_node_attribute(manager, session_name, aspen_path, attribute, value)


@tool()
def set_engine_file(session_name: str, file_path: str, kind: str = "linker_options") -> str:
    """Set a Run Settings > Engine Files entry, which set_value cannot reach.

    kind: linker_options (the DLL list a user Fortran model needs), run_def, insert_lib,
    stream_lib, cost, pp1a, pp1b, pp2a, pp2b, pp2c. file_path: an existing file; "" clears it.
    """
    return manager.set_engine_file(session_name, kind, file_path)


@tool()
def get_node_unit_info(session_name: str, aspen_path: str) -> str:
    """Get unit information for a node: current unit, dimension, and all available units.

    Example: get_node_unit_info(session, '\\Data\\Blocks\\COMP\\Input\\PRES')
    """
    return main_tools.get_node_unit_info(manager, session_name, aspen_path)


@tool()
def list_node_children(session_name: str, aspen_path: str) -> str:
    """List all child elements of a node in the Aspen Plus data tree.

    Use this to explore the tree structure.
    Example paths: '\\Data\\Properties\\Parameters', '\\Data\\Blocks'
    """
    return main_tools.list_node_children(manager, session_name, aspen_path)


# ==================================================================
# Observational knowledge extraction (2)
# ==================================================================

@tool()
def snapshot_tree(
    session_name: str,
    root_path: str,
    input_only: bool = True,
    count_only: bool = False,
    label: str = None,
) -> str:
    """Snapshot the Aspen node tree under root_path (stored server-side) to observe a GUI demonstration.

    Snapshot BEFORE the user demonstrates a setup in the Aspen GUI, again AFTER, then
    diff_snapshot(session, id_before, id_after) reveals exactly what changed -- values,
    units, recordtypes, added/removed nodes -- without knowing the parameters in advance.
    root_path: subtree to frame, e.g. '\\Data\\Blocks\\<BLOCK>\\Input'; keep it narrow.
    input_only (True): skip the Output branch so the diff shows deliberate edits, not results.
    count_only: only report how many leaves root_path covers -- probe size first, narrow if large.
    Returns just an id + node count; the tree itself never enters the conversation.
    Snapshots are in-memory only and cleared on server restart.
    (Full workflow: observation-knowledge-extraction skill.)
    """
    return knowledge_tools.run_snapshot(
        manager, session_name, root_path,
        input_only=input_only, count_only=count_only, label=label,
    )


@tool()
def diff_snapshot(session_name: str, id_before: str, id_after: str) -> str:
    """Diff two snapshots from snapshot_tree and return ONLY the delta.

    Reports nodes changed / added / removed between id_before and id_after. Changed
    nodes list each differing item (value, unit, recordtype, basis, ...) as old -> new;
    added nodes show value + recordtype/unit/basis inline. recordtype identifies the
    object type (e.g. LHHW). The full snapshots stay server-side; only this small delta
    reaches you, so it is exactly what the user demonstrated. Take id_before before the
    demonstration and id_after after it.
    """
    return knowledge_tools.run_diff(manager, session_name, id_before, id_after)


# ==================================================================
# Flowsheet tools (5)
# ==================================================================

@tool()
def place_block(
    session_name: str,
    block_name: str = None, block_type: str = None,
    blocks: list[dict] = None,
) -> str:
    """Place block(s) on the flowsheet.

    Single: place_block(session, block_name='R1', block_type='RCSTR')
    Batch:  place_block(session, blocks=[{"name": "R1", "type": "RCSTR"}, {"name": "COL1", "type": "RadFrac"}])
    IDs: at most 8 letters, digits or -.
    Blocks land at default coordinates (stacked) — after the flowsheet is
    fully built and connected, call layout_flowsheet once to arrange it.
    """
    if blocks:
        return intercept.each(blocks, lambda b: flowsheet_tools.place_block(
            manager, session_name, b["name"], b["type"]))
    return flowsheet_tools.place_block(manager, session_name, block_name, block_type)


@tool()
def remove_block(session_name: str, block_name: str) -> str:
    """Remove a block from the flowsheet"""
    return flowsheet_tools.remove_block(manager, session_name, block_name)


@tool()
def place_stream(
    session_name: str,
    stream_name: str = None, stream_type: str = "MATERIAL",
    streams: list[dict] = None,
) -> str:
    """Place stream(s) on the flowsheet.

    Single: place_stream(session, stream_name='FEED', stream_type='MATERIAL')
    Batch:  place_stream(session, streams=[{"name": "FEED"}, {"name": "PROD", "type": "MATERIAL"}])
    IDs: at most 8 letters, digits or -.
    """
    if streams:
        return intercept.each(streams, lambda s: flowsheet_tools.place_stream(
            manager, session_name, s["name"], s.get("type", "MATERIAL")))
    return flowsheet_tools.place_stream(manager, session_name, stream_name, stream_type)


@tool()
def remove_stream(session_name: str, stream_name: str) -> str:
    """Remove a stream from the flowsheet"""
    return flowsheet_tools.remove_stream(manager, session_name, stream_name)


@tool()
def connect_stream(
    session_name: str,
    block_name: str = None, stream_name: str = None,
    port_name: str = None, block_type: str = None,
    connections: list[dict] = None,
) -> str:
    """Connect stream(s) to block port(s).

    Single: connect_stream(session, block_name='R1', stream_name='FEED', port_name='F(IN)', block_type='RCSTR')
    Batch:  connect_stream(session, connections=[
                {"stream": "FEED", "block": "R1", "port": "F(IN)", "block_type": "RCSTR"},
                {"stream": "PROD", "block": "R1", "port": "P(OUT)", "block_type": "RCSTR"}])
    When construction is complete, call layout_flowsheet once — otherwise
    the diagram stays stacked at the origin.
    """
    if connections:
        return intercept.each(connections, lambda c: flowsheet_tools.connect_stream(
            manager, session_name, c["block"], c["stream"], c["port"], c.get("block_type")))
    return flowsheet_tools.connect_stream(manager, session_name, block_name, stream_name, port_name, block_type)


@tool()
def disconnect_stream(session_name: str, stream_name: str, block_name: str = None, port_name: str = None) -> str:
    """Take a stream off block port(s); the stream and its inputs stay.

    With block_name + port_name: that end only. With stream_name alone: every end
    (block_name alone: its ends on that block); the answer lists each port.
    """
    if block_name and port_name:
        return flowsheet_tools.disconnect_stream(manager, session_name, stream_name, block_name, port_name)
    if port_name:
        return f"Failed to disconnect '{stream_name}': port_name needs block_name."
    ends, answer = flowsheet_tools.stream_ends(manager, session_name, stream_name, block_name)
    if answer is not None:
        return answer
    return intercept.each(ends, lambda e: flowsheet_tools.disconnect_stream(
        manager, session_name, e["stream_name"], e["block_name"], e["port_name"]))


@tool()
def layout_flowsheet(session_name: str, from_workbench: bool = False) -> str:
    """Auto-arrange the flowsheet diagram left-to-right by process order.

    Removes only the drawing from the .bkp and reopens -- Aspen redraws it
    with proper icons and routed streams; data and file settings are kept.
    The session is briefly closed and reopened (~5-10 s). Run it once when
    a request's place_block / connect_stream edits, which stack everything
    at the origin, are done.

    from_workbench=true: instead put Aspen's blocks where the user arranged
    them in the workbench (docs/mcp/workbench/window.md, Arrangement).
    """
    if from_workbench:
        arrange, why = _wb.aspen_arrangement(session_name)
        if arrange is None:
            return why
        return flowsheet_tools.layout_flowsheet(manager, session_name, arrange=arrange)
    return flowsheet_tools.layout_flowsheet(manager, session_name)


# ==================================================================
# Property method tools (2)
# ==================================================================

@tool()
def get_property_method(session_name: str) -> str:
    """Get the current global property method"""
    return _get_prop(manager, session_name)


@tool()
def set_property_method(session_name: str, method: str) -> str:
    """Set the global property method (e.g. NRTL, UNIQUAC, PENG-ROB, IDEAL)"""
    return _set_prop(manager, session_name, method)


@tool()
def add_component(
    session_name: str,
    component_id: str = None,
    components: list[str] = None,
) -> str:
    """Add a component to the simulation component list (e.g. WATER, ETHANOL, METHANOL).

    Accepts any component name, synonym, CAS number, or short ID.
    Long names are auto-resolved via the Aspen databank.

    Single: add_component(session, component_id='WATER')
    Batch:  add_component(session, components=['WATER', 'ETHANOL', 'METHANOL'])
    """
    if components:
        return intercept.each(components, lambda comp: _add_comp(manager, session_name, comp))
    return _add_comp(manager, session_name, component_id)


@tool()
def remove_component(session_name: str, component_id: str) -> str:
    """Remove a component from the simulation component list by its label ID"""
    return _rm_comp(manager, session_name, component_id)


@tool()
def add_side_duty(session_name: str, block_name: str, stage: int, duty: float) -> str:
    """Add or update a side duty (heater/cooler) on a RadFrac stage.

    Creates a new HEATER_DUTY entry if the stage doesn't have one,
    or updates the existing value. Use positive values for heating,
    negative for cooling.

    Args:
        block_name: RadFrac block name (e.g. 'STRIP', 'RECT').
        stage: Stage number (integer).
        duty: Heat duty value in current display unit (e.g. cal/sec).
    """
    return _add_side_duty(manager, session_name, block_name, stage, duty)


@tool()
def remove_side_duty(session_name: str, block_name: str, stage: int) -> str:
    """Remove a side duty entry from a RadFrac stage.

    Args:
        block_name: RadFrac block name.
        stage: Stage number to remove the duty from.
    """
    return _rm_side_duty(manager, session_name, block_name, stage)



# ==================================================================
# Reaction tools (4)
# ==================================================================

@tool()
def add_reaction_set(
    session_name: str, reaction_set_name: str,
    reaction_type: str = "POWERLAW"
) -> str:
    """Create a new reaction set (e.g. POWERLAW, LHHW, REAC-DIST).

    This creates the reaction set container. Use add_reaction next to
    define individual reactions with stoichiometry inside the set.

    Args:
        reaction_set_name: Name for the set (e.g. 'R-1').
        reaction_type: Model type — POWERLAW, LHHW, GENERAL, REAC-DIST, USER, or a polymer type
                       (FREE-RAD, ZIEGLER-NAT, EMULSION, STEP-GROWTH, SEGMENT-BAS).
                       Equilibrium reactions are a REACTYPE of a set, not a set type.
                       Fields of each type: docs/reactions/reactions.md.
    """
    return _add_rxn_set(manager, session_name, reaction_set_name, reaction_type)


@tool()
def create_chemistry(
    session_name: str,
    reactions: list[dict],
    chemistry_name: str = "GLOBAL",
    bind_global: bool = True,
) -> str:
    """Create an electrolyte Chemistry object (equilibrium ionic reactions).

    Saves the .bkp, splices a CHEMISTRY paragraph into the text and reopens
    the file -- the COM tree cannot build these objects incrementally.
    The session is briefly closed and reopened; expect ~5-10 s.

    reactions: [{'reactants': {cid: coef}, 'products': {cid: coef},
                 'keq': {'A':..,'B':..,'C':..,'D':..} (optional -- omit to
                 compute Keq from Gibbs free energy)}]
    Coefficients positive on both sides; reactants are negated automatically.
    bind_global: also set GCHEMISTRY so the property method uses the object.
    Fields and recipe: docs/properties/properties-chemistry.md.
    """
    return _create_chemistry(
        manager, session_name, reactions, chemistry_name, bind_global)


@tool()
def remove_reaction_set(session_name: str, reaction_set_name: str) -> str:
    """Remove a reaction set and all its reactions."""
    return _rm_rxn_set(manager, session_name, reaction_set_name)


@tool()
def remove_reaction(
    session_name: str, reaction_set_name: str, reaction_no: int
) -> str:
    """Remove a single reaction from a reaction set.

    Removes the specified reaction number and all its associated data
    (stoichiometry, exponents, kinetics) while keeping other reactions.

    Args:
        reaction_set_name: Reaction set name (e.g. 'R-1').
        reaction_no: Reaction number to remove (e.g. 2).
    """
    return _rm_rxn(manager, session_name, reaction_set_name, reaction_no)


@tool()
def add_reaction(
    session_name: str, reaction_set_name: str,
    reaction_no: int,
    reactants: dict[str, float],
    products: dict[str, float],
    phase: str = "L",
    exponents: dict[str, float] = None,
) -> str:
    """Add a reaction with stoichiometry to an existing reaction set.

    Creates the reaction and sets stoichiometric coefficients and
    concentration exponents for the rate law.

    Args:
        reaction_set_name: Reaction set name (e.g. 'R-1').
        reaction_no: Reaction number within the set (usually 1).
        reactants: {component_id: coefficient} — use positive values,
                   Aspen auto-negates (e.g. {'ACETICAC': 1, 'METHANOL': 1}).
        products: {component_id: coefficient} — use positive values
                  (e.g. {'METHYLAC': 1, 'WATER': 1}).
        phase: 'L' (liquid) or 'V' (vapor).
        exponents: {component_id: exponent} for rate law. If omitted,
                   defaults to abs(reactant coefficients).
    """
    return _add_rxn(
        manager, session_name, reaction_set_name, reaction_no,
        reactants, products, phase, exponents,
    )


# ==================================================================
# Generic Elements tools (5)
# ==================================================================

@tool()
def list_elements(session_name: str, aspen_path: str) -> str:
    """List all elements under a node in the data tree.

    Shows index, name, and value for each element.
    Use this to explore table/collection nodes.

    Example: list_elements(session, '\\Data\\Blocks')
    """
    return manager.list_elements(session_name, aspen_path)


@tool()
def add_element(session_name: str, aspen_path: str, name: str) -> str:
    """Add an element to a node via Elements.Add(name).

    Use 'NAME!TYPE' syntax for typed elements (e.g. 'B1!Heater', 'R1!POWERLAW').
    This is the generic version of place_block, place_stream, etc.

    Examples:
      - add_element(session, '\\Data\\Blocks', 'PUMP1!Pump')
      - add_element(session, '\\Data\\Reactions\\Reactions', 'RXN1!POWERLAW')
    """
    return manager.add_element(session_name, aspen_path, name)


@tool()
def remove_element(session_name: str, aspen_path: str, name: str) -> str:
    """Remove an element from a node by name via Elements.Remove(name).

    Examples:
      - remove_element(session, '\\Data\\Blocks', 'PUMP1')
      - remove_element(session, '\\Data\\Streams', 'S1')
    """
    return manager.remove_element(session_name, aspen_path, name)


@tool()
def insert_row(session_name: str, aspen_path: str, dimension: int = 0) -> str:
    """Insert a new row in a table node.

    Use this for table-type nodes that require adding rows
    (e.g. component lists, reaction stoichiometry, sensitivity variables).
    Returns the index of the newly inserted row.
    Use set_label separately if the row needs a label.

    Args:
        aspen_path: Path to the table node.
        dimension: Table dimension (default 0).

    Example: insert_row(session, '\\Data\\Blocks\\R1\\Input\\RXN_ID')
    """
    return manager.insert_row(session_name, aspen_path, dimension)


@tool()
def set_label(session_name: str, aspen_path: str, index: int, label: str, dimension: int = 0) -> str:
    """Set the label of a row in a table node.

    Use this after insert_row to assign a label to the new row.
    Some table dimensions do not support labels — in that case, skip this step.

    Args:
        aspen_path: Path to the table node.
        index: Row index to label.
        label: Label string.
        dimension: Table dimension (default 0).

    Example: set_label(session, '\\Data\\Blocks\\R1\\Input\\RXN_ID', 0, 'CRACKING')
    """
    return manager.set_label(session_name, aspen_path, index, label, dimension)


@tool()
def remove_row(session_name: str, aspen_path: str, index: int, dimension: int = 0) -> str:
    """Remove a row from a table node by index.

    Args:
        aspen_path: Path to the table node.
        index: Row index to remove (0-based).
        dimension: Table dimension (default 0).

    Use list_elements to see current indices before removing.
    """
    return manager.remove_row(session_name, aspen_path, index, dimension)


# ==================================================================
# Discovery tool (1)
# ==================================================================

@tool()
def discover_ports(session_name: str, block_types: list[str] = None) -> str:
    """Auto-discover block ports via COM API.

    Places a temporary block of each type under a free name (existing blocks are never
    touched), reads its ports, removes it, and saves results to
    ~/.aspen-mcp/block_ports.json, which overlays the shipped table and applies at once.
    Requires an active Aspen session (preferably a blank simulation).

    Args:
        block_types: Optional list of block type names to discover.
                     If omitted, re-discovers every type in the shipped and user tables.
    """
    try:
        results, errors = _discover_ports(manager, session_name, block_types)
        summary_lines = [f"Discovered ports for {len(results)} block types:"]
        for bt, ports in sorted(results.items()):
            summary_lines.append(f"  {bt}: {', '.join(ports) if ports else '(none)'}")
        if errors:
            summary_lines.append(f"\nFailed for {len(errors)} block types:")
            for err in errors:
                summary_lines.append(f"  {err}")
        return "\n".join(summary_lines)
    except Exception as exc:
        return f"Port discovery failed: {exc}"


# ==================================================================
# Optimization tools
# ==================================================================

@tool()
async def optimize(
    session_name: str,
    algorithm: str,
    variables: list[dict] = None,
    objectives: list[dict] = None,
    constraints: list[dict] = None,
    eval_budget: int = None,
    options: dict = None,
    seed: int = None,
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str = None,
    resume_from: str = None,
    finish: str = "restore",
    ctx: Context = None,
) -> str:
    """Optimize (or map) an Aspen Plus flowsheet with one external algorithm.

    dry_run=True (default) previews the setup without running; call again with
    dry_run=False to run.

    algorithm:
      'afmcbo'   constrained BO with one feasibility GP per crash mechanism; for expensive
                 runs that crash in several distinct ways (different blocks or kinds)
      'cbo'      constrained BO with one feasibility GP; optimum near a crash boundary or
                 many runs crash
      'bo'       Bayesian optimization, crashes penalized (1 objective: scikit-optimize,
                 2+: qLogNEHVI); expensive runs that rarely crash
      'nsga2'    NSGA-II; 1-2 objectives with a generous budget
      'nsga3'    NSGA-III; 3+ objectives
      'de'       DE for 1 objective, GDE3 for 2+ ('gde3' = same, 2+ required)
      'pso'      PSO for 1 objective, MOPSO for 2+ ('mopso' = same, 2+ required)
      'gradient' SLSQP from one start point; cheap, smooth responses
      'grid'     full grid sweep recording feasibility and the Aspen failure reason per
                 point; maps the space, does not optimize

    variables:   [{aspen_path, lower, upper, type?: 'int', points?: int (grid only)}]
    objectives:  [{aspen_path | aspen_paths: [...], expression?, direction: 'minimize'|'maximize'}]
                 expression combines v0, v1, ... (values of aspen_paths; supports
                 sqrt/log/log10/exp/sin/cos/tan/floor/ceil/fabs/abs/pow/max/min/pi/e); omitted with
                 aspen_paths = sum. Optional for grid.
    constraints: optional [{aspen_path, lower?, upper?}]
    eval_budget: total Aspen evaluations; the algorithm sizes itself from it (approximate
                 for gradient). Omit to use the algorithm's defaults. With resume_from,
                 resumed evaluations count.
    options:     algorithm-specific settings, rarely needed (e.g. pop_size, n_initial, q,
                 min_count, x0); unknown keys are rejected with the valid list.
    output_dir:  writes report.md + evaluations.csv + config.json into a timestamped
                 folder; omitted = nothing saved (grid: the working directory).
    resume_from: bo / cbo / afmcbo only. A prior run folder or evaluations.csv, replayed
                 into the GP without Aspen calls; its config.json restores variables,
                 objectives and constraints, so they may be omitted.
    finish:      'restore' (default) | 'best' | 'last' -- where the model is left
    Full guide: docs/mcp/optimize/index.md, then the method's own doc.
    """
    rep: dict = {}
    res = await _run_optimize(
        manager, session_name, algorithm,
        variables=variables, objectives=objectives, constraints=constraints,
        eval_budget=eval_budget, options=options, seed=seed,
        max_retries=max_retries, dry_run=dry_run, output_dir=output_dir,
        resume_from=resume_from, finish=finish, ctx=ctx, report=rep,
    )
    intercept.annotate(report=rep)                # the journal's summary of this optimization
    return res


# ==================================================================
# Workbench: block editor window over a live session
# ==================================================================

@tool()
async def open_workbench(session_name: str, new_tab: bool = False, title: str = None,
                         lang: str = None, ctx: Context = None) -> str:
    """Open the Aspen Workbench window and show the session's model tab. One window holds
    one tab per model; a tab has its own block program and shows its session's flowsheet,
    its extra programs and your proposals are its sub-tabs.

    The user assembles programs from blocks, clicks streams and blocks to inspect them,
    or asks the AI about a stream or block ("outlet purity > 99%"; the `notes`). Read those
    with workbench_read and answer with workbench_edit: the window updates within a second.
    new_tab: add a program sub-tab in the model's tab. lang: "en" or
    "zh" -- set "zh" when the user writes Chinese. Guide: docs/mcp/workbench/index.md.
    """
    _hold(ctx)
    return await _wb.open_workbench(manager, session_name, new_tab=new_tab, title=title, lang=lang)


@tool()
def workbench_read(session_name: str = None, tab: str = None, ctx: Context = None) -> str:
    """Read a workbench tab: the session's Ask AI requests (notes), the selection, the program
    (statements with ids), the flowsheet with block errors, the last run's log and
    tables, and the list of tabs. Defaults to the active tab; session_name or
    tab (id or title) picks another. Call it whenever the user refers to the workbench.
    """
    _hold(ctx)
    return _wb.workbench_read(manager, session_name, tab)


@tool()
def workbench_edit(
    session_name: str = None,
    tab: str = None,
    program: list[dict] = None,
    insert: list[dict] = None,
    after_id: str = None,
    remove_ids: list[str] = None,
    highlight: list[dict] = None,
    message: str = None,
    note_replies: list[dict] = None,
    refresh_flowsheet: bool = False,
    lang: str = None,
    proposal: dict = None,
) -> str:
    """Change a workbench tab live (default: the active tab).

    program: replace the whole program. insert: statements to add after statement
    after_id (omit after_id to append at the end). remove_ids: statements to delete.
    Statements (ids are added when missing):
      {"do": "set", "path", "value" | "expr", "unit"?, "basis"?}   {"do": "run", "reinit"?}
      {"do": "read", "path", "as"}             {"do": "log", "text"}  ("{var}" is filled in)
      {"do": "calc", "as", "expr", "unit"?}    {"do": "def", "name", "params", "expr"}
      {"do": "if", "left": {"path"} | {"var"} | {"expr"}, "op": ">"|">="|"<"|"<="|"=="|"!=",
       "right": number | expression, "then": [...], "else": [...]}
      {"do": "repeat", "times", "body": [...]}  {"do": "until", "cond", "max"?, "body": [...]}
      {"do": "sweep", "path", "from", "to", "steps", "unit"?, "as"?, "body": [...]}
      {"do": "seek", "path", "lower", "upper", "measure", "target", "unit"?, "tol"?, "body": [...]}
      loops take "record": [names] to keep only those columns in their table
      {"do": "table", "title", "rows"?, "row_label"?, "columns": [{"label", "path" | "expr", "unit"?}]}
       | {"do": "table", "title", "loop" (a loop's id), "vars"?}  a loop's results, one row per pass
      {"do": "plot", "title", "x_from"?, "x_to"?, "y_from"?, "y_to"?, "xlabel"?, "ylabel"?,
       "series": [{"loop", "ycols", "xcol"?} | {"label", "expr" (of x), "from"?, "to"?, "color"?, "dash"?}
       | {"label", "x"}]}  a data line plots a loop's results; no x range: the data's
      {"do": "save", "path"?}                  {"do": "proc", "name", "params"?, "body": [...]}
      {"do": "call", "name", "args"?}
      {"do": "pinch", "dtmin"?, "auto"?, "exclude"?, "streams"?: [{"name", "t_in", "t_out",
       "duty"}], "matches"?}  heat-integration targets from the live model
      {"do": "optimize", "algorithm", "eval_budget",
       "variables": [{"path", "lower", "upper"}], "objectives": [{"path", "direction"}],
       "constraints": [{"path", "lower" | "upper"}], "options"?, "seed"?}
      an objective or constraint may give "expr" instead of "path": an expression over its
      own "paths": {name: path}, or over variables set by read/calc before the step
      flowsheet: {"do": "place", "block", "type"} | {"do": "place", "stream"}  {"do": "connect",
       "stream", "block", "port"}  {"do": "remove", "block" | "stream" (+"block","port": unhook)}
       {"do": "component", "add" | "remove"}  {"do": "method", "method"}
      {"do": "group", "title", "why"?}  a heading: the top-level steps after it, up to the next
       group, are one group (a run by group pauses before each)
    Paths are exact Aspen tree paths: look them up in the docs, never guess. Without
    "unit" a value is taken in the field's current unit. "{row}" in a table column
    stands for the row's name. Details and expressions: docs/mcp/workbench/program-format.md.
    highlight: [{"kind": "stream" | "block", "name", "note"?}] outlines them ([] clears);
    a note stays pinned on it for the user.
    message: shown in the tab's AI chat. note_replies: [{"id", "reply", "done"?,
    "choices"?, "multi"?, "working"?}] answers or closes Ask AI requests ("working": true
    when more work follows this reply); "choices" [{"label",
    "detail"?}] (2-6) put buttons under the reply for the user to click (one, or several
    with "multi": true), and the pick arrives as a new request with "answer_to" (the id
    asked) and "picked" (the labels). refresh_flowsheet: re-read the flowsheet after a
    topology change. lang: "en" or "zh". Build the program for the user to review and
    run; run it yourself only when asked.
    proposal: {"title", "reason", "status"?: "draft"|"withdrawn"}: a proposal tab only the user may run.
    Its "watch"?: [{"path", "label"?}] names results to tag after its run, the goal first;
    "explain"? (after the run) says how the change reached them (docs/mcp/workbench/proposals.md).
    """
    return _wb.workbench_edit(
        manager, session_name, tab, program=program, insert=insert, after_id=after_id,
        remove_ids=remove_ids, highlight=highlight, message=message,
        note_replies=note_replies, refresh_flowsheet=refresh_flowsheet, lang=lang, proposal=proposal,
    )


@tool()
async def workbench_run(session_name: str = None, tab: str = None, dry_run: bool = True) -> str:
    """Run a workbench tab's program (default: the active tab) and return its log, plus
    its loop tables, tables and plots. dry_run=True (default) checks every path and unit and previews
    optimize steps without changing the simulation; dry_run=False sets values, runs
    Aspen and optimizes. Ask before dry_run=False.
    """
    return await _wb.workbench_run(manager, session_name, tab, dry_run=dry_run)


# ==================================================================
# Energy analysis tool (1)
# ==================================================================

@tool()
async def pinch_analysis(
    streams: list[dict],
    dt_cont_default: float = 5.0,
    project_name: str = "Plant",
    include_curves: bool = False,
    utilities: list[dict] = None,
    timeout: int = 120,
) -> str:
    """Pinch analysis (OpenPinch) — minimum hot/cold utility targets + pinch temperature.

    Feed it the thermal stream table extracted from a CONVERGED flowsheet; returns the
    energy targets (compare against current utility duties = savings potential), the
    pinch temperature, and per-level utility breakdown. Pure computation in a separate
    subprocess (uv-provisioned Python 3.14 + OpenPinch) — needs no Aspen session.
    streams: [{name, t_supply, t_target, heat_flow_kw, dt_cont?, zone?,
    type?('hot'|'cold' — required only for isothermal condenser/reboiler duties)}],
    temperatures in degC. include_curves=True adds composite/GCC curve points (large).
    How to extract streams from Aspen + interpret results: docs/mcp/pinch-analysis.md.
    """
    # A subprocess of up to `timeout` s (plus uv's first-run setup): run it off the event
    # loop, or every other request and the workbench heartbeat stall with it. No COM here.
    return await asyncio.to_thread(
        _pinch_analysis,
        streams, dt_cont_default=dt_cont_default, project_name=project_name,
        include_curves=include_curves, utilities=utilities, timeout=timeout,
    )


@tool()
async def pinch_matches(
    streams: list[dict],
    dt_cont_default: float = 5.0,
    forbidden_pairs: list[list[str]] = None,
    weights: dict = None,
    extra_units: int = 0,
    n_alternatives: int = 8,
    timeout: int = 180,
) -> str:
    """Heat-exchanger match suggestions — minimum-matches MILP with exhaustive enumeration.

    Run after `pinch_analysis` with the SAME stream table: splits the problem at the
    pinch and solves the Papoulias-Grossmann transshipment MILP per region, then
    enumerates ALL alternative optimal match sets (integer cuts) so no combination is
    missed. Each option lists hot↔cold pairs with duties (utility matches marked).
    forbidden_pairs: [[hot_name, cold_name], ...] — exclude unsafe/impractical pairs.
    weights: {"HOT|COLD": w} implementation-difficulty weights (default 1 per match).
    extra_units: also enumerate sets with up to N_min+extra matches.
    Interpretation + workflow: docs/mcp/pinch-analysis.md.
    """
    return await asyncio.to_thread(
        _pinch_matches,
        streams, dt_cont_default=dt_cont_default, forbidden_pairs=forbidden_pairs,
        weights=weights, extra_units=extra_units, n_alternatives=n_alternatives,
        timeout=timeout,
    )


# ==================================================================
# Error history (1)
# ==================================================================

@tool()
def record_error(
    error_keyword: str,
    block_type: str,
    property_method: str,
    cause: str,
    fix_direction: str,
    fix_path: str,
    tried_failed: str = "",
) -> str:
    """Record a confirmed fix in this machine's error history (ASPEN_USER_DATA/error-history.md) so later sessions find it.

    Call it after a simulation error is fixed and a run confirms it. Generalize real block
    and component names to {name} / {component}. Nothing leaves the machine.

    Args:
        error_keyword: Error message keyword (e.g. 'COLUMN NOT IN MASS BALANCE').
        block_type: Block type involved (e.g. 'RadFrac', 'RCSTR').
        property_method: Property method used (e.g. 'NRTL', 'PENG-ROB').
        cause: Root cause.
        fix_direction: What fixed it.
        fix_path: Aspen path that was changed (e.g. 'Data.Blocks.{name}.Input.BASIS_D').
        tried_failed: What was tried and did not work (optional).
    """
    return _record_error(
        error_keyword=error_keyword,
        block_type=block_type,
        property_method=property_method,
        cause=cause,
        fix_direction=fix_direction,
        fix_path=fix_path,
        tried_failed=tried_failed,
        root=_USER_DATA,
    )


# Startup check: a tool registered without @tool() above, or a row of intercept.TOOLS
# left over from a removed tool, stops the server here.
intercept.verify(mcp)

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
