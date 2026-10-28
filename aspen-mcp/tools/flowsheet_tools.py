"""Implementations for flowsheet category tools.

Each function calls manager.get_app() to get the COM object directly.
Port resolution is a lookup in the port table (see searcher/discover_ports.py).
"""

from __future__ import annotations

import difflib
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

# Port table: the shipped searcher/block_ports.json overlaid by ~/.aspen-mcp/block_ports.json
# (discover_ports writes the latter). One dict, refreshed in place by reload_ports(), so
# references taken elsewhere (main_tools) stay current.
from searcher.discover_ports import PORTS as _PORTS, ports_for, reload_ports  # noqa: F401
from tools import checkpoints, dialogs, dispid, ids, knowledge_tools, pfsv, probes
from tools.checkpoints import SaveError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from aspen_manager import AspenPlusManager


# ---------------------------------------------------------------------------
# Names. FindNode is exact-case, Aspen's names are not (seen on V15):
# a block or stream added in lower case is listed upper-case -- and the Add
# raises all the same ("r9" -> R9 plus "Invalid Block/Model/Library
# Specification"); a lower-case name of an existing block crashes V15; a raw Add
# of an existing block's name under another type silently retypes it, a stream's
# silently does nothing. Other folders keep a lower-case name as a second object
# ("zds" beside Design-Spec ZDS). And a block named exactly like a Design-Spec,
# Calculator, Transfer or Measurement crashes V15 (a block named XA beside a Design-Spec XA); a block
# named like any other object (Balance, Sensitivity, Convergence, ...) or like a
# lower-case Design-Spec, and a stream named like anything but a stream, are fine
# So a name is upper-cased for blocks and
# streams, and one that is taken is refused before Aspen is asked.
# ---------------------------------------------------------------------------

_BLOCKS, _STREAMS = "\\Data\\Blocks", "\\Data\\Streams"
_UPPER = (_BLOCKS, _STREAMS)            # Aspen lists every name here upper-case
_BLOCK_RIVALS = (("\\Data\\Flowsheeting Options\\Design-Spec", "Design-Spec"),
                 ("\\Data\\Flowsheeting Options\\Calculator", "Calculator"),
                 ("\\Data\\Flowsheeting Options\\Transfer", "Transfer"),
                 ("\\Data\\Flowsheeting Options\\Measurement", "Measurement"))
# A child of this costs as long as an Export the first time it is touched after a run
# (inputs_check._HEAVY): not looked up -- Aspen refuses an exact duplicate there itself.
_HEAVY = ("\\Data\\Model Analysis Tools\\Sensitivity",)


def aspen_name(folder: str, name) -> str:
    """``name`` as Aspen lists it under ``folder``: upper-case for blocks and streams, else as given."""
    if name is None:
        return name
    name = str(name).strip()
    return name.upper() if _norm(folder) in _UPPER else name


def _norm(folder: str) -> str:
    return "\\" + str(folder).strip().strip("\\")


def _rtype(node) -> str | None:
    """An element's type: its RECORDTYPE (Heater, MATERIAL), else a string value."""
    for how in (("AttributeValue", 6), ("Value",)):
        try:
            v = dispid.get(node, *how)
        except Exception:
            continue
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _names(node) -> list[str]:
    """The names of a node's children, in order ([] when it has none). Listed by the node's
    enumerator: the node can be any path add_element is given (``_child``), and Item(i) faults
    Aspen on some label-keyed tables (knowledge_tools._children)."""
    if node is None:
        return []
    items = knowledge_tools._children(node.Elements)
    return [str(dispid.get(it, "Name")) for it in items if it is not None]


def _child(tree, folder: str, name: str):
    """(name as Aspen lists it, node) of the child of ``folder`` that is ``name`` ignoring
    case; None when there is none."""
    folder = _norm(folder)
    if folder in _HEAVY:
        return None
    for n in dict.fromkeys((name, name.upper())):
        node = tree.FindNode(f"{folder}\\{n}")
        if node is not None:
            return n, node
    if folder in _UPPER:
        return None
    try:
        listed = _names(tree.FindNode(folder))
    except Exception:                              # not a folder: Aspen's Add says so
        return None
    hit = next((n for n in listed if n.upper() == name.upper()), None)
    return None if hit is None else (hit, tree.FindNode(f"{folder}\\{hit}"))


def name_taken(app, folder: str, name: str) -> tuple | None:
    """What already holds ``name`` (ignoring case) where an element of that name would be
    added under ``folder``: (kind, name as Aspen lists it, its type) -- kind None for
    ``folder`` itself, else the object whose name a block may not take ("Design-Spec", ...);
    None when the name is free."""
    tree = app.Tree
    hit = _child(tree, folder, name)
    if hit is not None:
        return None, hit[0], _rtype(hit[1])
    if _norm(folder) == _BLOCKS:
        for rival, kind in _BLOCK_RIVALS:              # exact case, as V15 clashes
            if tree.FindNode(f"{rival}\\{name.upper()}") is not None:
                return kind, name.upper(), None
    return None


def id_refusal(app, what: str, folder: str, name, fallback: str) -> str | None:
    """The refusal of a new block or stream ID Aspen would refuse or cut (tools/ids.py), with an
    ID that fits and is free under ``folder``; None when ``name`` fits."""
    if ids.problem(name) is None:
        return None
    try:
        taken = _names(app.Tree.FindNode(_norm(folder)))
    except Exception:
        taken = ()
    return ids.refusal(what, name, taken, fallback)


def taken_text(what: str, given: str, name: str, taken: tuple, verb: str, instead: str) -> str:
    """The refusal of a name ``name_taken`` found: ``what`` 'Block' / 'Stream' / 'Element',
    ``given`` the name as the call gave it, ``name`` as it would have been added, ``verb`` what
    was not done, ``instead`` the tool that removes the one there."""
    kind, have, typ = taken
    if kind is not None:
        return (f"{what} '{name}' {verb}: {kind} {have} already exists, and Aspen crashes on a block "
                f"named like a Design-Spec, Calculator, Transfer or Measurement. Use another name.")
    case = "" if have == given else f"; Aspen names ignore case, so '{given}' is {have}"
    return (f"{what} '{have}' already exists ({typ or 'type unknown'}{case}); {verb}. "
            f"Use another name, or {instead} first to replace it.")


def _resolve_port(block_type: str, port_name: str) -> str | None:
    """Resolve a port name using the port table. Returns matched port or None."""
    ports = ports_for(block_type)
    if not ports:
        return None
    # Exact match
    if port_name in ports:
        return port_name
    # Case-insensitive match
    upper = port_name.upper()
    for p in ports:
        if p.upper() == upper:
            return p
    return None


# GUI palette names Aspen's Elements.Add does not take, by the record type it does (live V15:
# of the 67 palette names only ChgBal fails -- "ChgBal" and "CHGBAL" give Invalid
# Block/Model/Library Specification, CHARGEBAL places it).
_TYPE_ALIAS = {"CHGBAL": "CHARGEBAL"}


def block_record_type(block_type: str) -> str:
    """The type Elements.Add takes for ``block_type``: a GUI-only name mapped, else as given."""
    return _TYPE_ALIAS.get(str(block_type or "").strip().upper(), block_type)


def _near_types(block_type: str) -> list[str]:
    """The known block types (port table, aliases) whose names come closest to ``block_type``."""
    known = {str(t).upper(): str(t) for t in (*_PORTS, *_TYPE_ALIAS, *_TYPE_ALIAS.values())}
    hits = difflib.get_close_matches(str(block_type or "").upper(), list(known), n=4, cutoff=0.6)
    return [known[h] for h in hits]


@dialogs.quiet
def place_block(
    manager: AspenPlusManager,
    session_name: str,
    block_name: str,
    block_type: str,
) -> str:
    """Place a new block on the flowsheet."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    bad_id = id_refusal(app, "Block", _BLOCKS, block_name, "B")
    if bad_id:
        return bad_id
    given, block_name = block_name, aspen_name(_BLOCKS, block_name)
    rtype = block_record_type(block_type)
    try:
        taken = name_taken(app, _BLOCKS, block_name)
        if taken is not None:
            return taken_text("Block", given, block_name, taken, "not placed", "remove_block")

        blocks_node = app.Tree.FindNode("\\Data\\Blocks")
        blocks_node.Elements.Add(f"{block_name}!{rtype}")
        time.sleep(0.5)
        as_ = "" if rtype == block_type else f" as {rtype}, the type Aspen files it under"
        return f"Block '{block_name}' ({block_type}) placed{as_}."
    except Exception as exc:
        logger.error("Failed to place block '%s': %s", block_name, exc, exc_info=True)
        hint = ""
        if "Invalid Block/Model/Library" in str(exc):
            near = [t for t in _near_types(block_type) if t.upper() != str(block_type).upper()]
            hint = (f" '{block_type}' is not a block type Aspen knows"
                    + (f"; did you mean {', '.join(near)}?" if near else "."))
        return f"Failed to place block '{block_name}': {exc}{hint}"


@dialogs.quiet
def remove_block(manager: AspenPlusManager, session_name: str, block_name: str) -> str:
    """Remove a block from the flowsheet."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    block_name = aspen_name(_BLOCKS, block_name)
    try:
        app.Tree.FindNode("\\Data\\Blocks").Elements.Remove(block_name)
        return f"Block '{block_name}' removed."
    except Exception as exc:
        logger.error("Failed to remove block '%s': %s", block_name, exc, exc_info=True)
        return f"Failed to remove block '{block_name}': {exc}"


@dialogs.quiet
def place_stream(
    manager: AspenPlusManager,
    session_name: str,
    stream_name: str,
    stream_type: str = "MATERIAL",
) -> str:
    """Place a new stream on the flowsheet."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    bad_id = id_refusal(app, "Stream", _STREAMS, stream_name, "S")
    if bad_id:
        return bad_id
    given, stream_name = stream_name, aspen_name(_STREAMS, stream_name)
    try:
        taken = name_taken(app, _STREAMS, stream_name)
        if taken is not None:
            return taken_text("Stream", given, stream_name, taken, "not placed", "remove_stream")
        app.Tree.FindNode("\\Data\\Streams").Elements.Add(f"{stream_name}!{stream_type}")
        return f"Stream '{stream_name}' ({stream_type}) placed."
    except Exception as exc:
        logger.error("Failed to place stream '%s': %s", stream_name, exc, exc_info=True)
        return f"Failed to place stream '{stream_name}': {exc}"


@dialogs.quiet
def remove_stream(manager: AspenPlusManager, session_name: str, stream_name: str) -> str:
    """Remove a stream from the flowsheet."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    stream_name = aspen_name(_STREAMS, stream_name)
    try:
        app.Tree.FindNode("\\Data\\Streams").Elements.Remove(stream_name)
        return f"Stream '{stream_name}' removed."
    except Exception as exc:
        logger.error("Failed to remove stream '%s': %s", stream_name, exc, exc_info=True)
        return f"Failed to remove stream '{stream_name}': {exc}"


@dialogs.quiet
def connect_stream(
    manager: AspenPlusManager,
    session_name: str,
    block_name: str,
    stream_name: str,
    port_name: str,
    block_type: str | None = None,
) -> str:
    """Connect a stream to a block port.(port name: F(IN), LD(OUT), B(OUT)...)"""
    if block_type:
        resolved = _resolve_port(block_type, port_name)
        if resolved:
            port_name = resolved

    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    block_name, stream_name = aspen_name(_BLOCKS, block_name), aspen_name(_STREAMS, stream_name)
    try:
        blocks = app.Tree.FindNode("\\Data\\Blocks")
        block_node = blocks.Elements(block_name)
        ports_node = block_node.Elements("Ports")
        port_node = ports_node.Elements(port_name)
        if port_node is None:                      # FindNode and Elements(name) are exact-case
            hit = next((p for p in _names(ports_node) if p.upper() == str(port_name).upper()), None)
            if hit is not None:
                port_name, port_node = hit, ports_node.Elements(hit)
        if port_node is None:
            return (f"Port '{port_name}' not found on block '{block_name}'."
                    " Use discover_ports to see valid port names.")
        port_els = port_node.Elements
        if port_els is None:
            return (f"Port '{port_name}' not found on block '{block_name}'."
                    " Use discover_ports to see valid port names.")

        # An occupied single-stream outlet is freed so the stream can take its place. Only
        # after Aspen refuses the add: FSplit P(OUT)/HS(OUT) and the like take several
        # streams, and freeing them first silently dropped every outlet but the last.
        try:
            port_els.Add(stream_name)
        except Exception:
            if "(OUT)" not in port_name.upper() or port_els.Count == 0:
                raise
            old_stream = port_els.Item(0).Name
            port_els.Remove(old_stream)
            logger.info("Auto-disconnected stream '%s' from %s:%s", old_stream, block_name, port_name)
            port_els.Add(stream_name)
            return (f"Stream '{stream_name}' connected to {block_name} port {port_name} "
                    f"(replaced '{old_stream}', now unconnected).")
        return f"Stream '{stream_name}' connected to {block_name} port {port_name}."
    except Exception as exc:
        logger.error("Failed to connect stream '%s' to %s:%s: %s", stream_name, block_name, port_name, exc, exc_info=True)
        return f"Failed to connect stream '{stream_name}' to {block_name}:{port_name}: {exc}"


# ---------------------------------------------------------------------------
# Disconnect: the port's Elements.Remove(stream) -- connect_stream's own way of freeing an
# outlet above, and the undo's (undo_apply). On V15:
# an inlet or an outlet, the stream stays with that end free; removing a stream that is not
# on the port is refused, so that is checked first. A stream's ends are read as the probes
# read them (probes._ends: the stream's own Connections, then the block's for the port).
# ---------------------------------------------------------------------------

@dialogs.quiet
def disconnect_stream(manager: AspenPlusManager, session_name: str, stream_name: str,
                      block_name: str, port_name: str) -> str:
    """Take a stream off one block port; the stream stays."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    stream, block = aspen_name(_STREAMS, stream_name), aspen_name(_BLOCKS, block_name)
    try:
        tree = app.Tree
        if tree.FindNode(f"{_BLOCKS}\\{block}") is None:
            return f"Failed to disconnect '{stream}': block '{block}' not found."
        port, node = probes._port(tree, block, port_name)
        if node is None:
            return (f"Failed to disconnect '{stream}': port '{port_name}' not found on block '{block}'."
                    " Use discover_ports to see valid port names.")
        port = str(dispid.get(node, "Name") or port)          # as Aspen names it
        on = probes._names(node) or []
        hit = next((x for x in on if x.upper() == stream.upper()), None)
        if hit is None:
            return (f"Failed to disconnect '{stream}': it is not on {block} port {port} "
                    f"({'on it: ' + ', '.join(on) if on else 'the port is free'}).")
        node.Elements.Remove(hit)
        return f"Stream '{hit}' disconnected from {block} port {port}."
    except Exception as exc:
        logger.error("Failed to disconnect stream '%s' from %s:%s: %s", stream, block, port_name, exc, exc_info=True)
        return f"Failed to disconnect '{stream}' from {block}:{port_name}: {exc}"


def stream_ends(manager: AspenPlusManager, session_name: str, stream_name: str,
                block_name: str | None = None) -> tuple[list[dict], str | None]:
    """The ports ``stream_name`` is on (only ``block_name``'s, when given), as disconnect_stream
    items [{"stream_name", "block_name", "port_name"}], and, when there are none, the answer."""
    app = manager.get_app(session_name)
    if app is None:
        return [], f"No active session named '{session_name}'."
    stream = aspen_name(_STREAMS, stream_name)
    block = aspen_name(_BLOCKS, block_name) if block_name else None
    try:
        tree = app.Tree
        if tree.FindNode(f"{_STREAMS}\\{stream}") is None:
            return [], f"Failed to disconnect '{stream}': stream not found."
        if block is not None and tree.FindNode(f"{_BLOCKS}\\{block}") is None:
            return [], f"Failed to disconnect '{stream}': block '{block}' not found."
        name, ends = probes._ends(tree, stream)
    except Exception as exc:
        logger.error("Failed to read the ends of stream '%s': %s", stream, exc, exc_info=True)
        return [], f"Failed to disconnect '{stream}': {exc}"
    if ends is None:
        return [], f"Failed to disconnect '{stream}': its connections could not be read."
    items = [{"stream_name": name, "block_name": b, "port_name": p} for b, p in ends
             if block is None or b.upper() == block.upper()]
    if not items:
        return [], f"Stream '{name}' is not connected{' to ' + block if block else ''}; nothing to disconnect."
    return items, None


# ---------------------------------------------------------------------------
# Flowsheet layout -- delete the .bkp drawing and let Aspen redraw it on
# reopen. V15's regeneration lays the diagram out left-to-right by process
# order with proper icons and routed streams -- strictly better than any
# hand-computed coordinates, and text-splicing a synthetic section risks
# parseable-but-unrenderable graphics (symptom: blank white canvas even at
# full zoom, while the tree shows all blocks).
# Only the PFSVData section goes. The " GRAPHICS_BACKUP" block that holds it
# also holds the model's $CONFIG (databanks, display options),
# $_APWNSHELL_SETTINGS and $_GRID_TEMPLATES: cut from its header and Aspen
# silently drops all of them for defaults (live, V15: purebank PURE38 became
# PURE41). The file is edited as bytes: whole lines go, every other byte
# (non-ASCII text in any code page, line endings) stays as Aspen wrote it.
# Aspen draws the model only once its window shows, a second or two after the
# reopen -- a save before that has no drawing at all -- so the save waits for
# it; a hidden session is drawn when it is next shown.
# ---------------------------------------------------------------------------

_TMP = Path.home() / ".aspen-mcp" / "tmp"       # Aspen's exports of the model, read and deleted at once
_DRAW_WAIT_S = 20.0


def _drop_drawing(data: bytes) -> tuple[bytes, int] | None:
    """The .bkp without its drawing, and the number of lines removed; None when it has none.
    The drawing is the PFSVData section: from the first line whose first word is PFSVData
    (as tools/pfsv.py finds it) up to the next ``$_`` line or the end -- icons, routes,
    legend, viewport, hierarchy drawings; Aspen resets the lot once the icons are gone.
    Every other line stays, the GRAPHICS_BACKUP header and $CONFIG before it included."""
    lines = data.splitlines(keepends=True)
    g0 = next((i for i, l in enumerate(lines) if l.split()[:1] == [b"PFSVData"]), None)
    if g0 is None:
        return None
    g1 = next((i for i in range(g0 + 1, len(lines)) if lines[i].startswith(b"$_")), len(lines))
    return b"".join(lines[:g0] + lines[g1:]), g1 - g0


def _await_drawing(app, timeout: float = _DRAW_WAIT_S) -> bool:
    """Wait until Aspen has drawn the reopened model: its backup export (Export(1); the
    session's file is not touched) has a PFSVData section again -- Aspen writes none until it
    has laid the model out. False when it has not within ``timeout`` seconds."""
    end = time.time() + timeout
    while True:
        try:
            if pfsv.parse_pfsvdata(pfsv.export_text(app, _TMP))["found"]:
                return True
        except Exception:
            logger.debug("layout: reading the redrawn diagram failed", exc_info=True)
        if time.time() >= end:
            return False
        time.sleep(0.5)


def _arrange(manager: AspenPlusManager, session_name: str, arrange: dict) -> str:
    """layout_flowsheet with an arrangement: the drawing's coordinates edited in the saved .bkp
    (patch_file: saved first, backed up, reopened). Nothing is written when the model has no
    drawing yet or none of the blocks is in it."""
    blocks = {str(k): v for k, v in (arrange.get("blocks") or {}).items()
              if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(c, (int, float)) for c in v)}
    if not blocks:
        return "Arrangement not applied: it places no block."
    got = {}

    def edit(data):
        old = pfsv.parse_pfsvdata(data.decode("latin-1"))
        if not old["found"]:
            got["why"] = "no_drawing"
            return None
        res = pfsv.place(data, pfsv.to_aspen(blocks, old["blocks"]), arrange.get("ends") or {})
        if res is None or not res[1]["moved"]:
            got["why"] = "none_in_drawing"
            return None
        got.update(res[1], same=res[0] == data)
        return res[0]

    try:
        res = manager.patch_file(session_name, edit, tool="layout_flowsheet")
    except SaveError as exc:
        return f"Arrangement not applied: {exc}"
    except Exception as exc:
        logger.error("arranging '%s' failed: %s", session_name, exc, exc_info=True)
        return f"Arrangement failed: {exc}"
    note = checkpoints.note(res["backup"])
    if got.get("why") == "no_drawing":
        return "\n".join(filter(None, ("Arrangement not applied: Aspen's file has no drawing yet; run "
                                        "layout_flowsheet without one first (Aspen draws the model), then again.", note)))
    if got.get("same"):
        return "\n".join(filter(None, ("Nothing to change: Aspen's blocks are already where the workbench has them.", note)))
    if not res["changed"]:
        return "\n".join(filter(None, ("Arrangement not applied: none of its blocks is in Aspen's drawing.", note)))
    if not res["reopened"]:
        return "\n".join(filter(None, (
            f"Arrangement written to {res['path']} but reopen failed: {res['opened']}", note)))
    miss = got.get("missing") or []
    return "\n".join(filter(None, (
        f"Flowsheet diagram arranged as in the workbench: {len(got['moved'])} block(s) moved, "
        f"{len(got['streams'])} stream route(s) moved along; Aspen reopened the model.",
        f"Not in Aspen's drawing, left as they were: {', '.join(miss[:10])}." if miss else "", note)))

def layout_flowsheet(manager: AspenPlusManager, session_name: str, arrange: dict | None = None) -> str:
    """Aspen's own drawing laid out again (Aspen redraws it once the drawing is cut), or, with
    ``arrange`` {"blocks": {name: [x, y]} (the workbench's block centres, px, y down), "ends":
    {stream: [source, destination]}}, its blocks put where the workbench has them, in Aspen's scale
    (pfsv.to_aspen) -- each stream's route moved along with its blocks (pfsv.place)."""
    if manager.get_app(session_name) is None:
        return f"No active session named '{session_name}'."
    if arrange is not None:
        return _arrange(manager, session_name, arrange)
    removed = []

    def edit(data):
        cut = _drop_drawing(data)
        if cut is None:
            return None
        removed.append(cut[1])
        return cut[0]

    try:
        res = manager.patch_file(session_name, edit, tool="layout_flowsheet")
    except SaveError as exc:
        return f"Layout not done: {exc}"
    except Exception as exc:
        logger.error("layout of '%s' failed: %s", session_name, exc, exc_info=True)
        return f"Layout failed: {exc}"
    note = checkpoints.note(res["backup"])
    if not res["changed"]:
        return "\n".join(filter(None, ("No graphics section found; nothing to reset.", note)))
    if not res["reopened"]:
        return "\n".join(filter(None, (
            f"Graphics reset in {res['path']} but reopen failed: {res['opened']}", note)))
    app = manager.get_app(session_name)
    if not manager.visible(session_name):
        later = ("The session is hidden: Aspen draws the new diagram when the model is next "
                 "shown, and the file has none until a save after that.")
    elif app is not None and _await_drawing(app):
        later = ""
    else:
        later = (f"Aspen had not drawn the diagram {_DRAW_WAIT_S:.0f} s after the reopen, so "
                 "this save has none; the next save stores it.")
    # save so Aspen persists its regenerated layout into the file
    try:
        manager.save(session_name, tool="layout_flowsheet")
    except SaveError as exc:
        later = f"The redrawn diagram is not saved yet: {exc}"
    return "\n".join(filter(None, (
        f"Flowsheet diagram reset ({removed[0]} drawing lines removed); "
        "Aspen regenerated a clean left-to-right layout on reopen.", note, later)))
