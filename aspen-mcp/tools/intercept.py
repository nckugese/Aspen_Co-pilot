"""One interception point for every MCP tool: the classification table ``TOOLS`` and the
``@tool()`` decorator server.py registers every tool with.

    tool = intercept.make(mcp, lambda: manager, hooks)      # server.py, once
    @tool()
    def set_value(session_name: str, ...) -> str: ...        # registered through one async wrapper
    ...
    intercept.verify(mcp)                                     # last line: an unclassified tool fails startup
    res, rp = intercept.measured(manager, book, "place_block", args, fn)   # a program statement, measured alike

Each tool is registered as an ``async`` wrapper whose signature is the tool's own plus, for the
kinds that change a model, an optional ``reason`` (keyword-only, no description: the server
instructions' ``reason`` rule says what it is for, once instead of on every tool). ``tools/list`` is otherwise what the bare function
gave, with MCP annotations from the tool's row (readOnlyHint / destructiveHint /
idempotentHint / openWorldHint). The decorator returns the function itself, so
``server.<tool>(...)`` still calls it directly, unrecorded.

Per call (``_call``): hold the client session for Ask AI pushes; journal what was changed in
Aspen's own window since the last compare (``hooks.external``: gated, before anything of
the call's, so its brief tells it; never waited on); show the call as in flight
(``tools/activity.py``); a changing call waits for its session's writer (a program or
an optimize holding it) and is refused -- journaled, no exception -- when that takes more
than ``activity.WRITER_WAIT_S``; join the AI's change group
(``journal.GROUPS.ai`` ... ``end``; ``hooks.note_state`` is the Ask AI note it is for);
a call whose row has ``cp`` first gets a restore point of its model (``restore_point``:
a record of its own, ahead of the call's; none made -- too slow, failed -- a line at the end
of the answer says so; a value call pays one attribute test for this);
for a changing call with the journal on, open a
recording scope (``tools/recorder.py``; an ``Aggregate`` for an optimization, whose ``begin``
record is written as it starts, so a server killed mid-optimize leaves it) around the tool
-- a sync tool still runs right here on the event loop thread, as FastMCP ran it before (COM
is apartment-bound; never move it to a worker). A tool that raises gets an ``error`` record
and the exception goes on unchanged, so FastMCP's error text is what it was. Last, the layout
reminder (``_layout_due``) may add a line to the answer, and a call that ends well gets
what others changed in its models since the AI's last call at its top (tools/brief.py).
A call whose exception or answer carries Aspen's internal fault (RPC_E_SERVERFAULT) flags its
session, whose runs are then refused until it is reopened (``_fault``; ``measured`` alike).
Bookkeeping never fails a tool: every step of it is guarded and logged.

``TOOLS`` columns: ``kind`` read | value | structure | run | file | batch
| config | ui; ``destructive``; ``probe``: how tools/probes.py measures the call before and
after it (``kid:<path>`` / ``row:<path>`` the element the arguments name, ``kids:<folder>`` /
``rows:<table>`` all of them, ``port``, ``run``, ``sess``, ``file``, ``args:<path>``, ``hook``
the value hook, joined with ``+``: its docstring has the notation;
``sum`` an Aggregate, ``prog`` the workbench program records itself, None nothing) -- and
every changing call but a config one leaves at least one record; ``items``: the batch
parameter (``each`` measures it item by item); ``refresh``: what the window re-reads
afterwards (``topology*``: only for a topology path, see ``refresh_of``); ``undo``: how it is
taken back; ``writer``: the call waits for its session's holder -- a name (``"optimizer"``):
it also holds the session for its whole run, as that actor; ``phase``: what the activity bar
shows it doing; ``topo`` (the layout reminder: True, or "path"); ``idempotent``;
``open_world``; ``dry``: the parameter that, when true, makes the call a read; ``cp``: a
restore point of the model before the call (``restore_point``) -- "group": before its change
group's first structural change, "call": before each (non-dry) call, None: never (a value, a
file tool: create_chemistry keeps one through ``patch_file(keep=True)``); ``risk``:
True -- the "risk" mode asks the user first (a confirmation card), a name -- only when that
condition holds (``save_other``, ``program``: tools/brake_effects via the Brake's ``cond``),
False -- never (it keeps a backup), None -- not a risky tool; a destructive tool must say.

The brakes (``hooks.gate``: the workspace's tools/brake.Brake, None without one).
A changing AI call the window's mode or pause or a card concerns joins the AI's group, then
waits -- an asyncio Future on the event loop (``_wait``), no COM touched, the window's own
jobs run meanwhile -- before the Aspen-window check, the writer wait and anything of the call's: refused in Observe, held
while paused (one hold per pause; a resume judges it again, and a model someone else
changed meanwhile refuses it with the brief), a card for a risky call. The hold and the writer
wait share one wall-clock ``Budget`` (brake.hold_s of the client); past its safe margin
nothing is applied inside the call: an approval then runs after the answer (``late`` ->
``replay``: the same pipeline as the user's, "AI proposed, you executed"). A client's
cancel goes through unchanged and leaves the card open. A refused call is journaled
(``refused``, a ``gate`` field) and answered "Not applied ..."; an applied one's records
carry ``gate`` (confirmed, allowed for the group, the window not live).

Learning mode (tools/learn.py; any window state, every registration of this server): a changing AI
call of kind value, structure or batch (not a dry run) whose ``reason`` is missing, or weak
for the first time in a while, is refused before the brakes, the Aspen-window check and any COM -- "Not applied
...", a ``refused`` record with ``learn`` in the AI's group, so its retry joins the same group
-- unless Observe refuses it anyway. A weak one let through carries ``reason_weak`` on its
records ("remind": and a reminder as its answer's last line).

Stdlib only at import (mcp's types are taken in ``make``); no COM of its own.
"""
from __future__ import annotations

import asyncio
import contextvars
import functools
import inspect
import json
import logging
import re
import time
import typing
from dataclasses import dataclass

from tools import activity, brake, brief, journal, learn, probes, recorder, restore_points

logger = logging.getLogger(__name__)

REASON_KINDS = frozenset({"value", "structure", "run", "file", "batch"})
_CHANGE_KINDS = frozenset({"value", "structure", "run", "batch"})
ARGS_MAX = 1024                        # bytes of an argument summary in a record
_perf = time.perf_counter
_CALL: contextvars.ContextVar = contextvars.ContextVar("aspen_mcp_call", default=None)
_ITEMS: contextvars.ContextVar = contextvars.ContextVar("aspen_mcp_items", default=None)
REGISTERED: set = set()                # tool names that went through tool()


@dataclass(frozen=True)
class Spec:
    kind: str
    destructive: bool = False
    probe: str | None = None
    items: str | None = None
    refresh: str | None = None
    undo: str | None = None
    writer: bool | str = False
    phase: str = "call"
    topo: bool | str = False
    idempotent: bool = False
    open_world: bool = False
    dry: str | None = None
    cp: str | None = None
    risk: bool | str | None = None

    @property
    def reason(self) -> bool:
        """The tool takes the optional ``reason`` parameter."""
        return self.kind in REASON_KINDS

    @property
    def changes(self) -> bool:
        """A (non-dry) call may change a model: the brakes' observe mode and pause govern it."""
        return self.kind in _CHANGE_KINDS or bool(self.writer) or self.risk not in (None, False)

    @property
    def records(self) -> bool:
        """A (non-dry) call runs inside a recording scope the wrapper opens."""
        return self.kind != "read" and self.probe not in (None, "prog")

    def annotations(self) -> dict:
        """MCP ToolAnnotations fields."""
        read = self.kind == "read"
        a = {"readOnlyHint": read}
        if not read:
            a["destructiveHint"] = self.destructive
        if self.idempotent:
            a["idempotentHint"] = True
        a["openWorldHint"] = self.open_world
        return a


_B, _S, _RX = r"\Data\Blocks", r"\Data\Streams", r"\Data\Reactions\Reactions"
_C = r"\Data\Components\Specifications\Input\TYPE"
_RT = _RX + r"\{reaction_set_name}\Input\REACTYPE\{reaction_no}"
_W = dict(writer=True)
_WG = dict(writer=True, cp="group")         # structural: a restore point before its group's first one
_R = dict(risk=True)                        # risky: in "risk" mode a confirmation card first

TOOLS: dict[str, Spec] = {
    # -- sessions and files
    "open_aspen_plus":        Spec("file", probe="sess", refresh="topology", undo="none", phase="aspen"),
    "set_reopen_interval":    Spec("config"),
    "create_new_simulation":  Spec("file", probe="sess", refresh="topology", undo="none", phase="aspen", **_R),
    "close_aspen_plus":       Spec("file", True, probe="sess", refresh="topology", undo="none", phase="aspen",
                                   cp="call", risk=False, **_W),  # no card: the before-close restore point keeps unsaved work
    "list_aspen_sessions":    Spec("read"),
    "reinit_simulation":      Spec("run", True, probe="run:reinit", refresh="results", undo="none", phase="aspen",
                                   **_W, **_R),
    "run_simulation":         Spec("run", probe="run", refresh="results", undo="none", phase="aspen", **_W),
    "get_flowsheet_topology": Spec("read"),
    "save_simulation":        Spec("file", True, probe="file", undo="checkpoint", phase="aspen", risk="save_other",
                                   **_W),
    "check_inputs":           Spec("read", phase="aspen"),
    # -- values and the tree
    "get_value":              Spec("read"),
    "set_value":              Spec("value", probe="hook", items="items", refresh="values", undo="value",
                                   idempotent=True, **_W),
    "get_node_attribute":     Spec("read"),
    "set_node_attribute":     Spec("value", probe="hook:attr", refresh="values", undo="value", idempotent=True, **_W),
    "set_engine_file":        Spec("value", idempotent=True, **_W),        # not a tree node: no probe
    "get_node_unit_info":     Spec("read"),
    "list_node_children":     Spec("read"),
    "snapshot_tree":          Spec("read", phase="aspen"),
    "diff_snapshot":          Spec("read"),
    # -- flowsheet
    "place_block":            Spec("structure", probe="kid:" + _B + r"\{block_name}", items="blocks",
                                   refresh="topology", undo="inverse", topo=True, **_WG),
    "remove_block":           Spec("structure", True, probe="kid:" + _B + r"\{block_name}", refresh="topology",
                                   undo="checkpoint", topo=True, **_WG, **_R),
    "place_stream":           Spec("structure", probe="kid:" + _S + r"\{stream_name}", items="streams",
                                   refresh="topology", undo="inverse", topo=True, **_WG),
    "remove_stream":          Spec("structure", True, probe="kid:" + _S + r"\{stream_name}", refresh="topology",
                                   undo="checkpoint", topo=True, **_WG, **_R),
    "connect_stream":         Spec("structure", probe="port", items="connections", refresh="topology",
                                   undo="inverse", topo=True, **_WG),
    "disconnect_stream":      Spec("structure", probe="port", refresh="topology", undo="inverse", topo=True,
                                   **_WG),       # stream alone: each of its ends measured apart (each)
    "layout_flowsheet":       Spec("file", True, probe="file+sess", refresh="topology", undo="checkpoint",
                                   phase="aspen", risk=False, **_W),         # a backup of the file: no card
    # -- properties and components
    "get_property_method":    Spec("read"),
    "set_property_method":    Spec("value", probe="hook", refresh="values", undo="value", idempotent=True, **_W),
    "add_component":          Spec("structure", probe="kids:" + _C, items="components", refresh="topology",
                                   undo="checkpoint", **_WG),         # kids: the label may not be the id given
    "remove_component":       Spec("structure", True, probe="kid:" + _C + r"\{component_id}", refresh="topology",
                                   undo="checkpoint", **_WG, **_R),
    "add_side_duty":          Spec("value", probe=r"args:\Data\Blocks\{block_name}\Input\HEATER_DUTY\{stage}",
                                   refresh="values", undo="checkpoint", **_WG),      # adds a row: structural
    "remove_side_duty":       Spec("structure", True, probe="row:" + _B + r"\{block_name}\Input\HEATER_DUTY\{stage}",
                                   refresh="values", undo="checkpoint", **_WG, **_R),
    # -- reactions
    "add_reaction_set":       Spec("structure", probe="kid:" + _RX + r"\{reaction_set_name}", refresh="values",
                                   undo="checkpoint", **_WG),
    "create_chemistry":       Spec("file", True, probe=r"file+sess+kids:\Data\Reactions\Chemistry",
                                   refresh="topology", undo="checkpoint", phase="aspen", risk=False, **_W),
    "remove_reaction_set":    Spec("structure", True, probe="kid:" + _RX + r"\{reaction_set_name}", refresh="values",
                                   undo="checkpoint", **_WG, **_R),
    "remove_reaction":        Spec("structure", True, probe="row:" + _RT, refresh="values", undo="checkpoint", **_WG,
                                   **_R),
    "add_reaction":           Spec("structure", probe="row:" + _RT + "+hook", refresh="values", undo="checkpoint",
                                   **_WG),
    # -- generic elements
    "list_elements":          Spec("read"),
    "add_element":            Spec("structure", probe=r"kid:{aspen_path}\{name}", refresh="topology*",
                                   undo="inverse", topo="path", **_WG),
    "remove_element":         Spec("structure", True, probe=r"kid:{aspen_path}\{name}", refresh="topology*",
                                   undo="checkpoint", topo="path", **_WG, **_R),
    "insert_row":             Spec("structure", probe="rows:{aspen_path}", refresh="values", undo="inverse", **_WG),
    "set_label":              Spec("structure", probe="rows:{aspen_path}", refresh="values", undo="checkpoint", **_WG),
    "remove_row":             Spec("structure", True, probe="rows:{aspen_path}", refresh="values",
                                   undo="checkpoint", **_WG, risk="own_row"),     # not the AI's own row: a card
    "discover_ports":         Spec("config", probe="kids:" + _B, phase="aspen", **_W),
    # -- optimization, workbench, energy, community
    "optimize":               Spec("batch", probe="sum", refresh="results", undo="value", phase="aspen",
                                   dry="dry_run", writer="optimizer", cp="call"),
    "open_workbench":         Spec("ui"),
    "workbench_read":         Spec("read"),
    "workbench_edit":         Spec("ui", undo="program"),
    "workbench_run":          Spec("batch", probe="prog", phase="aspen", dry="dry_run", risk="program", **_W),
    "pinch_analysis":         Spec("read", phase="compute"),
    "pinch_matches":          Spec("read", phase="compute"),
    "record_error":           Spec("config"),
}


class Hooks:
    """What server.py plugs in, so this module imports nothing of the server or the workbench.
    ``hold(ctx)``: remember the client session Ask AI pushes go to; ``after(session, refresh)``:
    a call ended (``refresh`` None for a read or a call that changes nothing the window
    shows); ``note_state()``: the open Ask AI note;
    ``session_of(tool, args)``: the session a call that names none works on (a workbench
    tab's), for the writer wait and the activity bar; ``types(session)``: {block: type} as the window last read them,
    no COM (the brief names fields by them); ``external(manager, tool, args)``: before anything of
    the call's own, what was changed in Aspen's own window is compared and journaled
    (tools/external.py's pre_call: gated, ~3 us when the gate is shut), so the brief the call
    ends with tells the AI. ``gate()``: the brakes of the window this server serves
    (a tools/brake.Brake), None without a workspace -- every call then passes with nothing
    added; ``gate_done(name, session, call, res)``: a changing AI call ran -- a line for the end
    of its answer (the stuck detector's note) or None; ``effects(name, kw, session, cond)``: what a card
    shows ({risky, more, effects, cp}: tools/brake_effects); ``late(brk, cid, pending)``: a
    card's late apply the workspace runs its own way (a workbench_run card: its tab queued as
    the window's Run, ``late_done`` when it ends) -- an awaitable when it took it, None for the
    replay. ``refuse(name, kw)``: the workspace's own refusal of a changing AI call,
    before the brakes and in every mode (the AI's real run of a proposal tab: only the user runs
    one) -- its answer, or None. ``before()``: awaited first of all, for every AI call (the
    standalone workbench's sessions and window are taken over there: tools/handoff.py); a text it
    returns ends the call's answer. None: not wired."""

    def __init__(self, hold=None, after=None, note_state=None, session_of=None, types=None, external=None,
                 gate=None, gate_done=None, effects=None, late=None, refuse=None, before=None):
        self.before = before
        self.hold, self.after, self.note_state, self.session_of = hold, after, note_state, session_of
        self.types, self.external = types, external
        self.gate, self.gate_done, self.effects, self.late = gate, gate_done, effects, late
        self.refuse = refuse


class _Call:
    """The recorded call now running in this task (``annotate`` / ``each`` find it here), and
    its measurements (``probe``: a tools.probes.Probe, None for an Aggregate)."""
    __slots__ = ("name", "spec", "args", "scope", "notes", "probe")

    def __init__(self, name, spec, args, scope):
        self.name, self.spec, self.args, self.scope, self.notes = name, spec, args, scope, {}
        self.probe = None


# ---------------------------------------------------------------------------- registration
def make(mcp, manager, hooks: Hooks | None = None):
    """The ``tool()`` decorator factory for ``mcp``. ``manager``: the AspenPlusManager, or a
    function returning the current one (server.py's global, which may be replaced)."""
    from mcp.server.fastmcp import Context
    try:
        from mcp.types import ToolAnnotations
    except ImportError:                                     # an SDK without annotations
        ToolAnnotations = None
    with_ann = ToolAnnotations is not None and "annotations" in inspect.signature(mcp.add_tool).parameters
    get_manager = manager if callable(manager) and not hasattr(manager, "get_app") else (lambda: manager)
    hooks = hooks if hooks is not None else Hooks()

    def tool():
        def deco(fn):
            name = fn.__name__
            spec = TOOLS.get(name)
            if spec is None:
                raise RuntimeError(f"tool {name!r} is not classified: add its row to TOOLS in tools/intercept.py")
            sig = inspect.signature(fn, eval_str=True)
            params = list(sig.parameters.values())
            ctx_name = next((p.name for p in params if _is_ctx(p.annotation, Context)), None)
            if spec.reason:
                if "reason" in sig.parameters:
                    raise RuntimeError(f"tool {name!r} has its own `reason` parameter")
                at = next((i for i, p in enumerate(params) if p.kind is p.VAR_KEYWORD), len(params))
                params.insert(at, inspect.Parameter("reason", inspect.Parameter.KEYWORD_ONLY,
                                                    default=None, annotation=str | None))
            is_async = inspect.iscoroutinefunction(fn)

            @functools.wraps(fn)
            async def wrapper(**kw):
                return await _call(mcp, get_manager, hooks, spec, name, fn, is_async, ctx_name, kw)

            wrapper.__signature__ = sig.replace(parameters=params)     # its return annotation kept
            ann = {p.name: p.annotation for p in params if p.annotation is not p.empty}
            if sig.return_annotation is not sig.empty:
                ann["return"] = sig.return_annotation
            wrapper.__annotations__ = ann                              # FastMCP finds ctx through these
            if with_ann:
                mcp.add_tool(wrapper, annotations=ToolAnnotations(**spec.annotations()))
            else:
                mcp.add_tool(wrapper)
            REGISTERED.add(name)
            return fn
        return deco
    return tool


def _is_ctx(annotation, Context) -> bool:
    """FastMCP's own test (context_injection.find_context_parameter): Context, or a generic of it."""
    cands = [annotation, typing.get_origin(annotation), *typing.get_args(annotation)]
    return any(inspect.isclass(a) and issubclass(a, Context) for a in cands)


def verify(mcp) -> None:
    """Startup check: every registered tool went through ``tool()`` (so it is classified),
    every row of ``TOOLS`` is a registered tool, and the rows agree with each other
    (``table_problems``). RuntimeError otherwise."""
    have = {t.name for t in mcp._tool_manager.list_tools()}
    bypass, stale = sorted(have - REGISTERED), sorted(set(TOOLS) - have)
    problems = []
    if bypass:
        problems.append("registered with @mcp.tool() instead of intercept's @tool() (use it and add a "
                        f"row to TOOLS): {', '.join(bypass)}")
    if stale:
        problems.append(f"rows of TOOLS for tools that are not registered: {', '.join(stale)}")
    problems += table_problems()
    if problems:
        raise RuntimeError("tools/intercept.py: " + "; ".join(problems))


def table_problems(tools: dict | None = None) -> list[str]:
    """What is wrong in a classification table (``TOOLS``): a tool that changes the model in a
    way only a restore point takes back (undo ``checkpoint``) or whose inverse is a structural
    change (``inverse``) must say when its restore point is made (``cp``) -- a file tool
    excepted: it keeps its own (``patch_file(keep=True)``) or writes the file itself; ``cp``
    is "group", "call" or None, and a read has none. A destructive tool must say what the
    brakes do with it (``risk`` True, False or a condition's name, not None), so a
    new removal cannot slip past the confirmation cards."""
    out = []
    for name, s in (TOOLS if tools is None else tools).items():
        if s.destructive and s.risk is None:
            out.append(f"{name}: a destructive tool needs its brake decided: give its row risk=True (a "
                       "confirmation card), False (none: it keeps a backup) or a condition's name")
        if s.risk not in (None, True, False) and not isinstance(s.risk, str):
            out.append(f"{name}: risk must be True, False, None or a condition's name, not {s.risk!r}")
        if s.cp not in (None, "group", "call"):
            out.append(f"{name}: cp must be 'group', 'call' or None, not {s.cp!r}")
        elif s.cp is not None and s.kind == "read":
            out.append(f"{name}: a read makes no restore point (cp {s.cp!r})")
        elif s.cp is None and s.undo in ("checkpoint", "inverse") and s.kind != "file":
            out.append(f"{name}: undo {s.undo!r} needs a restore point before it: give its row cp='group'")
    return out


def stats(mcp) -> tuple[int, int, int]:
    """(registered, classified, taking ``reason``) for ``aspen-mcp --check``."""
    names = [t.name for t in mcp._tool_manager.list_tools()]
    done = [n for n in names if n in REGISTERED and n in TOOLS]
    return len(names), len(done), sum(TOOLS[n].reason for n in done)


def coverage() -> dict[str, list[str]]:
    """{undo kind: [tools]}: what can be taken back and how (the undo coverage note)."""
    out: dict[str, list[str]] = {}
    for name, spec in TOOLS.items():
        if spec.undo:
            out.setdefault(spec.undo, []).append(name)
    return out


# ---------------------------------------------------------------------------- per call
async def _call(mcp, get_manager, hooks, spec, name, fn, is_async, ctx_name, kw, by=None):
    """One tool call through the pipeline (the module docstring). ``by``: a late apply's _By
    (``replay``): the call runs as the user's -- no client hold, no brakes, no brief, the
    user's group, no writer wait."""
    reason = kw.pop("reason", None) if spec.reason else None
    t0 = _perf()
    ctx = kw.get(ctx_name) if ctx_name else None
    pre = None                                          # the before hook's line for the answer's end
    if by is None:
        _hold(mcp, hooks, ctx)
        if hooks is not None and hooks.before is not None:
            try:
                pre = await hooks.before()
            except Exception:
                logger.warning("the before-call hook failed", exc_info=True)
    reading = spec.kind == "read" or (spec.dry is not None and bool(kw.get(spec.dry)))
    session = _session(hooks, name, kw)
    early = None if reading or by is not None or hooks.refuse is None else _early(hooks, name, kw)
    gate = None if early is not None or reading or by is not None or hooks.gate is None else \
        _gate(mcp, get_manager, hooks, spec, name, fn, is_async, ctx_name, kw, ctx, reason, session)
    lv = None if early is not None or reading or by is not None or spec.kind not in _SPLITS or \
        (gate is not None and gate.need.what == "observe") else _learn(name, kw, reason, session)
    if (gate is None or not gate.acts) and not (lv is not None and lv.refuse):
        _external(get_manager, hooks, name, kw, session)     # Aspen-window edits journaled first
    news = _brief(get_manager, hooks, kw) if by is None else None     # what others changed, told when it ends well
    ntok = brief.CURRENT.set(news)
    cid = None if reading else journal.new_id("c")      # the journal's id of this call
    act = _begin(spec, name, kw, session, cid, by)
    status, handed = "error", False                     # handed: _run has the group the brakes took
    group = lgroup = None
    try:
        if early is not None:                           # the workspace refuses it, whatever the mode
            status = "refused"
            res = _refused(get_manager, name, kw, session, cid, reason, early, journal.GROUPS.current(),
                           why="workbench")
            return brief.deliver(news, res)
        if lv is not None and lv.refuse:                # learning mode wants the principle first
            status = "refused"                          # (in the group its retry joins; no COM touched)
            lgroup = _group(hooks, None, change=True)
            res = _refused(get_manager, name, kw, session, cid, reason, lv.text, lgroup, **lv.fields)
            return brief.deliver(news, res)
        if gate is not None and gate.acts:              # the brakes: before anything of the call's, COM included
            await gate.run(act, cid)
            group = gate.group
            _external(get_manager, hooks, name, kw, session)     # after the hold: the user's edits meanwhile
            if gate.answer is None and gate.since is not None:
                gate.changed(get_manager, news)
            if gate.answer is not None:
                status = "refused"
                res = _refused(get_manager, name, kw, session, cid, reason, gate.answer, group, gate=gate.fields)
                return brief.deliver(news, res)
        if not reading and spec.writer:                   # one writer per session at a time
            wait = 0.0 if by is not None else gate.writer_wait() if gate is not None else None
            held = await activity.wait_free(session, timeout=wait, act=act)
            if held is not None:
                status = "refused"
                if gate is not None:
                    gate.busy(held)
                res = _refuse(get_manager, name, kw, session, held, cid, reason, _perf() - t0, by=by, group=group)
                return brief.deliver(news, res)
            t0 = _perf()
        # a writer that yields to the loop while it works holds the session itself; a sync
        # tool needs no hold: nothing else runs until it returns
        mine = activity.hold(session, spec.writer, tool=name, algorithm=kw.get("algorithm"),
                             via="mcp" if by is None else by.via,
                             call=cid) if not reading and isinstance(spec.writer, str) else None
        try:
            handed = True                                   # _run ends it
            res = await _run(get_manager, hooks, spec, name, fn, is_async, kw, reading, session, cid, reason, t0,
                             group=group, by=by, gate=gate, fields=lv.fields if lv is not None else None)
        except BaseException as exc:
            _fault(get_manager, name, session, exc)
            if gate is not None:
                gate.failed(exc)
            raise
        finally:
            activity.release(mine)
        _fault(get_manager, name, session, res)
        status = "ok"
        if lv is not None and lv.note:                  # learning mode's reminder (weak "remind")
            res = _append(res, lv.note)
        if gate is not None:
            res = gate.after(res)
        if not reading and by is None and hooks.gate_done is not None:
            res = _gate_done(hooks, name, session, cid, res, dict(kw, reason=reason))
        if pre:
            res = _append(res, pre)
        return brief.deliver(news, res)
    finally:
        if gate is not None:
            gate.close()                                  # confirmed but not run (cancelled): the card reopens
            if gate.group is not None and not handed:     # refused, or cancelled while held
                journal.GROUPS.end()
        if lgroup is not None:
            journal.GROUPS.end()
        brief.CURRENT.reset(ntok)
        activity.end(act, status)


async def _run(get_manager, hooks, spec, name, fn, is_async, kw, reading, session, cid, reason, t0,
               group=None, by=None, gate=None, fields=None):
    """The call itself, in its group (``group``: the AI's the brakes took, ended here too; else
    taken here -- the user's for a late apply): restore point, recording scope, probes, the tool.
    ``fields``: more fields of its records (learning mode's ``reason_weak``)."""
    ai = by is None
    if group is None:
        group = _group(hooks, None if reading else reason, change=not reading and spec.kind in _SPLITS) if ai \
            else journal.GROUPS.user(session=session)
    cp = None
    if spec.cp is not None and not reading:            # a restore point first, a record of its own
        cp = _restore_point(get_manager, spec, name, session, group, cid, by)
        t0 = _perf()                                   # the call's ms is the tool's own time
    scope = None
    if not reading and spec.records and journal.enabled():
        scope = _open(get_manager, spec, name, kw, group, reason, cid, by, gate.fields if gate is not None else None,
                      fields)
    topo = [] if not reading and is_topo(spec, kw) else None       # the layout reminder: what it did, item by item (each)
    ttok = _ITEMS.set(topo) if topo is not None else None
    try:
        if scope is None:
            res = (await fn(**kw)) if is_async else fn(**kw)
        else:
            call = _Call(name, spec, kw, scope)
            call.probe = _probe(spec, name, kw, scope)
            tok = _CALL.set(call)
            try:
                res = (await fn(**kw)) if is_async else fn(**kw)
            except BaseException as exc:
                _failed(scope, name, kw, exc)
                raise
            else:
                if call.probe is not None:
                    call.probe.done(res)
                _settle(scope, t0, res)
            finally:
                _close(scope)
                _CALL.reset(tok)
        if cp and cp.get("note") and isinstance(res, str):     # none made: the AI is told, one line
            res = res.rstrip("\n") + "\n\n" + " ".join(str(cp["note"]).split())
        return _layout_due(get_manager, name, kw, session, group, res, topo) if ai else res
    finally:
        if ttok is not None:
            _ITEMS.reset(ttok)
        if group is not None and ai:
            journal.GROUPS.end()
        if hooks.after is not None:            # every call, reads too: the first one after a
            try:                               # /mcp reconnect takes the open window back
                hooks.after(session, None if reading else refresh_of(spec, kw))
            except Exception as exc:
                logger.warning("intercept: after-hook of %s failed (%r)", name, exc)


# Tools whose answers quote stored text (the journal, a program, an error shared, a snapshot):
# what they say is not what Aspen answered now, so it never flags a session.
_QUOTES = frozenset({"workbench_read", "workbench_edit", "open_workbench", "record_error", "diff_snapshot"})


def _fault(get_manager, name, session, what) -> None:
    """Aspen threw inside a COM call -- RPC_E_SERVERFAULT in the call's exception or answer: its
    session is flagged, and its runs refused until it is opened again (the manager's
    ``note_fault``; on Aspen V15 no run of it returns). Answers of ``_QUOTES`` are not read."""
    if name in _QUOTES and not isinstance(what, BaseException):
        return
    try:
        note = getattr(get_manager(), "note_fault", None)
        if note is not None:
            note(session, what, tool=name)
    except Exception as exc:
        logger.warning("intercept: fault check of %s failed (%r)", name, exc)


def _checked(manager, tool, session, fn):
    """``fn()``, its exception or answer looked at as ``_fault`` does."""
    try:
        res = fn()
    except BaseException as exc:
        _fault(lambda: manager, tool, session, exc)
        raise
    _fault(lambda: manager, tool, session, res)
    return res


def _hold(mcp, hooks, ctx) -> None:
    """Any tool call makes its client session the one Ask AI requests are pushed to."""
    if hooks.hold is None:
        return
    try:
        ctx = ctx if ctx is not None else mcp.get_context()
        if ctx.session is not None:
            hooks.hold(ctx)
    except Exception:              # no request (a direct call): nothing to hold
        pass


def _external(get_manager, hooks, name, kw, session) -> None:
    """Before the call: the session it works on (every open one when none) compared with what
    the server knows, what differs journaled as the user's in Aspen's window -- only reported,
    never waited on."""
    if hooks.external is None:
        return
    try:
        args = kw if session is None or kw.get("session_name") == session else {**kw, "session_name": session}
        hooks.external(get_manager(), name, args)
    except Exception as exc:
        logger.warning("intercept: Aspen-window check before %s failed (%r)", name, exc)


def _brief(get_manager, hooks, kw):
    """The brief of this call (tools/brief.py): the model of its ``session_name``, else every open session's."""
    try:
        return brief.Pending(get_manager, kw.get("session_name"), hooks.types)
    except Exception as exc:
        logger.warning("intercept: no brief (%r)", exc)
        return None


def _session(hooks, name, kw):
    """The session a call works on: its ``session_name``, else what ``hooks.session_of`` finds."""
    s = kw.get("session_name")
    if s is None and hooks.session_of is not None:
        try:
            s = hooks.session_of(name, kw)
        except Exception as exc:
            logger.warning("intercept: session_of %s failed (%r)", name, exc)
    return s


def _begin(spec, name, kw, session, call, by=None):
    """The call, in flight (tools/activity.py: the window's activity bar)."""
    try:
        return activity.begin("ai" if by is None else by.actor, name, session=session, phase=spec.phase,
                              target=target_of(name, kw), call=call, via="mcp" if by is None else by.via)
    except Exception as exc:
        logger.warning("intercept: activity of %s not shown (%r)", name, exc)
        return None


def _refuse(get_manager, name, kw, session, held, call, reason, waited, by=None, group=None) -> str:
    """The answer to a changing call its session's holder kept out, and the call's
    ``refused`` record, in the AI's group without joining it (a refused call does not count
    as the AI's activity for the group's idle time) -- the group the brakes took, if they did;
    a late apply's in the user's."""
    text = activity.refusal(held)
    who = {k: held[k] for k in ("actor", "tab", "title", "via", "tool", "algorithm", "since", "paused", "paused_n",
                                "waiting_user", "wait_sid") if k in held}
    if group is None:
        group = journal.GROUPS.current() if by is None else journal.GROUPS.user(session=session)
    return _refused(get_manager, name, kw, session or held.get("session"), call, reason, text, group, by=by,
                    holder=who, waited=round(waited, 2))


def _learn(name, kw, reason, session):
    """Learning mode's verdict on a changing AI call (tools/learn.check): None, or refuse / mark
    it. The grace of a weak reason is per tool and target (its session's). Off: one cached look."""
    if not learn.on():
        return None
    try:
        key = json.dumps([session, target_of(name, kw)], sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        key = str(session)
    return learn.check(reason, name, key)


def _early(hooks, name, kw) -> str | None:
    """Hooks.refuse's answer for this call (None: it goes on); a failing hook refuses nothing."""
    try:
        return hooks.refuse(name, kw)
    except Exception as exc:
        logger.warning("intercept: refuse-hook of %s failed (%r)", name, exc)
        return None


def _refused(get_manager, name, kw, session, call, reason, text, group, by=None, **fields) -> str:
    """A call that did not run: its ``refused`` record (``fields``: why -- the session's holder, the
    brakes' ``gate``) in ``group``, and ``text``, the answer. No session, no model: no record."""
    if not journal.enabled():
        return text
    try:
        m = get_manager()
        model = m.model_id(session) if session else None
        if model:
            with recorder.scope(actor="ai" if by is None else by.actor, via="mcp" if by is None else by.via,
                                session=session, model=model, group=group, call=call, tool=name, reason=reason) as s:
                s.manager = m
                s.add("call", status="refused", result=text[:journal.RESULT_MAX], target=target_of(name, kw),
                      args=args_summary(kw), **fields)
    except Exception as exc:
        logger.warning("intercept: refused record of %s lost (%r)", name, exc)
    return text


_SPLITS = frozenset({"value", "structure", "batch"})   # a call of these kinds changes the model


def _group(hooks, reason, change=False):
    """The AI's change group for this call (journal.GROUPS.ai); ``change``: the call changes the
    model, so it may open the diagnose group a failed run left waiting."""
    try:
        note = hooks.note_state() if hooks.note_state is not None else None
    except Exception as exc:
        logger.warning("intercept: note_state failed (%r)", exc)
        note = None
    return journal.GROUPS.ai(note=note, reason=reason, change=change)


_CP_REASON = {"group": "before-structure", "call": "before-optimize", "close_aspen_plus": "before-close"}
_CP_FAILED = ("(No restore point was made before this change: it could not be saved. The user can save one "
              "from the workbench.)")
_CP_SLOW: dict = {}                    # (model, group id) -> est_s: its restore point was too slow (told once)


def _restore_point(get_manager, spec, name, session, group, call, by=None) -> dict | None:
    """``Spec.cp``: a restore point of the call's session before the call -- "group":
    before its change group's first structural change (the group's later ones reuse it; one
    that was too slow to make is not tried again in that group, the AI told once), "call":
    before each optimization, each close (none while the model is its file: "before-close").
    None when the call names no open session. ``by``: a late
    apply's -- the user's, its ``extra`` on the record, a slow Export allowed when they asked."""
    try:
        m = get_manager()
        if not session or m.get_app(session) is None:
            return None
        gid = group.get("id") if isinstance(group, dict) else group
        key = (m.model_id(session), gid) if spec.cp == "group" and gid else None
    except Exception:
        return None
    slow = by is not None and by.allow_slow
    if key is not None and key in _CP_SLOW and not slow:
        return None
    # an optimization's begin record counts as ended by any change record of its call (journal.page,
    # the timeline): its restore point gets a call id of its own
    who = {} if by is None else {"actor": by.actor, "via": by.via, "allow_slow": slow, **(by.extra or {})}
    rp = restore_point(m, session, _CP_REASON.get(name) or _CP_REASON[spec.cp], group=group,
                       dedup=spec.cp == "group", **{"actor": "ai", "via": "mcp", **who}, tool=name,
                       call=journal.new_id("c") if spec.probe == "sum" else call)
    if key is not None and rp.get("why") == "slow":
        _CP_SLOW[key] = rp.get("est_s")
        while len(_CP_SLOW) > 256:
            _CP_SLOW.pop(next(iter(_CP_SLOW)))
    return rp


def restore_point(manager, session: str, reason: str, *, group=None, dedup: bool = True,
                  name: str | None = None, actor: str = "ai", via: str | None = "mcp",
                  tool: str | None = None, call: str | None = None, allow_slow: bool = False,
                  **extra) -> dict:
    """A restore point of ``session``'s model (tools/restore_points.ensure; with ``name`` a
    named one, kept for good: ``make``) in a recording scope of its own -- the caller's
    ``call`` id and change ``group`` (a dict or its id), no reason -- so it is a record of its
    own, ahead of the call's: the timeline's milestone. ``dedup``: one per (model, group);
    ``allow_slow``: an Export however long it takes (the user asked for it: before a restore);
    ``extra``: fields of the record (a program statement's ``sid``). A failure ensure could not
    journal itself is journaled here. Returns ensure's dict -- its ``note`` the line for the AI
    when none was made; never raises."""
    gid = group.get("id") if isinstance(group, dict) else group
    try:
        with recorder.scope(actor=actor, via=via, session=session, model=manager.model_id(session), group=gid,
                            call=call, tool=tool, **extra) as s:
            s.manager = manager
            if name is not None:
                rp = restore_points.make(manager, session, name, actor=actor, via=via, tool=tool or "checkpoint",
                                         group=gid)
            else:
                rp = restore_points.ensure(manager, session, reason, group=gid if dedup else None, actor=actor,
                                           via=via, tool=tool, allow_slow=allow_slow)
            if rp.get("status") == "failed" and "tier" not in rp:      # ensure's own failure: not journaled
                s.add("checkpoint", status="skipped", why="failed", cp_reason=reason,
                      result=str(rp.get("error") or "")[:journal.RESULT_MAX])
            return rp
    except Exception as exc:
        logger.warning("intercept: restore point of %s before %s failed (%r)", session, tool, exc)
        return {"status": "failed", "why": "failed", "error": str(exc), "note": _CP_FAILED}


def measured(manager, scope, tool: str, args: dict, fn, *, spec: Spec | None = None, actor: str = "program",
             via: str | None = "window", **extra) -> tuple:
    """``fn()`` -- the implementation of tool ``tool`` (flowsheet_tools.place_block ...), called
    with ``args`` in the MCP tool's single-call names (session_name, block_name ...) -- measured
    as ``_run`` measures that tool, for a caller with a recording ``scope`` of its own (a block
    program's statement): first the restore point its row's ``cp`` asks for, in the
    scope's change group -- once per group (``_restore_point``; ``actor`` / ``via`` / ``extra``,
    e.g. the statement's ``sid``, on its record) -- then the same probes.Probe (before, after, at
    least one record), the scope's ``tool`` set to ``tool`` and flushed before it is put back: its
    records are the MCP call's (op, target, tool, ms) but for the scope's own actor, via and
    fields. A tool that raises gets its ``error`` record and the exception goes on; an internal
    fault of Aspen's in either flags the session (``_fault``). ``spec``: the row to measure by
    when not ``tool``'s own. The window's refresh stays the caller's (``refresh_of``). Returns
    (the tool's answer, the restore point's dict -- ``note`` / ``why`` when none was made -- or
    None). Without a scope or with the journal off: the restore point and ``fn()`` only."""
    spec = spec if spec is not None else TOOLS[tool]
    session = (args or {}).get("session_name")
    rp = None
    if spec.cp is not None:
        rp = _restore_point(lambda: manager, spec, tool, session, getattr(scope, "group", None),
                            getattr(scope, "call", None), _By(actor, via, extra or None))
    if scope is None or not getattr(scope, "on", False):
        return _checked(manager, tool, session, fn), rp
    was, t0 = scope.tool, _perf()
    scope.tool = tool
    try:
        p = _probe(spec, tool, args, scope)
        try:
            res = _checked(manager, tool, session, fn)
        except BaseException as exc:
            _failed(scope, tool, args, exc)
            raise
        if p is not None:
            p.done(res)
        return res, rp
    finally:
        try:
            scope.flush(ms=(_perf() - t0) * 1e3)
        except Exception as exc:
            logger.warning("intercept: records of %s lost (%r)", tool, exc)
        scope.tool = was


def _open(get_manager, spec, name, kw, group, reason, call=None, by=None, gate=None, fields=None):
    """The call's recording scope, entered; None if it cannot be had (the call runs unrecorded).
    ``by``: a late apply's (the user's, its ``extra`` on every record); ``gate``: the brakes'
    field of the call's records (confirmed, allowed for the group, the window not live);
    ``fields``: more fields of every record."""
    try:
        m, session = get_manager(), kw.get("session_name")
        model = m.model_id(session) if session else None
        extra = dict(by.extra or {}) if by is not None else {}
        if gate:
            extra["gate"] = gate
        if fields:
            extra.update(fields)
        via = "mcp" if by is None else by.via
        if spec.probe == "sum":            # its begin record, written on entering, says what it will do
            s = recorder.Aggregate(do=name, actor="optimizer", via=via, session=session, model=model,
                                   group=group, call=call, tool=name, reason=reason, **extra)
            s.begin = {"target": target_of(name, kw), "args": args_summary(kw)}
        else:
            s = recorder.scope(actor="ai" if by is None else by.actor, via=via, session=session, model=model,
                               group=group, call=call, tool=name, reason=reason, **extra)
        s.manager = m
        return s.__enter__()
    except Exception as exc:
        logger.warning("intercept: no recording scope for %s (%r)", name, exc)
        return None


def _probe(spec, name, kw, scope):
    """The call's measurements (tools/probes.py), taken before it runs -- or, for a batch,
    before each item (``each``). None for an Aggregate, whose summary is the record."""
    if isinstance(scope, recorder.Aggregate):
        return None
    try:
        batch = spec.items if spec.items and kw.get(spec.items) else None
        p = probes.Probe(scope.manager, scope, name, spec.probe, kw, batch=batch, fallback=spec.kind != "config",
                         describe=lambda a: (target_of(name, a), args_summary(a)))
        if batch is None:
            p.before()
        return p
    except Exception as exc:
        logger.warning("intercept: %s not measured (%r)", name, exc)
        return None


def _failed(scope, name, kw, exc) -> None:
    """The tool raised: an ``error`` record with its message."""
    try:
        text = str(exc) or type(exc).__name__
        text = text if len(text) <= journal.RESULT_MAX else text[:journal.RESULT_MAX]
        if isinstance(scope, recorder.Aggregate):
            scope.extra["result"], scope.status = text, "error"
        scope.add("call", status="error", result=text, target=target_of(name, kw), args=args_summary(kw))
    except Exception as e:
        logger.warning("intercept: error record of %s lost (%r)", name, e)


def _settle(scope, t0, res) -> None:
    """What the tool handed to ``annotate``: an Aggregate's report, else fields of the last
    record. An Aggregate whose tool answered "Error..." (it did not run) is ``failed``."""
    try:
        if isinstance(scope, recorder.Aggregate) and str(res or "").lstrip().startswith("Error"):
            scope.extra["result"], scope.status = str(res).strip()[:journal.RESULT_MAX], "failed"
        c = _CALL.get()
        if c is None or not c.notes:
            return
        notes = dict(c.notes)
        if isinstance(scope, recorder.Aggregate):
            if "report" in notes:
                scope.report = notes.pop("report")
            scope.extra.update(journal.clean({k: v for k, v in notes.items() if v is not None}))
        else:
            scope.flush(ms=(_perf() - t0) * 1e3, **notes)
    except Exception as exc:
        logger.warning("intercept: annotations lost (%r)", exc)


def _close(scope) -> None:
    try:
        scope.__exit__(None, None, None)
    except Exception as exc:
        logger.warning("intercept: closing the recording scope failed (%r)", exc)


def annotate(**fields) -> None:
    """From inside a tool: something only the tool knows, for the call's record (the MCP
    optimize: ``report=``). Nothing outside a recorded call."""
    c = _CALL.get()
    if c is not None:
        c.notes.update(fields)


def each(items, fn) -> str:
    """A batch parameter's loop: ``fn(item)`` for each, results joined with newlines exactly as
    the loops in server.py always did. While item k runs, the call's records are numbered k,
    and the call's probe measures that item alone (a failed item gets its own record)."""
    s = recorder.current()
    c = _CALL.get()
    p = c.probe if c is not None and s is not None and c.scope is s else None
    done = _ITEMS.get()
    out = []
    try:
        for k, item in enumerate(items):
            if s is not None:
                s.item = k
            a = p.enter(item) if p is not None else None
            out.append(fn(item))
            if p is not None:
                p.leave(a, out[-1])
            if done is not None:
                done.append((item, out[-1]))
    finally:
        if s is not None:
            s.item = None
    return "\n".join(out)


# ---------------------------------------------------------------------------- the brakes
_mono = time.monotonic          # the brakes' wall clock (budgets, waits); kept as a module attribute so it can be overridden
POLL_S = 0.5                    # a held call looks this often whether the window is still live
LATE_DELAY_S = 0.3              # a late apply starts this long after it is due: the AI's answer goes out first
PENDING_MAX = 64
PENDING: dict = {}              # card id -> Pending: the call a card runs when the user approves it late
_RUNNING: set = set()           # cards whose call runs now (confirmed inside the AI's call, or late): not again
_WHY = {"decline": "declined", "late": "late", "timeout": "timeout", "window_closed": "window_closed",
        "expired": "expired", "joined": "joined"}


class Budget:
    """One changing call's wall-clock budget from its arrival: the hold and the writer
    wait share ``hold`` seconds (brake.hold_s of the client); once past ``safe`` nothing is
    applied inside the call any more (an approval then runs late). Measured on the clock each
    time -- a sync job that stopped the loop meanwhile counts."""
    __slots__ = ("t0", "hold", "safe")

    def __init__(self, client=None):
        self.t0, self.hold, self.safe = _mono(), brake.hold_s(client), brake.safe_s(client)

    def elapsed(self) -> float:
        return _mono() - self.t0

    def left(self) -> float:
        return max(0.0, self.hold - self.elapsed())

    def in_time(self, more: float = 0.0) -> bool:
        """Still time to apply inside the call: elapsed + ``more`` (a restore point's) + 3 s <= safe."""
        return self.elapsed() + float(more or 0) + 3.0 <= self.safe


@dataclass
class Pending:
    """A card's call as it came, kept to run later (``late``); memory only -- after a restart
    the card expires (brake.Brake's store)."""
    pipe: tuple                 # (mcp, get_manager, hooks)
    spec: Spec
    name: str
    fn: object
    is_async: bool
    ctx_name: str | None
    kw: dict
    reason: str | None
    session: str | None
    model: str | None
    call: str | None
    group: str | None


@dataclass
class _By:
    """Who runs a call that is not the AI's request of the moment: a late apply (``replay``)."""
    actor: str = "user"
    via: str | None = "window"
    extra: dict | None = None
    allow_slow: bool = False


def _gate(mcp, get_manager, hooks, spec, name, fn, is_async, ctx_name, kw, ctx, reason, session):
    """The brakes' first look at a changing AI call (brake.need, no group yet): a _Gate, or None
    -- no workspace, or nothing to hold and nothing to record (the common case: a few us)."""
    try:
        brk = hooks.gate()
        if brk is None:
            return None
        n = brk.need(spec, name, kw, None)
    except Exception as exc:
        logger.warning("intercept: the brakes of %s not consulted (%r)", name, exc)
        return None
    if n.what == "pass" and not n.fallback:
        return None
    client = None
    if n.what != "pass":
        client = _client_of(mcp, ctx)
        if client and getattr(brk, "client", None) != client:
            brk.client = client
    return _Gate(brk, n, (mcp, get_manager, hooks), spec, name, fn, is_async, ctx_name, kw, reason, session,
                 client)


class _Gate:
    """One changing AI call and the brakes. ``need``: brake.need's first verdict;
    ``acts``: it holds or refuses (else only ``fields``: the window is not live, for its records).
    ``run`` takes the AI's group and acts -- Observe refuses, a pause holds (a resume judges
    the call again), a risky call waits on a card -- leaving ``answer`` (not applied: what the
    AI is told, ``fields`` its refused record's ``gate``) or, to apply it: ``fields`` (its
    records' ``gate``), ``note`` (the answer's last line), ``card`` (live-applied: ``after``
    settles it), ``since`` (resumed: the time its hold began -- ``changed`` then)."""

    def __init__(self, brk, need, pipe, spec, name, fn, is_async, ctx_name, kw, reason, session, client):
        self.brk, self.need, self.pipe, self.spec, self.name = brk, need, pipe, spec, name
        self.fn, self.is_async, self.ctx_name, self.kw, self.reason = fn, is_async, ctx_name, kw, reason
        self.session, self.client = session, client
        self.acts = need.what != "pass"
        self.budget = Budget(client) if self.acts else None
        self.fields = {"mode": need.mode, "fallback": need.fallback} if need.fallback else None
        self.group = self.answer = self.note = self.card = self.since = self.cid = None
        self.held = 0.0

    # -- the wait
    async def run(self, act, cid) -> None:
        brk, spec, name, kw = self.brk, self.spec, self.name, self.kw
        self.cid, self.group = cid, _group(self.pipe[2], self.reason, change=spec.kind in _SPLITS)
        n = brk.need(spec, name, kw, self.group)          # with its group: a class the user let through?
        for _ in range(16):
            if n.what == "observe":
                brk.note_refused()
                return self._refuse(brake.text("observe"), "observe")
            if n.what == "pause":
                if not await self._pause(act):
                    return None
                n = brk.need(spec, name, kw, self.group)  # resumed: judged again (the mode may have changed)
                continue
            if n.what == "card":
                return await self._card(act, n)
            if n.allowed:
                self.fields = {"allowed": n.allowed}
            elif n.fallback:
                self.fields = {"mode": n.mode, "fallback": n.fallback}
            if self.since is not None:
                self.note = brake.text("resumed", s=max(1, round(self.held)))
                self.fields = {**(self.fields or {}), "resumed": True, "held_s": round(self.held, 1)}
            return None
        return self._refuse(brake.paused_text(brk.paused or {}), "paused")

    async def _pause(self, act) -> bool:
        """Held while paused -- one hold per pause: every call until its deadline waits, a later
        one is refused at once. True: resumed in time."""
        brk = self.brk
        p = dict(brk.paused or {})
        why = "stuck" if p.get("by") == "stuck" else "paused"
        deadline = brk.pause_deadline(self.budget.hold)
        rest = (deadline - brk.now()) if deadline is not None else 0.0
        if rest <= 0:
            self._refuse(brake.paused_text(p, past=True), why)
            return False
        e = brk.hold(call=self.cid, tool=self.name, session=self.session, target=target_of(self.name, self.kw))
        t, since = _mono(), time.time()
        was = activity.phase(act, "wait", why="pause")
        try:
            r = await _wait(brk, "pause", min(rest, self.budget.left()))
        finally:
            self.held += _mono() - t
            brk.unhold(e)
            activity.phase(act, was, why=False)
        if r == "resume":
            if self.budget.in_time():
                self.since = since if self.since is None else self.since
                return True
            self._refuse(brake.text("resumed_late", s=round(self.held)), "late")
            return False
        self._refuse(brake.paused_text(p), "window_closed" if r == "window_closed" else why)
        return False

    async def _card(self, act, n) -> None:
        """A risky call: a card (the same action's, if one waits already), then its wait."""
        brk, name, kw, session = self.brk, self.name, self.kw, self.session
        _, get_manager, hooks = self.pipe
        model = _model_of(get_manager, session)
        card, how = brk.card(name, kw, session=session, model=model, group=self.group, call=self.cid,
                             target=target_of(name, kw), args=args_summary(kw), cls=n.cls, reason=self.reason,
                             hold=self.budget.left(), **_facts(hooks, name, kw, session, n.cond))
        cid = card["id"]
        if how == "timeout":                            # its card is open, its wait over: not again
            return self._refuse(brake.card_text("dup", card), "dup", card=cid)
        if how == "new":
            _keep(cid, Pending(self.pipe, self.spec, name, self.fn, self.is_async, self.ctx_name,
                               {k: v for k, v in kw.items() if k != self.ctx_name}, self.reason, session, model,
                               self.cid, _gid(self.group)))
        t = _mono()
        was = activity.phase(act, "wait", why="card", card=cid)
        try:
            r = await _wait(brk, cid, self.budget.left())
        except BaseException:                           # the client cancelled: the card stays open
            brk.settle(cid, "cancelled")
            raise
        finally:
            self.held += _mono() - t
            activity.phase(act, was, why=False, card=False)
        cp_s = _cp_s(card)
        if r == "apply":
            if self.budget.in_time(cp_s):
                _RUNNING.add(cid)
                self.since = None                       # the user saw it after the pause: their approval stands
                self.card, self.note = cid, brake.text("confirmed", id=cid)
                self.fields = {"card": cid, "confirmed": "user", "held_s": round(self.held, 1)}
                return None
            brk.late(cid)                               # no time left inside this call: right after it
            late(brk, cid)
            r = "late"
        elif r == "late":                               # "restore point first": always after the answer
            late(brk, cid, allow_slow=True)
        elif r in ("timeout", "window_closed"):
            brk.settle(cid, "timeout", closed=True if r == "window_closed" else None)
        elif r in ("decline", "expired"):
            PENDING.pop(cid, None)
        comment = (card.get("decided") or {}).get("comment") if r == "decline" else None
        return self._refuse(brake.card_text(r, card, cp_s=cp_s), _WHY.get(r, r), card=cid, comment=comment)

    def _refuse(self, text, why, **fields) -> None:
        g = {"why": why, "mode": self.brk.mode}
        if self.held:
            g["held_s"] = round(self.held, 1)
        g.update({k: v for k, v in fields.items() if v is not None})
        self.answer, self.fields, self.note = text, g, None

    # -- after the wait
    def writer_wait(self) -> float | None:
        """The session-writer wait, from what is left of the budget once the call was held."""
        return min(activity.WRITER_WAIT_S, self.budget.left()) if self.acts else None

    def changed(self, get_manager, news) -> None:
        """A call resumed after a pause: someone else changed its model meanwhile -> not applied,
        what changed below (the brief, its cursors moved as if attached)."""
        if not _changed_since(get_manager, self.session, self.since):
            return
        lines = []
        if news is not None:
            try:
                lines, news.taken = news.make(), True
            except Exception as exc:
                logger.warning("intercept: brief of a resumed call lost (%r)", exc)
        text = brake.text("resumed_changed") + ("\n" + "\n".join(lines) if lines else "")
        self._refuse(text, "changed")

    def busy(self, held) -> None:
        """The writer wait refused the call after the user confirmed its card: the card opens again (its
        Pending kept), saying who holds the session -- the user applies it once that ended."""
        self._reopen(busy=_busy(held))

    def close(self) -> None:
        """The call ended without running after the user confirmed its card (cancelled while
        waiting for its session's writer): the card opens again, its Pending kept."""
        self._reopen()

    def _reopen(self, **fields) -> None:
        if self.card is not None:
            cid, self.card = self.card, None
            _RUNNING.discard(cid)
            self.brk.settle(cid, "timeout", **fields)

    def failed(self, exc) -> None:
        self._done(False, str(exc) or type(exc).__name__)

    def after(self, res):
        """The call ran: a live-applied card is applied / failed with its answer, the note last."""
        self._done(not _failed_res(res), _text(res))
        return _append(res, self.note)

    def _done(self, ok, text) -> None:
        if self.card is not None:
            cid, self.card = self.card, None
            _RUNNING.discard(cid)
            PENDING.pop(cid, None)
            self.brk.done(cid, ok, text)


async def _wait(brk, key, seconds) -> str:
    """Wait on the event loop for ``key``'s decision (a card id, or "pause"): what the Brake
    hands its waiter (apply, late, joined, decline, resume, expired, window_closed), "timeout"
    after ``seconds`` of wall clock, "window_closed" once the window is not live. Only an
    await on a Future: the loop -- the window's sync loop, its jobs, the beacon -- runs on, and
    the call has touched no COM yet."""
    loop = asyncio.get_running_loop()
    fut = loop.create_future()

    def put(result):
        if not fut.done():
            fut.set_result(result)

    def decided(result):                       # the Brake's waiter; the loop's thread, else handed to it
        try:
            here = asyncio.get_running_loop() is loop
        except RuntimeError:
            here = False
        put(result) if here else loop.call_soon_threadsafe(put, result)

    tok = brk.wait_on(key, decided)
    end = _mono() + max(0.0, float(seconds))
    try:
        while not fut.done():
            rest = end - _mono()
            if rest <= 0:
                return "timeout"
            if not brk.live():
                return "window_closed"
            await asyncio.wait((fut,), timeout=min(POLL_S, rest))
        return fut.result()
    finally:
        brk.unwait(tok)


def late(brk, cid, allow_slow: bool = False, delay: float | None = None):
    """Run card ``cid``'s call now the user approved it outside its call's wait -- after a
    timeout, the window closing, the client's cancel, with no time left in the call, or
    "restore point first" (``allow_slow``): its Pending replayed as the user's ("AI proposed,
    you executed"), the card then applied / failed with the answer. First: the card applying
    and its Pending here (a restart lost it: expired), its session still on the same model
    (else expired), no writer holding the session (a program, an optimize: the card opens
    again with ``busy`` -- nothing waits here). Returns the asyncio Task, or None. A card runs
    once: None for a card whose call runs already. On the event loop's thread (the
    workbench's sync loop)."""
    c = brk.get(cid)
    if c is None or c.get("status") != "applying" or cid in _RUNNING:
        return None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("intercept: late apply of card #%s asked for outside the event loop", cid)
        return None
    p = PENDING.get(cid)
    if p is None:
        brk.settle(cid, "expired", why="restart")
        return None
    try:
        if p.session and _model_of(p.pipe[1], p.session) != p.model:
            PENDING.pop(cid, None)
            brk.settle(cid, "expired", why="session")
            return None
    except Exception:
        pass
    held = activity.holder(p.session) if p.spec.writer else None
    if held is not None:
        brk.settle(cid, "timeout", busy=_busy(held))
        return None
    PENDING.pop(cid, None)
    c.pop("busy", None)
    _RUNNING.add(cid)
    own = _late_own(brk, cid, p)
    if own is not None:
        return own
    return loop.create_task(_late(brk, cid, p, allow_slow, LATE_DELAY_S if delay is None else delay))


def _late_own(brk, cid, p):
    """hooks.late's answer for card ``cid``: an awaitable when the workspace runs it its own way."""
    hook = getattr(p.pipe[2], "late", None)
    if hook is None:
        return None
    try:
        return hook(brk, cid, p)
    except Exception as exc:
        logger.warning("intercept: the workspace's late apply of card #%s failed (%r)", cid, exc)
        return None


def late_done(brk, cid, ok, text=None, **fields) -> None:
    """A late apply hooks.late took (a queued program run) ended: the card applied / failed --
    ``ok`` None: it never started (stopped, its tab closed), the card open again (``fields``)."""
    _RUNNING.discard(cid)
    if ok is None:
        brk.settle(cid, "timeout", **fields)
    else:
        brk.done(cid, ok, text)


async def _late(brk, cid, p, allow_slow, delay):
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        c = brk.get(cid) or {}
        proposed = {"by": "ai", "card": cid, "call": p.call, "group": p.group, "t": c.get("t")}
        try:
            res = await replay(p, extra={"proposed": proposed}, allow_slow=allow_slow)
        except Exception as exc:
            logger.warning("intercept: late apply of card #%s (%s) failed (%r)", cid, p.name, exc)
            brk.done(cid, False, str(exc) or type(exc).__name__)
            return None
        brk.done(cid, not _failed_res(res), _text(res))
        return res
    finally:
        _RUNNING.discard(cid)


async def replay(p: Pending, *, actor: str = "user", via: str | None = "window", extra: dict | None = None,
                 allow_slow: bool = False):
    """``p``'s call again, later, through the same pipeline (``_call``) as ``actor`` / ``via``:
    no brakes, no client hold, no brief; its restore point, probes, records (``extra`` on
    each: ``proposed``), the window's refresh as for any call. The tool's answer."""
    mcp, get_manager, hooks = p.pipe
    kw = dict(p.kw)
    if p.spec.reason and p.reason is not None:
        kw["reason"] = p.reason
    return await _call(mcp, get_manager, hooks, p.spec, p.name, p.fn, p.is_async, p.ctx_name, kw,
                       by=_By(actor, via, extra, allow_slow))


def _keep(cid, p: Pending) -> None:
    PENDING[cid] = p
    while len(PENDING) > PENDING_MAX:
        PENDING.pop(next(iter(PENDING)))


def _changed_since(get_manager, session, since) -> bool:
    """Someone other than this AI changed ``session``'s model (None: any open one's) after
    ``since``: a record tools/brief.py would tell -- the user's inputs and runs, a program's,
    Aspen's own window's, another AI session's (not milestones such as a pause): the brief's
    ``collect(since=)``. The journal off: never (the call applies)."""
    if since is None or not journal.enabled():
        return False
    try:
        return bool(brief.collect(get_manager(), session, since=since)[0])
    except Exception as exc:
        logger.warning("intercept: changes while paused not read (%r)", exc)
    return False


def _client_of(mcp, ctx) -> str | None:
    """The MCP client's clientInfo.name (claude-code, codex-mcp-client), None unknown."""
    try:
        ctx = ctx if ctx is not None else mcp.get_context()
        return getattr(ctx.session.client_params.clientInfo, "name", None)
    except Exception:
        return None


def _facts(hooks, name, kw, session, cond) -> dict:
    """What a card shows beyond the call (hooks.effects: tools/brake_effects), {} when unwired."""
    if hooks.effects is None:
        return {}
    try:
        f = hooks.effects(name, kw, session, cond) or {}
        return {k: f[k] for k in ("risky", "more", "effects", "cp") if k in f}
    except Exception as exc:
        logger.warning("intercept: a card's effects for %s not known (%r)", name, exc)
        return {}


def _model_of(get_manager, session):
    try:
        return get_manager().model_id(session) if session else None
    except Exception:
        return None


def _cp_s(card) -> float:
    cp = (card or {}).get("cp")
    try:
        return float(cp.get("est_s") or 0) if isinstance(cp, dict) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _busy(held) -> dict:
    return {**{k: held[k] for k in ("actor", "tab", "title", "tool", "since") if k in held},
            "text": activity.refusal(held)}


def _gid(group):
    return group.get("id") if isinstance(group, dict) else group


def _failed_res(res) -> bool:
    return isinstance(res, str) and probes.failed(res)


def _text(res) -> str:
    return res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, default=str)


def _gate_done(hooks, name, session, cid, res, kw=None):
    """hooks.gate_done's line (the stuck detector's note) at the end of a changing AI call's answer;
    ``kw``, the call's arguments, lets it note what the call did (the AI's own table rows, a
    workbench session's gap steps)."""
    try:
        return _append(res, hooks.gate_done(name, session, cid, res, kw=kw))
    except Exception as exc:
        logger.warning("intercept: gate_done after %s failed (%r)", name, exc)
        return res


def _append(res, note):
    """``note`` as the answer's last line -- in a JSON object answer, under "workbench_note"."""
    if not note or not isinstance(res, str):
        return res
    body = res.rstrip()
    if body.startswith("{") and body.endswith("}"):
        try:
            obj = json.loads(body)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            sep = "," if obj else ""
            return body[:-1].rstrip() + f"{sep}\n \"workbench_note\": {json.dumps(note, ensure_ascii=False)}\n}}"
    return res.rstrip("\n") + "\n\n" + note


# ---------------------------------------------------------------------------- call facts
def target_of(tool, args) -> dict | None:
    """What a call works on, for a record or the activity bar: the path (labelled), the first of
    a batch plus its size, the block / stream / component / reaction set / file / algorithm."""
    a = args or {}
    t = {}
    if a.get("aspen_path"):
        t = journal.label(a["aspen_path"])
    for key, sub in (("items", "path"), ("paths", None), ("blocks", "name"), ("streams", "name"),
                     ("connections", "stream"), ("components", None), ("variables", "aspen_path")):
        seq = a.get(key)
        if isinstance(seq, list) and seq:
            first = seq[0].get(sub) if sub and isinstance(seq[0], dict) else (seq[0] if sub is None else None)
            if not t and first is not None:
                t = journal.label(first) if key in ("items", "paths", "variables") else {"name": str(first)}
            t["n"] = len(seq)
            break
    for key, field in (("block_name", "block"), ("stream_name", "stream"), ("component_id", "component"),
                       ("reaction_set_name", "rxnset"), ("algorithm", "algorithm"), ("tab", "tab")):
        if a.get(key) is not None and field not in t:
            t[field] = str(a[key])
    if a.get("file_path"):
        t["file"] = re.split(r"[\\/]", str(a["file_path"]))[-1]
    return t or None


def args_summary(args) -> dict | None:
    """The arguments a call was given (None left out), JSON-safe, at most ARGS_MAX bytes."""
    try:
        a = journal.clean({k: v for k, v in (args or {}).items()
                           if v is not None and not type(v).__module__.startswith("mcp.")})   # not ctx
        text = json.dumps(a, ensure_ascii=False)
        return a if len(text.encode("utf-8")) <= ARGS_MAX else {"trunc": True, "text": text[:ARGS_MAX // 2]}
    except Exception:
        return None


_TOPO = (r"\data\blocks", r"\data\streams")


def _topo_path(path) -> bool:
    p = str(path or "").rstrip("\\").casefold()
    return p in _TOPO or re.search(r"\\ports\\[^\\]+$", p) is not None


def refresh_of(spec: Spec, args) -> str | None:
    """What the window re-reads after the call: ``topology*`` is topology only for
    ``\\Data\\Blocks``, ``\\Data\\Streams`` or a ``\\Ports\\<port>`` path, else values."""
    if spec.refresh == "topology*":
        return "topology" if _topo_path((args or {}).get("aspen_path")) else "values"
    return spec.refresh


def is_topo(spec: Spec, args) -> bool:
    """The call changes what the flowsheet drawing shows (the layout reminder)."""
    return spec.topo is True or (spec.topo == "path" and _topo_path((args or {}).get("aspen_path")))


# ---------------------------------------------------------------------------- layout reminder
# session -> {"model", "group": the AI's group of its latest topology change, "ops": {verb:
# [names]}, "told": groups reminded}. layout_flowsheet clears it; so does the session closing
# or another model opening under its name.
_LAYOUT: dict = {}
_ENDS = ("run_simulation", "save_simulation")       # a request that runs or saves is past its topology
_VERBS = {"place_block": ("placed", "block_name", "name"), "remove_block": ("removed", "block_name", None),
          "place_stream": ("added stream", "stream_name", "name"),
          "remove_stream": ("removed stream", "stream_name", None),
          "connect_stream": ("connected", "stream_name", "stream"),
          "disconnect_stream": ("disconnected", "stream_name", "stream_name")}
_NAMES_MAX = 50


def _layout_due(get_manager, name, kw, session, group, res, topo):
    """Keep each session's topology changes that are not laid out yet, and remind the AI
    to run layout_flowsheet -- a last line of the answer, once per change group and session:
    when its request runs or saves the model or answers its Ask AI note, or, left over from
    an earlier request, at the first call of the next one. ``topo``: the (batch item, answer)
    pairs of a topology call (``each``), [] for a single one; None for any other call."""
    if (not _LAYOUT and topo is None) or not isinstance(res, str):
        return res
    try:
        gid = group.get("id") if isinstance(group, dict) else None
        m = get_manager()
        if name == "layout_flowsheet" and not probes.failed(res):
            _LAYOUT.pop(session, None)
        for s in [s for s, p in _LAYOUT.items() if m.model_id(s) != p["model"]]:
            del _LAYOUT[s]
        if gid is None:
            return res
        notes = []
        for s, p in _LAYOUT.items():
            if p["group"] != gid and p["group"] not in p["told"]:
                p["told"].add(p["group"])
                notes.append(_reminder("an earlier request", s, p["ops"]))
        if topo is not None:
            _track(m, name, kw, session, gid, res, topo)
        if name in _ENDS or (name == "workbench_edit" and kw.get("note_replies")):
            for s, p in _LAYOUT.items():
                if p["group"] == gid and gid not in p["told"] and (name == "workbench_edit" or s == session):
                    p["told"].add(gid)
                    notes.append(_reminder("this request", s, p["ops"]))
        if notes:
            return res.rstrip("\n") + "\n\n" + "\n".join(notes)
    except Exception as exc:
        logger.warning("intercept: layout reminder after %s failed (%r)", name, exc)
    return res


def _track(m, name, kw, session, gid, res, topo) -> None:
    """Add what a topology call did (the items its answer does not call failed) to its session."""
    ops = [_topo_op(name, kw, item) for item, answer in (topo or [(None, res)]) if not probes.failed(answer)]
    ops = [op for op in ops if op is not None]
    if not ops or not session:
        return
    p = _LAYOUT.get(session)
    if p is None:
        p = _LAYOUT[session] = {"model": m.model_id(session), "group": gid, "ops": {}, "told": set()}
    p["group"] = gid
    for verb, el in ops:
        names = p["ops"].setdefault(verb, [])
        if len(names) < _NAMES_MAX:
            names.append(el)


def _topo_op(name, kw, item) -> tuple | None:
    """(verb, element) of one topology change: a call's, or a batch item's."""
    if name in ("add_element", "remove_element"):
        add, path = name == "add_element", str(kw.get("aspen_path") or "").rstrip("\\").casefold()
        el = str(kw.get("name") or "?").split("!")[0]
        if path.endswith(r"\data\blocks"):
            return ("placed" if add else "removed"), el
        if path.endswith(r"\data\streams"):
            return ("added stream" if add else "removed stream"), el
        return ("connected" if add else "disconnected"), el
    verb, arg, key = _VERBS.get(name, (None, None, None))
    if verb is None:
        return None
    return verb, str((item.get(key) if isinstance(item, dict) else kw.get(arg)) or "?")


def _reminder(who, session, ops) -> str:
    parts = []
    for verb, names in ops.items():
        if verb in ("connected", "disconnected"):
            parts.append(f"{verb} {len(names)} stream{'s' * (len(names) != 1)}")
        else:
            more = f" +{len(names) - 6} more" if len(names) > 6 else ""
            parts.append(f"{verb}{'s' * (verb.endswith('stream') and len(names) > 1)} {', '.join(names[:6])}{more}")
    return (f"Note: {who} changed the flowsheet of '{session}' ({'; '.join(parts)}) and Aspen's own drawing is "
            f"not laid out for it: run layout_flowsheet once when this request's topology edits are done.")
