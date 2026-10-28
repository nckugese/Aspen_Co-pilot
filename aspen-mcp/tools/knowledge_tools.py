"""Observational knowledge extraction — node-tree snapshot & diff (MVP).

Implements the observation half of the "demonstration -> extract -> retrieve"
loop. The LLM frames a ``root_path`` (a region, e.g. a block or
its ``\\Input`` subtree), takes a snapshot before and after the user demonstrates
a setup in the Aspen GUI, then diffs the two snapshots.

What a snapshot captures, per node (not just leaf values):
- ``value``       — ``node.Value``
- ``unit``        — ``node.UnitString``
- ``recordtype``  — ``AttributeValue(6)``: the object type (e.g. a reaction set's
  ``LHHW`` / ``POWERLAW``). This lives in an attribute, NOT in ``.Value``.
- ``basis``, ``userentered``, ``valuedefault``, ``upperlimit``, ``lowerlimit``,
  ``optionlist`` — other configuration attributes.
Every node is recorded (containers included), so the diff detects not only
changed items but also added / removed child nodes.

Design notes:
- The full snapshot lives **server-side only** (an in-memory dict); it is never
  returned to the LLM. ``snapshot_tree`` returns just an id + node count, so the
  token cost is independent of subtree size. Only ``diff_snapshot``'s delta
  reaches the model.
- No hard traversal cap: the whole subtree is walked. When it is large the return
  carries an advisory to narrow ``root_path``; ``count_only=True`` probes size first.
- Aspen exposes some collections (component-indexed COEF/EXPONENT, ANAME, ...) keyed
  by label, where ``Elements.Item(integer)`` returns None. Children are enumerated
  via the COM ``_NewEnum`` iterator (``_children``) so those string-keyed subtrees
  (e.g. stoichiometry) are not silently skipped.
- Standard library only (no heavy imports inside an MCP tool).
- The walk (``_iter_tree``, ``_walk_tree``) is shared with the workbench's deep compare of one
  block's or stream's inputs (tools/external.py ``Deep``), which reads two items a node.

Storage is intentionally in-memory (cleared on server restart).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Server-side snapshot store: id -> {session, root, input_only, nodes, label}.
# In-memory only; lost on MCP server restart.
_SNAPSHOTS: dict[str, dict] = {}
_COUNTER: dict[str, int] = {}

# Defensive recursion backstop (NOT a coverage cap) — guards against an
# unexpected cyclic COM reference, not against deep-but-finite Aspen trees.
_MAX_DEPTH = 60
# Above this node count the snapshot return suggests narrowing the root.
_LARGE_NODE_HINT = 4000

# Per-node attributes to capture beyond value/unit (Aspen HAP attribute numbers).
# value is read via .Value, unit via .UnitString.
_NODE_ATTRS = {
    "recordtype": 6,    # object type, e.g. reaction set LHHW / POWERLAW
    "basis": 13,
    "userentered": 11,  # was this value entered by the user vs a default
    "valuedefault": 10,
    "upperlimit": 8,
    "lowerlimit": 9,
    "optionlist": 5,
}
# Attributes shown inline for an *added* node (kept compact); changed nodes show
# every differing attribute regardless of this list.
_ADDED_INLINE_ATTRS = ("recordtype", "unit", "basis")


def server_fault(exc) -> bool:
    """``exc`` is Aspen's internal fault (RPC_E_SERVERFAULT): aspen_manager.server_fault -- the
    COM error's HRESULT, or the scode of a DISP_E_EXCEPTION. Looked up at the call, as
    aspen_manager imports this module (it is loaded long before any walk: a dict lookup)."""
    import aspen_manager
    return aspen_manager.server_fault(exc)


def _next_id(session_name: str) -> str:
    _COUNTER[session_name] = _COUNTER.get(session_name, 0) + 1
    return f"{session_name}#{_COUNTER[session_name]}"


def _children(els) -> list:
    """Return child nodes of an Elements collection, robust to string-keyed tables.

    Aspen exposes some collections (component-indexed COEF/EXPONENT, ANAME, ...) keyed
    by label rather than position: ``Elements.Item(integer)`` returns None for those,
    so a positional loop silently skips the whole subtree -- and on some (V15: a binary
    parameter set's ``CC Nodes\\LBLLE\\NRTL``) it faults Aspen (RPC_E_SERVERFAULT), after
    which no run of that session returns. The COM _NewEnum iterator (``for c in els``)
    yields the real children for both integer- and string-keyed collections, so every walk
    over a node not known in advance lists it here. Fall back to positional access only if
    iteration is unsupported; a fault there is raised at once, not met again for every row.
    """
    try:
        kids = list(els)
        if kids:
            return kids
    except Exception as exc:
        if server_fault(exc):
            raise
        logger.debug("Elements not iterable; falling back to positional access")
    out = []
    try:
        count = els.Count
    except Exception:
        return out
    for i in range(count):
        try:
            out.append(els.Item(i))
        except Exception as exc:
            if server_fault(exc):
                raise
            out.append(None)
    return out


def _read_node(node) -> dict:
    """Read all captured items of a single node: value, unit, and key attributes.

    Only non-empty items are recorded. Every COM access is guarded.
    """
    rec: dict[str, str] = {}
    try:
        v = node.Value
    except Exception:
        v = None
    if v is not None:
        rec["value"] = str(v)
    try:
        u = node.UnitString
        if u:
            rec["unit"] = str(u)
    except Exception:
        pass
    for name, num in _NODE_ATTRS.items():
        try:
            a = node.AttributeValue(num)
        except Exception:
            a = None
        if a is not None and str(a) != "":
            rec[name] = str(a)
    return rec


class _Win32com:
    """How the walk reaches a node's children and its name: through win32com's own access, a
    collection's children listed at once (``_children``). The snapshot's; the deep compare
    passes its own (tools/external.py: by DISPID, children one at a time)."""

    @staticmethod
    def elements(node):
        return node.Elements

    @staticmethod
    def children(els):
        return _children(els)

    @staticmethod
    def name(child):
        return child.Name


def _iter_tree(node, path: str, *, input_only: bool, access=None, _depth: int = 0):
    """Every node under ``node`` as ``(path, node)``, depth first, a node before its children
    (containers too); ``access``: elements / children / name (default ``_Win32com``). A
    generator, so a caller can stop between two nodes and go on later: the deep compare
    (tools/external.py) walks in turns that let the event loop run."""
    acc = _Win32com if access is None else access
    if _depth > _MAX_DEPTH:
        logger.warning("snapshot walk hit defensive depth limit at '%s'", path)
        return
    try:
        els = acc.elements(node)
    except Exception:
        logger.debug("No Elements under '%s'", path)
        return

    for i, child in enumerate(acc.children(els)):
        if child is None:
            continue
        try:
            name = acc.name(child)
        except Exception:
            name = None
        if name is None:
            name = f"[{i}]"
        # input_only: skip the Output (results) branch; keep only the input side.
        if input_only and str(name) == "Output":
            continue
        child_path = f"{path}\\{name}"
        yield child_path, child
        yield from _iter_tree(child, child_path, input_only=input_only, access=access, _depth=_depth + 1)


def _walk_tree(node, path: str, nodes: dict, *, input_only: bool, read=None, stop=None,
               _depth: int = 0) -> int:
    """Record EVERY node under ``node`` into ``nodes[path] = read(node)`` (``read``: default
    ``_read_node``, the snapshot's items; the deep compare reads value and unit only).

    Records containers as well as leaves so the diff can detect added/removed nodes.
    ``stop()`` true ends the walk before the next node (default: never). Returns the number
    of nodes visited.
    """
    read = _read_node if read is None else read
    visited = 0
    for child_path, child in _iter_tree(node, path, input_only=input_only, _depth=_depth):
        if stop is not None and stop():
            break
        nodes[child_path] = read(child)
        visited += 1
    return visited


def _large_hint(n: int) -> str:
    if n > _LARGE_NODE_HINT:
        return (f"\n(Note: {n} nodes is large. If you only need this demonstration, "
                f"consider narrowing root_path to a specific block or its \\Input subtree.)")
    return ""


def run_snapshot(manager, session_name: str, root_path: str,
                 input_only: bool = True, count_only: bool = False,
                 label: str | None = None) -> str:
    """Walk ``root_path`` and store a server-side snapshot. Returns id + count only."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."

    try:
        node = app.Tree.FindNode(root_path)
    except Exception as exc:
        logger.error("snapshot FindNode failed for '%s': %s", root_path, exc, exc_info=True)
        return f"Error finding node '{root_path}': {exc}"
    if node is None:
        return f"Node not found: {root_path}"

    root_key = root_path.rstrip("\\")
    nodes: dict[str, dict] = {}
    try:
        nodes[root_key] = _read_node(node)  # capture root itself (its recordtype, etc.)
        _walk_tree(node, root_key, nodes, input_only=input_only)
    except Exception as exc:
        logger.error("snapshot walk failed under '%s': %s", root_path, exc, exc_info=True)
        return f"Error walking '{root_path}': {exc}"

    n = len(nodes)
    hint = _large_hint(n)

    if count_only:
        return (f"count_only: {n} nodes under '{root_path}' "
                f"(input_only={input_only}).{hint}")

    sid = _next_id(session_name)
    _SNAPSHOTS[sid] = {
        "session": session_name, "root": root_path,
        "input_only": input_only, "nodes": nodes, "label": label,
    }
    label_str = f" | label={label}" if label else ""
    return (f"snapshot id={sid} | root='{root_path}' | {n} nodes | "
            f"input_only={input_only}{label_str}.{hint}\n"
            f"Take another snapshot after the demonstration, then call "
            f"diff_snapshot(session_name, id_before='{sid}', id_after=<new id>).")


def _fmt_added(path: str, rec: dict) -> str:
    val = rec.get("value")
    extras = [f"{k}={rec[k]}" for k in _ADDED_INLINE_ATTRS if k in rec]
    line = f"  {path}"
    if val is not None:
        line += f" = {val}"
    if extras:
        line += f"  {{{', '.join(extras)}}}"
    return line


def _fmt_changed(path: str, before: dict, after: dict) -> list:
    keys = sorted(set(before) | set(after))
    lines = []
    for k in keys:
        b, a = before.get(k), after.get(k)
        if b != a:
            lines.append(f"  {path} [{k}]: {b} -> {a}")
    return lines


def run_diff(manager, session_name: str, id_before: str, id_after: str) -> str:
    """Diff two server-side snapshots. Returns only the delta (+ a next-step hint)."""
    before = _SNAPSHOTS.get(id_before)
    after = _SNAPSHOTS.get(id_after)
    missing = [i for i, s in ((id_before, before), (id_after, after)) if s is None]
    if missing:
        known = ", ".join(_SNAPSHOTS) or "(none)"
        return (f"Snapshot(s) not found: {', '.join(missing)}. Snapshots are kept only in the "
                f"running server, so a restart clears them — re-run snapshot_tree. "
                f"Known ids: {known}.")

    nb = before["nodes"]
    na = after["nodes"]
    added = [p for p in na if p not in nb]
    removed = [p for p in nb if p not in na]
    changed = [p for p in na if p in nb and na[p] != nb[p]]

    if not (changed or added or removed):
        return ("No differences between the two snapshots. If the user did demonstrate a "
                "change, check that root_path covered it and that input_only did not prune "
                "the edited subtree (Output branch is skipped when input_only=True).")

    lines = []
    if changed:
        lines.append(f"Changed ({len(changed)}):")
        for p in sorted(changed):
            lines.extend(_fmt_changed(p, nb[p], na[p]))
    if added:
        lines.append(f"Added nodes ({len(added)}):")
        for p in sorted(added):
            lines.append(_fmt_added(p, na[p]))
    if removed:
        lines.append(f"Removed nodes ({len(removed)}):")
        for p in sorted(removed):
            lines.append(f"  {p}")

    header = (f"Diff {id_before} -> {id_after} (root '{after['root']}'): "
              f"{len(changed)} changed, {len(added)} added, {len(removed)} removed.")
    next_step = (
        "\n\nNext step (to persist as knowledge): summarize the user's intent together with the "
        "delta above into a natural-language note. Note the object's recordtype (e.g. a reaction "
        "set's LHHW/POWERLAW) — it identifies what kind of thing was configured. If this "
        "block type has a doc under docs/blocks/, append to <ASPEN_USER_DATA>/blocks/<type>.md; "
        "otherwise create <ASPEN_USER_DATA>/learned/<type>.md and add it to that folder's "
        "index.md (observation-knowledge-extraction skill, step 6).")
    return header + "\n" + "\n".join(lines) + next_step
