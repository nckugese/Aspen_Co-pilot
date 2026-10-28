"""Measurements around a call that changes a model: what a structure, run, file or
session tool did, read from Aspen before and after the call -- a record says what happened,
not what the tool's answer claims. Value writes are measured by the recorder's hook in
``AspenPlusManager.set_node_value``; this measures the rest.

The ``probe`` column of ``intercept.TOOLS`` drives it; parts join with ``+``, and ``{arg}``
in a path is that argument of the call (or of the batch item):

    kid:<path>       one element the arguments name (``NAME!TYPE``: NAME), there or not before
                     and after: an ``add`` or ``remove`` record (target kind from its folder:
                     block, stream, component, rxnset, reaction, chemistry; else element) with
                     its type (a component also its ``aname``, the name it was added by); a
                     removed block keeps its connections in ``before``
    row:<path>       the same for a table row (kind ``row``)
    kids:<folder>    every child of a folder by name, for a call that does not name what it
                     adds (an ``add`` / ``remove`` per element); rows:<table> the same for rows
    port             the streams on the block's port: one ``connect``, ``before`` / ``after``
                     stream lists, ``displaced`` the streams the call took off the port, and
                     ``moved_from`` {block, port}: the end the stream itself was on before and
                     is not after -- V15 moves a connected stream to the new port rather than
                     refusing, so an undo can put it back; {} it moved
                     off none; left out when its ends could not be read. A connect that left
                     the port as it was but the stream off its old port (V15 refusing a stream
                     into the block at its other end) records that detach instead,
                     as a disconnect of the old port (``detached``, ``asked``), then the call's
                     failed record
    run, run:reinit  one ``run`` / ``reinit``: status ok | warn | error (Aspen's run status and
                     the blocks it lists as completed with errors or warnings), refused |
                     failed (the run did not happen), error / warning counts, ``blocks``, ``secs``,
                     ``msgs`` (the run status's lines); a run that ran also ``seq``, ``inputs``
                     and ``delta`` (tools/runlog.py: a result fingerprint read before and after);
                     one that ended in errors ``first_error`` (``first_error``: its first error's
                     block, words and failure kind, taken before ``result`` is cut); one that
                     ended in warnings ``first_warn`` / ``warns_more`` (``run_warnings``: a line
                     Aspen writes after every clean run, "... was never executed", is not one)
    sess             the open sessions: ``open`` / ``close`` records with ``file`` and the model
    file             the call's checkpoint events (the recorder makes them one ``save`` record);
                     with ``sess`` that record is a ``patch`` saying whether it ``reopened``
    args:<path>      the node the arguments name, read before and after: one ``value`` record
    hook, hook:attr  the value hook records it; nothing here.  sum, prog: not a probe's job

Every changing call leaves at least one record: when nothing was measured, an ``unchanged``
one -- ``failed`` when the tool's answer says it did not do it -- with the arguments and the
answer (op ``call``). A batch (``intercept.each``) is measured item by item, each item its own.

Cost (live V15, hidden): nothing outside a recording scope (``ASPEN_MCP_JOURNAL=0`` opens
none). Inside one, a lookup by path is ~1 ms, so a named element costs one before and one
after, where listing a folder costs ~0.5 ms a child (hence ``kid`` wherever the arguments
name the element; in a batch a folder's list after one item is the next one's before). Also
a port's streams and the ends of the stream a connect names (its own Connections, never every
block's), the run status -- taken from main_tools, which read it for the tool's own
answer (``saw_status``), so a run's status costs no COM read here (its result fingerprint does:
tools/runlog.py, within 40 ms and 5% of the run); the blocks come from the lists in it, never
one read per block -- and one liveness check per open session. Aspen names are case-sensitive to
FindNode and uppercase by construction, so a name looked up as given is exact. Nothing
raises into the tool: a read that fails leaves that measurement out.
Stdlib only (tools/diagnose for a failure's kind: it imports this module back, both only
use each other at call time), no I/O; COM only through the manager's apps.
"""
from __future__ import annotations

import collections
import functools
import logging
import re
import time
import weakref

from tools import diagnose, dispid, journal, knowledge_tools, recorder, runlog

logger = logging.getLogger(__name__)

_perf = time.perf_counter
LIST_MAX = 50                      # records per folder per call, blocks in a run record
MSGS_MAX, MSG_WIDTH = 20, 200      # run-status lines a run record keeps, characters of each
FE_LINES, FE_WIDTH, FE_NAME = 3, 160, 64   # a run record's first_error: lines, characters of each, of its block
RUN_STATUS = r"\Data\Results Summary\Run-Status\Output\PER_ERROR"
_ORDER = {"sess": 0, "file": 2}    # after the call: sessions first (a patch asks), file last
_TREE = frozenset({"kid", "row", "kids", "rows", "port", "args"})     # parts that read the tree
_APP = _TREE | {"run"}                                                # parts that need the app after
_NOT_NAMES = frozenset({"session_name", "aspen_path", "reason"})
# A batch item as the arguments of the single call it stands for (server.py's batch loops).
_ITEM = {"blocks": {"name": "block_name", "type": "block_type"},
         "streams": {"name": "stream_name", "type": "stream_type"},
         "connections": {"block": "block_name", "stream": "stream_name", "port": "port_name"},
         "components": "component_id"}
# The tool's answer says it did not do it: how it starts, or words in it.
_FAILED = re.compile(r"^\s*(error|failed|cannot|could not|no active|no reactions|node not found|unknown|"
                     r"refused|not applied|layout not done|nothing to set|nothing patched)\b"
                     r"|not enterable|does not fit|already exists|not found|out of range|\bfailed\b", re.I)


def failed(result) -> bool:
    """The first line of a tool's answer says it did not do what it was asked."""
    return bool(_FAILED.search(str(result or "").split("\n", 1)[0]))


@functools.lru_cache(maxsize=None)
def parse(probe: str | None) -> tuple:
    """A TOOLS ``probe`` -> ((kind, param or None), ...), sessions first and the file last."""
    parts = []
    for p in (probe or "").split("+"):
        if p:
            kind, _, param = p.partition(":")
            parts.append((kind, param or None))
    return tuple(sorted(parts, key=lambda kp: _ORDER.get(kp[0], 1)))


# ---------------------------------------------------------------------------- COM reads
# ``tree`` below is the app's Tree, taken once per measuring phase.
def _tree(app):
    try:
        return app.Tree if app is not None else None
    except Exception:
        return None


def _find(tree, path):
    try:
        return tree.FindNode(path)
    except Exception:
        return None


def _fault(exc, fault) -> None:
    """A read here that raised: Aspen's internal fault (knowledge_tools.server_fault) is not passed
    by -- ``fault(exc)`` flags the session (the caller's manager.note_fault) and the read stops
    there, or, with no ``fault``, it is raised: to a Probe's part, which flags it
    (``Probe._noted``), or to a tool's own handler, whose answer intercept flags. Any other
    error: nothing (the read is None, as before)."""
    if knowledge_tools.server_fault(exc):
        if fault is None:
            raise exc
        fault(exc)


def _names(node, fault=None) -> list | None:
    """The names of a node's children in order; None when it has no readable children. Listed
    by the node's enumerator: ``rows:{aspen_path}`` reads any table a call names, and Item(i)
    faults Aspen on some label-keyed ones (knowledge_tools._children). Aspen's internal fault:
    ``_fault``."""
    if node is None:
        return None
    try:
        return [str(dispid.get(c, "Name")) for c in knowledge_tools._children(node.Elements) if c is not None]
    except Exception as exc:
        _fault(exc, fault)
        return None


def _values(node, fault=None) -> list | None:
    """The values of a node's children (a message list, a block's reaction sets); None when
    unreadable. Listed by the enumerator as ``_names`` is; Aspen's internal fault: ``_fault``."""
    if node is None:
        return None
    try:
        return [dispid.get(c, "Value") if c is not None else None for c in knowledge_tools._children(node.Elements)]
    except Exception as exc:
        _fault(exc, fault)
        return None


def _type(node) -> str | None:
    """An element's type: its RECORDTYPE (a block's RadFrac, a set's POWERLAW), else a string
    value (a component's CONV, a reaction's KINETIC)."""
    for how in (("AttributeValue", 6), ("Value",)):
        try:
            v = dispid.get(node, *how)
        except Exception:
            continue
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _details(tree, folder, name, node, fault=None) -> dict:
    """What a removal would take with it: the element's type; a block's connections
    {stream: port} -- its Connections listed by the enumerator (Item(i) there can fault V15,
    tools/undo_apply) --; a component's ``aname`` (``_aname``). Aspen's internal fault: ``_fault``
    (with ``fault``, the connections read so far)."""
    d = {"type": _type(node)}
    if _kind(folder, "") == "component":
        d["aname"] = _aname(tree, name)
    if _kind(folder, "") == "block":
        conn = _find(tree, rf"{folder}\{name}\Connections")
        if conn is not None:
            d["connections"] = {}
            try:
                for c in knowledge_tools._children(conn.Elements):
                    if c is not None:
                        d["connections"][str(dispid.get(c, "Name"))] = str(dispid.get(c, "Value") or "")
            except Exception as exc:
                _fault(exc, fault)
    return d


def _aname(tree, label) -> str | None:
    """A component's name as it was given -- a replay adds it again by that name: its databank
    name (DBNAME: ETHYL-ACETATE for the label ETHYLACE that add_component made of it), else its
    ANAME -- which V15 turns into the formula alias once it resolves the name (C4H8O2-3), so only
    a name Aspen did not resolve is still there; None when neither is."""
    for folder in ("DBNAME", "ANAME"):
        v = _values_of(_find(tree, rf"\Data\Components\Specifications\Input\{folder}\{label}"))
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _values_of(node):
    try:
        return dispid.get(node, "Value") if node is not None else None
    except Exception:
        return None


def _kind(folder: str, default: str) -> str:
    p = folder.rstrip("\\").casefold()
    if p in (r"\data\blocks", r"\data\streams"):
        return p.rsplit("\\", 1)[1][:-1]
    if p.endswith(r"\components\specifications\input\type"):
        return "component"
    if p == r"\data\reactions\reactions":
        return "rxnset"
    if p == r"\data\reactions\chemistry":
        return "chemistry"
    if p.endswith(r"\input\reactype"):
        return "reaction"
    return default


def _minus(a, b) -> list:
    """The names of ``a`` not in ``b``, as multisets (rows may share a label), in a's order."""
    left, out = collections.Counter(b), []
    for x in a:
        if left[x]:
            left[x] -= 1
        else:
            out.append(x)
    return out


_ARG = re.compile(r"\{(\w+)\}")


def _fill(template: str, a: dict, element: bool = False) -> str:
    """``{arg}`` replaced by that argument (KeyError when the call did not give it);
    ``element``: the last segment is a name, ``NAME!TYPE`` stands for NAME."""
    def sub(m):
        v = a.get(m.group(1))
        if v is None:
            raise KeyError(m.group(1))
        return str(v)
    path = re.sub(r"\\{2,}", r"\\", _ARG.sub(sub, template)).rstrip("\\")   # aspen_path given as "...\"
    if element:
        folder, _, name = path.rpartition("\\")
        path = f"{folder}\\{name.split('!', 1)[0]}"
    return path


def _el(tree, path):
    """(path, node) of the element ``path`` names: as given, else with its name upper-cased --
    the tools upper-case block and stream names (flowsheet_tools.aspen_name), FindNode is
    exact-case. The path as given when neither is there."""
    node = _find(tree, path)
    if node is None:
        folder, _, name = path.rpartition("\\")
        if name != name.upper():
            up = _find(tree, f"{folder}\\{name.upper()}")
            if up is not None:
                return f"{folder}\\{name.upper()}", up
    return path, node


def _block(tree, block):
    """A block's name as Aspen has it: as given, else upper-cased (as the tools do)."""
    if block and str(block) != str(block).upper() and _find(tree, rf"\Data\Blocks\{block}") is None:
        return str(block).upper()
    return block


def _port(tree, block, port, fault=None):
    """(the port's name as Aspen has it, its node) on a block; the name matched as the tool
    resolves it (exactly, else ignoring case). ``fault``: ``_names``'."""
    base = rf"\Data\Blocks\{_block(tree, block)}\Ports"
    node = _find(tree, f"{base}\\{port}")
    if node is None:
        want = str(port).upper()
        hit = next((n for n in _names(_find(tree, base), fault) or () if n.upper() == want), None)
        if hit is not None:
            port, node = hit, _find(tree, f"{base}\\{hit}")
    return port, node


def _ends(tree, stream, fault=None) -> tuple:
    """(the stream's name as Aspen has it, [(block, port)] it is connected to -- None when that
    cannot be read). The stream's own Connections has a row per end named by the block (``#n``:
    no block there) -- V15 -- and the block's Connections the port: ~3.5 ms live, whatever the
    flowsheet's size, where reading every block's grows with it (13 blocks: 9 ms). ``fault``:
    ``_names``' (the ends then unknown)."""
    if not stream:
        return stream, None
    name, conn = str(stream), _find(tree, rf"\Data\Streams\{stream}\Connections")
    if conn is None and name != name.upper():
        name, conn = name.upper(), _find(tree, rf"\Data\Streams\{name.upper()}\Connections")
    names = _names(conn, fault)
    if names is None:
        return name, None
    out = []
    for block in names:
        c = None if block.startswith("#") else _find(tree, rf"\Data\Blocks\{block}\Connections\{name}")
        if c is not None:
            try:
                out.append((block, str(dispid.get(c, "Value"))))
            except Exception:
                return name, None
    return name, out


def _left(tree, stream, ends, block, port) -> dict | None:
    """Of the stream's ends before a connect to block/port, the one it is no longer on:
    {"block", "port"}; {} when it left none (or had none); None when that is not known (its
    ends could not be read) -- a record without the field."""
    if ends is None:
        return None
    for b, p in ends:
        if b.upper() == str(block).upper() and p.upper() == str(port).upper():
            continue
        c = _find(tree, rf"\Data\Blocks\{b}\Connections\{stream}")
        try:
            if c is None or str(dispid.get(c, "Value")) != p:
                return {"block": b, "port": p}
        except Exception:
            return None
    return {}


# ---------------------------------------------------------------------------- runs
# The head of one of Aspen's messages ("*  WARNING", "**  ERROR", "***SEVERE ERROR", a "***"
# banner, "INFORMATION IN ..."); _QUIET: the heads of those that do not fail a run.
_MSG_HEAD = re.compile(r"^\s*(\*|INFORMATION\b)")
_QUIET = re.compile(r"^\s*(\*+\s*WARNING|INFORMATION)\b")


def run_failed(text) -> bool:
    """Whether Aspen's run status (its Run-Status lines, one per line, as Aspen cased them) says
    the run failed: "failed", or "error" other than "0 errors" -- read outside WARNING and
    INFORMATION messages, whose own words ("THE ABSOLUTE ERROR IS 0.10000E-01") are not the
    outcome. A message is its head and the upper-case lines under it: Aspen's engine writes
    messages in capitals, the Run-Status lines around them ("The following Unit Operation blocks
    were", "completed with errors:") are sentence case; a blank line or a new head ends it too.
    Lowered text (its case lost) gets the plain substring test."""
    kept, quiet = [], False
    for line in str(text or "").splitlines():
        if _MSG_HEAD.match(line):
            quiet = bool(_QUIET.match(line))
        elif not line.strip() or line != line.upper():
            quiet = False
        if not quiet:
            kept.append(line)
    s = "\n".join(kept).lower()
    return "failed" in s or ("error" in s and "0 errors" not in s)


# The Run-Status lines main_tools read last (its answer quotes them), so the journal's run
# record and the window's take them from there instead of reading them again: {"app": a weak
# reference to the app (or its id), "t": perf_counter time of the read, "lines"}.
_SEEN: dict = {"app": None, "t": None, "lines": None}


def _ref(app):
    try:
        return weakref.ref(app)
    except TypeError:
        return id(app)


def _is(ref, app) -> bool:
    return (ref() is app) if isinstance(ref, weakref.ref) else (ref is not None and ref == id(app))


def saw_status(app, values) -> None:
    """main_tools just read ``app``'s Run-Status lines after a run (``values`` as Aspen gives
    them, blank lines kept): kept for ``status_lines``. No COM."""
    try:
        _SEEN.update(app=_ref(app), t=_perf(), lines=list(values))
    except Exception:
        pass


def status_lines(app, since: float | None = None, read: bool = True, fault=None) -> list | None:
    """The Run-Status PER_ERROR values of ``app``'s last run, blank lines kept: those main_tools
    read (``saw_status``) at or after ``since`` (a time.perf_counter time), else read now --
    one FindNode and a read per line -- unless ``read`` is False. None: unreadable (or, not
    reading, not seen since then). Aspen's internal fault reading them: ``_fault``."""
    if app is not None and since is not None and _SEEN["t"] is not None and _SEEN["t"] >= since \
            and _is(_SEEN["app"], app):
        return list(_SEEN["lines"])
    if not read or app is None:
        return None
    tree = _tree(app)
    return _values(_find(tree, RUN_STATUS), fault) if tree is not None else None


_INFO = re.compile(r"^\s*INFORMATION\b")


def messages(values, cap: int | None = MSGS_MAX) -> list[str]:
    """Run-Status values as the lines people read: stripped, blank ones left out, each at most
    MSG_WIDTH characters; at most ``cap`` (None: all) -- when there are more, Aspen's
    INFORMATION messages (head and body, e.g. "MW ENTERED FOR COMPONENT ... IS DIFFERENT")
    are left out first, then the last lines."""
    lines = ["" if v is None else str(v) for v in values or ()]
    out = [s.strip()[:MSG_WIDTH] for s in lines if s.strip()]
    if cap is None or len(out) <= cap:
        return out
    kept, info = [], False
    for line in lines:
        if _MSG_HEAD.match(line):
            info = bool(_INFO.match(line))
        elif not line.strip() or line != line.upper():
            info = False
        if not info and line.strip():
            kept.append(line.strip()[:MSG_WIDTH])
    return kept[:cap]


def run_msgs(values) -> dict:
    """A run's ``msgs`` (``messages``) and, when that is not all of them, ``nmsgs`` (how many
    lines Aspen gave); {} when its run status says nothing."""
    n = sum(1 for v in values or () if v is not None and str(v).strip())
    if not n:
        return {}
    out = {"msgs": messages(values)}
    if n > len(out["msgs"]):
        out["nmsgs"] = n
    return out


_LIST_HEAD = re.compile(r"\bunit operation blocks were\b", re.I)
_LIST_LEVEL = re.compile(r"\bcompleted with (errors|warnings)\s*:", re.I)


def _is_names(raw, s) -> bool:
    """A line of block / stream names under a list's head: upper case, not a message, no colon."""
    return bool(s) and s == s.upper() and not _MSG_HEAD.match(raw) and not s.endswith(":")


def _list_level(s) -> tuple:
    """(error | warn, the names after its colon) of a list head's line that says its level --
    "completed with errors:" / "... warnings:" / "never executed:" (a warning); (None, "") else."""
    m = _W_LEVEL.search(s)
    if m is None:
        return None, ""
    return ("error" if (m.group(1) or "").lower() == "errors" else "warn"), s[m.end():].strip()


def listed_blocks(values) -> dict:
    """{block: "error" | "warn"}: the blocks Aspen's run status names under "The following Unit
    Operation blocks were / completed with errors: / B1  B2" (or warnings, or "never executed:",
    a warning too; the head on one line or two, the names after its colon or on the lines after
    it until a blank line or a line that is not a list of upper-case names). A block in both
    lists is an error."""
    out, level, head = {}, None, False

    def add(names):
        for name in names.split():
            if level == "error" or name not in out:
                out[name] = level
    for raw in values or ():
        line = "" if raw is None else str(raw)
        s = line.strip()
        if _LIST_HEAD.search(s) or head:           # a head, or its second line
            level, rest = _list_level(s)
            head = level is None and not head
            if level is not None and _is_names(rest, rest):
                add(rest)
            continue
        if level is not None and _is_names(line, s):
            add(s)
            continue
        level = None
    return out


# A run answer's sections (main_tools.run_simulation: "Block errors:" -- "  B1: BLKMSG" and its
# PER_ERROR lines, indented deeper -- and "Loop convergence summary:" -- "  C-1: STATUS in N
# iterations | ..."), any "The following ... blocks were / completed with errors:" list (Unit
# Operation, Convergence), an Aspen message's "*..." head, and a head that says nothing more.
_SECTIONS = ("Block errors:", "Loop convergence summary:")
_ENTRY = re.compile(r"^ {2}(\S+?):(?:\s(.*))?$")
_ANY_LIST = re.compile(r"\bblocks were\b", re.I)
_STAR = re.compile(r"^\s*\*")
_BARE = re.compile(r"^\*+\s*(?:SEVERE\s+)?(?:ERROR|WARNING)S?\s*$", re.I)


def _entries(result) -> dict:
    """{NAME: [its lines]} of a run answer's "Block errors:" and "Loop convergence summary:"."""
    out, on, cur = {}, False, None
    for raw in str(result or "").splitlines():
        if raw and not raw[0].isspace():
            on, cur = raw.strip() in _SECTIONS, None
            continue
        if not on:
            continue
        m = _ENTRY.match(raw)
        if m:
            cur = out.setdefault(m.group(1).upper(), [])
            first = (m.group(2) or "").split(" | ", 1)[0].strip()
            if first:
                cur.append(first)
        elif cur is not None and raw.strip():
            cur.append(raw.strip())
    return out


def _error_lists(values) -> list:
    """[(NAME, the list's head)]: the blocks Run-Status lists as "completed with errors" under any
    "The following ... blocks were" head (Unit Operation, Convergence), in order."""
    out, head, level = [], "", None
    for raw in values or ():
        s = " ".join(str(raw).split())
        if _ANY_LIST.search(s):
            m = _LIST_LEVEL.search(s)
            head, level = s, (m.group(1).lower() if m else None)
            continue
        m = _LIST_LEVEL.search(s)
        if head and level is None and m:
            head, level = f"{head} {s}", m.group(1).lower()
            continue
        if level == "errors" and s and s == s.upper() and not _STAR.match(s) and not s.endswith(":"):
            out += [(n, head) for n in s.split()]
            continue
        head, level = "", None
    return out


def _error_msgs(values) -> list:
    """Aspen's ERROR messages among Run-Status lines: [[head, the upper-case lines under it]]."""
    out, cur = [], None
    for raw in values or ():
        s = " ".join(str(raw).split())
        if _STAR.match(s):
            cur = [s] if "ERROR" in s.upper() else None
            if cur is not None:
                out.append(cur)
        elif cur is not None and s and s == s.upper():
            cur.append(s)
        else:
            cur = None
    return out


def _mentions(lines, block) -> bool:
    b = str(block or "").upper()
    return bool(b) and any(re.search(rf"(?<![\w-]){re.escape(b)}(?![\w-])", str(x).upper()) for x in lines)


def _says(line, kind) -> bool:
    return bool(kind) and kind in diagnose.mechanisms(line, limit=len(diagnose.EXPLAIN))


def first_error(result, values=None, levels=None) -> dict | None:
    """A failed run's first error, from the whole run answer (``result``, before the journal cuts
    it to RESULT_MAX: a long run status pushes "Block errors:" past it) and its Run-Status lines
    (``values``): {"block", "lines", "kind"}, each only when known, None when nothing is.

    block: the first block the status lists in errors (``levels``, else ``listed_blocks``: Unit
    Operation blocks, then Convergence blocks) whose words the answer kept, else the first listed,
    else the first "Block errors:" entry saying ERROR; lines: its lines in the answer, else Aspen's
    ERROR message naming it in the status (the first such message when no block is named) --
    whitespace collapsed, bare "***SEVERE ERROR" heads left out, at most FE_LINES of FE_WIDTH,
    the line naming ``kind`` always kept; kind: the first failure kind tools/diagnose names in all
    of them (else in the list's head: a Convergence block's is a recycle loop, "tear")."""
    try:
        ent, listed = _entries(result), _error_lists(values)
        levels = levels if isinstance(levels, dict) else listed_blocks(values)

        def pick(names):
            return next((b for b in names if ent.get(b.upper())), None) or (names[0] if names else None)
        block = pick([str(b) for b, lv in levels.items() if lv == "error"]) or \
            pick([n for n, _ in listed if n not in levels]) or next(iter(levels), None) or \
            next((n for n, ls in ent.items() if any("ERROR" in x.upper() for x in ls)), None)
        lines = ent.get(str(block).upper()) if block else None
        if not lines:
            said = _error_msgs(values)
            lines = next((m for m in said if _mentions(m, block)), None) or (said[0] if said and not block else None)
        lines = [s for s in (" ".join(str(x).split()) for x in lines or ()) if s]
        mechs = diagnose.mechanisms(" ".join(lines)) if lines else []
        if not mechs and block:
            mechs = diagnose.mechanisms(next((h for n, h in listed if n == block), ""))
        kind = mechs[0] if mechs else None
        kept = [x for x in lines if not _BARE.match(x)] or lines
        named = next((x for x in kept if _says(x, kind)), None)
        if named is not None and named not in kept[:FE_LINES]:
            kept = kept[:FE_LINES - 1] + [named]
        out = {"block": str(block)[:FE_NAME] if block else None, "lines": [x[:FE_WIDTH] for x in kept[:FE_LINES]],
               "kind": kind}
        return {k: v for k, v in out.items() if v} or None
    except Exception as exc:
        logger.debug("probes: first error not read (%r)", exc)
        return None


# A run's warnings, by the Run-Status heads Aspen words them with (sentence case; short fragments,
# matched without case): a list of blocks "The following <kind> blocks were / completed with
# warnings:" (or "never executed:", with names under it), "Warnings occurred in Flash calculations
# / for the following Tear streams:", the "*  WARNING" messages under "The following messages were
# issued during Input Translation:" (or Calculations:), "Properties estimation was completed with
# warnings". Not warnings: a one-line "... was never executed" (a step the model does not use,
# many clean runs say it of properties estimation), INFORMATION messages, an empty list.
_W_LIST = re.compile(r"\bthe following (.*?)\s*blocks were\b", re.I)
_W_LEVEL = re.compile(r"\b(?:completed with (errors|warnings)|(never executed))\s*:", re.I)
_W_FLASH = re.compile(r"\b(warnings|errors) occurred in flash calculations\b", re.I)
_W_STREAMS = re.compile(r"\bstreams\s*:", re.I)
_W_ISSUED = re.compile(r"\bmessages were issued during (.*?)\s*:?\s*$", re.I)
_W_PROP = re.compile(r"\bproperties estimation was completed with warnings\b", re.I)
_W_NEVER = re.compile(r"\bwas never executed\b", re.I)
_W_MSG = re.compile(r"^\s*\*+\s*WARNING\b", re.I)
_W_WORD = re.compile(r"warn", re.I)
# Where the window shows each kind: blk a block's results, conv the convergence results, cp the
# control panel's messages, rs the run status.
WARN_WHERE = {"block": "blk", "conv": "conv", "flash": "cp", "input": "cp", "calc": "cp", "prop": "rs",
              "other": "rs"}
WARN_OBJS, WARN_MORE, WARN_WIDTH = 20, 3, 200   # a warning's objects, the others a record keeps, its line


def _list_entry(kind, what, head):
    """A list's (or a Flash head's) entry once its head is whole -- the names under it go in its
    ``objs`` -- or False for a Flash head of errors (its names are read past: run_failed's)."""
    if kind == "list":
        w = str(what).lower()
        kind = "block" if "unit operation" in w else "conv" if "convergence" in w else "other"
    elif kind != "flash":
        return False
    return {"kind": kind, "objs": [], "where": WARN_WHERE[kind], "line": " ".join(head.split())[:WARN_WIDTH]}


def run_warnings(values) -> list[dict]:
    """The warnings among Run-Status lines (``values``, blank lines kept or not), in order:
    [{"kind": block | conv | flash | input | calc | prop | other, "objs": the names Aspen lists
    (blocks, streams; [] for a message), "where": WARN_WHERE[kind], "line": Aspen's words for it
    (a list's head and names on one line; a message's head and first lines; at most WARN_WIDTH),
    "n" (input / calc: the WARNING messages under that "issued during" head, one entry)}]. A list
    of another kind of block (Calculator, ...) is ``other``; an empty list is none. Errors are
    not here: run_failed."""
    out, pend, names, para, sect, sect_w = [], None, None, None, "", None

    def head_done(kind, what, head, s):
        """The list whose head ends in ``s`` (its level, or a Flash head's "streams:"): its entry
        (False: errors) and the names after the colon; None: ``s`` does not end one."""
        if kind == "list":
            lv, rest = _list_level(s)
            if lv is None:
                return None
            e = False if lv == "error" else _list_entry(kind, what, head)
        else:
            m = _W_STREAMS.search(s)
            if m is None:
                return None
            e, rest = _list_entry(kind, what, head), s[m.end():].strip()
        if e is not False and rest and _is_names(rest, rest):
            add(e, rest)
        return e

    def add(e, s):
        if not e["objs"]:
            out.append(e)
            e["head"] = e["line"]
        e["objs"] = (e["objs"] + s.split())[:WARN_OBJS]
        e["line"] = f"{e['head']} {' '.join(e['objs'])}"[:WARN_WIDTH]

    for raw in values or ():
        raw = "" if raw is None else str(raw)
        s = " ".join(raw.split())
        if not s:
            pend = names = para = None
            continue
        if pend is not None:                      # a head's second line
            kind, what, head = pend
            pend = None
            e = head_done(kind, what, f"{head} {s}".split(":")[0] + ":", s)
            if e is not None:
                names = e
                continue
        if names is not None:                     # the names under a list's head
            if _is_names(raw, s):
                if names is not False:
                    add(names, s)
                continue
            names = None
        m = _W_LIST.search(s) or _W_FLASH.search(s)
        if m:
            para = None
            kind = "list" if m.re is _W_LIST else "flash" if m.group(1).lower() == "warnings" else "flash_errors"
            what = m.group(1) if kind == "list" else s
            e = head_done(kind, what, s.split(":")[0] + ":", s)
            if e is None:
                pend = (kind, what, s)
            else:
                names = e
            continue
        m = _W_ISSUED.search(s)
        if m:
            para, sect, sect_w = None, m.group(1).lower(), None
            continue
        if _MSG_HEAD.match(raw):                  # a message: WARNING, INFORMATION, an ERROR, a banner
            para = False                          # (its body is read past)
            if _W_MSG.match(raw):
                if sect_w is None:
                    kind = "input" if "input" in sect else "calc"
                    sect_w = {"kind": kind, "objs": [], "where": WARN_WHERE[kind], "line": s, "n": 0}
                    out.append(sect_w)
                    para = sect_w                 # the first one's words: its head and first lines
                sect_w["n"] += 1
            continue
        if para is not None and s == s.upper():   # a message's body
            if para is not False and para["line"].count("\n") < 2:
                para["line"] += "\n" + s
            continue
        para = None
        if _W_PROP.search(s):
            out.append({"kind": "prop", "objs": [], "where": WARN_WHERE["prop"], "line": s[:WARN_WIDTH]})
        elif _W_WORD.search(s) and not _W_NEVER.search(s):
            out.append({"kind": "other", "objs": [], "where": WARN_WHERE["other"], "line": s[:WARN_WIDTH]})
    for e in out:
        e.pop("head", None)
        e["line"] = " ".join(e["line"].split())[:WARN_WIDTH]
    return out


def run_warning(values) -> dict | None:
    """The first of ``run_warnings``: {"kind", "objs", "where", "line"(, "n")}; None: none."""
    w = run_warnings(values)
    return w[0] if w else None


def run_state(app, blocks: bool = True, lines=None, fault=None) -> dict:
    """How Aspen says its last run ended: ``status`` ok | warn | error | unknown (the run
    status unreadable) -- error by ``run_failed`` and the blocks the status lists in errors
    (``listed_blocks``), warn by the warnings it lists (``run_warnings``: a line that is only
    neutral, "Properties estimation was never executed", or an INFORMATION message, is ok);
    after a run that did not end cleanly ``errors`` / ``warnings`` (blocks) and ``blocks``
    {name: level} (at most LIST_MAX), after a warn ``first_warn`` (``run_warning``) and
    ``warns_more`` (the next WARN_MORE warnings, when there are), and ``msgs`` / ``nmsgs``
    (``run_msgs``) whenever the status says anything. ``lines``: the Run-Status values already
    read (``status_lines``, ``said_lines``), else they are read here. ``blocks=False``: the
    status alone (a loop's run). No block is read either way. Aspen's internal fault reading the
    status: ``_fault`` (``fault``: flagged, the status unknown)."""
    if lines is None:
        tree = _tree(app)
        lines = _values(_find(tree, RUN_STATUS), fault) if tree is not None else None
    if lines is None:
        return {"status": "unknown"}
    raw = "\n".join(str(v) for v in lines if v is not None)
    if not raw.strip():
        return {"status": "ok"}
    levels = listed_blocks(lines)
    errs = sum(v == "error" for v in levels.values())
    warns = run_warnings(lines)
    status = "error" if errs or run_failed(raw) else "warn" if levels or warns else "ok"
    out = {"status": status}
    if blocks:
        if status != "ok":
            out.update(errors=errs, warnings=len(levels) - errs)
            if levels:
                out["blocks"] = dict(list(levels.items())[:LIST_MAX])
        if status == "warn" and warns:
            out["first_warn"] = warns[0]
            if len(warns) > 1:
                out["warns_more"] = warns[1:1 + WARN_MORE]
        out.update(run_msgs(lines))
    return out


# main_tools._check_run_status's answer when the run status could not be read.
UNREADABLE = "Warning: could not read run status"
# main_tools._why_not_run's head over the errors a run's history file gained, one per line after it.
HIS_HEAD = "Aspen's history file ("


def his_errors(text) -> list[str]:
    """The history-file error lines a run answer quotes (main_tools._why_not_run): [] when none."""
    s = str(text or "")
    i = s.find(HIS_HEAD)
    if i < 0:
        return []
    body = s[i:].split("\n", 1)[1] if "\n" in s[i:] else ""
    out = []
    for line in body.split("\n"):
        if not line.startswith("  ") or line.lstrip().startswith("(+"):
            break
        out.append(line.strip())
    return [x for x in out if "ERROR" in x.upper()]


def said_lines(app, text, since: float | None = None) -> list | None:
    """The Run-Status lines a run's answer was made from: those main_tools read for it (``saw_status``
    at or after ``since``), else the lines of the answer's "Run status message:" (``text``:
    main_tools._check_run_status's answer or the whole run answer; one without those lines: []).
    None: the status could not be read. No COM."""
    if app is not None and since is not None:
        seen = status_lines(app, since, read=False)
        if seen is not None:
            return seen
    s = str(text or "")
    if UNREADABLE in s:
        return None
    i = s.find("Run status message:")
    if i < 0:
        return []
    body = s[i + len("Run status message:"):].lstrip("\n").split("\n\n", 1)[0]
    return [x.strip() for x in body.splitlines() if x.strip()]


def run_fields(app, result, op: str = "run", blocks: bool = True, since: float | None = None,
               fault=None) -> dict:
    """The fields of a ``run`` / ``reinit`` record: refused / failed by the tool's answer when
    the run did not happen, else what ``run_state`` measures -- on the run status main_tools
    read at or after ``since`` (``status_lines``) when it did; with no run status, error when
    the answer quotes errors from the history file (``his_errors``; ``via_his``, their lines the
    ``first_error``) -- and, when it ended in errors, ``first_error`` from the whole answer
    (``result`` itself is kept cut). ``fault``: Aspen's
    internal fault reading the status flags the session there and the status is unknown."""
    res = str(result or "")
    if op == "reinit":
        out = {"status": "ok" if res.rstrip().endswith("reinitialized.") else
               "refused" if res.startswith("Cannot") else "failed"}
    elif res.startswith("Cannot run"):
        out = {"status": "refused"}
    elif "run completed" not in res or app is None:
        out = {"status": "failed"}
    else:
        lines = status_lines(app, since, read=UNREADABLE not in res, fault=fault)   # (the answer's own verdict)
        out = run_state(app, blocks=blocks, lines=lines) if lines is not None else {"status": "unknown"}
        his = his_errors(res) if out["status"] == "unknown" else []
        if his:                                   # no run status, but the history file says the run failed
            out = {"status": "error", "via_his": True}
            if blocks:
                out["first_error"] = {"lines": [x[:FE_WIDTH] for x in his[:FE_LINES]]}
        elif blocks and out["status"] == "error":
            fe = first_error(res, lines, out.get("blocks") or {})
            if fe:
                out["first_error"] = fe
    if out["status"] != "ok" and res:
        out["result"] = res[:journal.RESULT_MAX]
    return out


def run_entry(manager, session, result, op: str = "run", secs: float | None = None, scope=None,
              since: float | None = None, fp=None):
    """Record a run or reinit someone made outside a probed call (a workbench program's run
    step): into ``scope`` (default: the current one); in a loop's Aggregate only its status
    counts. ``since``: when the run started (time.perf_counter; default now - ``secs``), so
    the run status main_tools read for it is used, not read again. ``fp``: what
    ``runlog.before_run`` took before it (seq, inputs, delta). Never raises; returns the
    record's fields (None: no scope)."""
    s = scope if scope is not None else recorder.current()
    if s is None or not getattr(s, "on", False):
        return None
    t = _perf()
    if since is None and secs is not None:
        since = t - secs
    try:
        app = manager.get_app(session) if manager is not None and session else None
        f = run_fields(app, result, op, blocks=not isinstance(s, recorder.Aggregate), since=since,
                       fault=_noter(manager, session, op))
        if secs is not None:
            f["secs"] = round(secs, 2)
        runlog.after_run(fp, manager, f)
        s.add(op, session=session, **f)
        return f
    except Exception as exc:
        logger.warning("probes: %s of %s not recorded (%r)", op, session, exc)
        return None
    finally:
        s.jt += _perf() - t


def _noter(manager, session, tool):
    """A read's ``fault``: Aspen's internal fault flags ``session`` (manager.note_fault; with no
    session named, the only open one); None when the manager keeps no such flag."""
    note = getattr(manager, "note_fault", None)
    if note is None:
        return None

    def noted(exc):
        try:
            note(session, exc, tool=tool)
        except Exception as e:                   # never into the call it measures
            logger.warning("probes: fault of %s not flagged (%r)", session, e)
    return noted


# ---------------------------------------------------------------------------- sessions
def _sessions(m) -> dict:
    """{name: (model id, weak reference to its app, file)}: weak, so a closed Aspen's proxy is
    not kept alive through a close and reopen."""
    out = {}
    for name in m.session_names():
        app = m.get_app(name)
        try:
            ref = weakref.ref(app) if app is not None else None
        except TypeError:
            ref = None
        out[name] = (m.model_id(name), ref, m.session_file(name))
    return out


# ---------------------------------------------------------------------------- the probe
class Probe:
    """One call's measurements. ``before()`` / ``after(result)`` around the whole call; for a
    batch (``batch``: the parameter ``intercept.each`` loops over) ``enter(item)`` /
    ``leave(args, result)`` around each item instead, and ``done(result)`` at the end.
    ``describe(args) -> (target, args summary)`` for an at-least-one record; ``fallback``
    False: none (a config tool that records only a net change). Never raises."""

    def __init__(self, manager, scope, tool, probe, args, batch=None, fallback=True, describe=None):
        self.m, self.scope, self.tool, self.args = manager, scope, tool, args or {}
        self.parts = parse(probe)
        self.batch, self.fallback, self.describe = batch, fallback, describe
        self.n = 0                     # batch items measured
        self._last = {}                # folder -> its names after the last item (the next before)
        self._st = None
        self._mark = scope.count
        self._side = False             # the only records: what a refused call did anyway (a detach)
        self._t0 = None
        if any(k == "sess" for k, _ in self.parts) and any(k == "file" for k, _ in self.parts):
            scope.file_op = "patch"    # a file edit that reopens the session

    # -- whole call / item by item
    def enter(self, item) -> dict:
        try:
            a = self.item_args(item)
        except Exception:
            a = dict(self.args)
        self.n += 1
        self.before(a)
        return a

    def leave(self, a, result) -> None:
        self.after(a, result)

    def done(self, result) -> None:
        if not (self.batch and self.n):
            self.after(self.args, result)

    def item_args(self, item) -> dict:
        """A batch item as the arguments of the single call it stands for."""
        a = {k: v for k, v in self.args.items() if k != self.batch}
        keys = _ITEM.get(self.batch)
        if isinstance(item, dict):
            a.update({(keys.get(k, k) if isinstance(keys, dict) else k): v for k, v in item.items()})
        else:
            a[keys if isinstance(keys, str) else "item"] = item
        return a

    # -- measuring
    def before(self, a=None) -> None:
        a = self.args if a is None else a
        t = self._t0 = _perf()
        self._mark = self.scope.count
        self._side = False
        st, tree = {}, None
        f = _noter(self.m, a.get("session_name"), self.tool)     # Aspen's internal fault: flagged
        try:
            self._st = None
            if any(k in _TREE for k, _ in self.parts):
                tree = _tree(self.m.get_app(a.get("session_name")))
            for i, (kind, param) in enumerate(self.parts):
                try:
                    if kind == "sess":
                        st[i] = _sessions(self.m)
                    elif kind == "run":
                        if param is None:             # a run (a reinit runs nothing): runlog's before-read
                            st[i] = runlog.before_run(self.m, a.get("session_name"), self.scope)
                        self._t0 = _perf()            # the run's secs and its status start here
                    elif tree is None:
                        continue
                    elif kind in ("kid", "row"):
                        path, node = _el(tree, _fill(param, a, element=True))
                        folder, _, name = path.rpartition("\\")
                        st[i] = (path, None if node is None else _details(tree, folder, name, node, f))
                    elif kind in ("kids", "rows"):
                        st[i] = self._kids_before(tree, _fill(param, a), a, f)
                    elif kind == "port":
                        st[i] = (_names(_port(tree, a.get("block_name"), a.get("port_name"), f)[1], f),
                                 _ends(tree, a.get("stream_name"), f))
                    elif kind == "args":
                        path = _fill(param, a)
                        node = _find(tree, path)
                        st[i] = (path, recorder.read_state(node) if node is not None else None)
                except Exception as exc:
                    self._noted(a, exc)
                    logger.debug("probes: %s before %s not read (%r)", kind, self.tool, exc)
            self._st = st
        except Exception as exc:
            logger.warning("probes: %s not measured before (%r)", self.tool, exc)
        finally:
            self.scope.jt += _perf() - t

    def after(self, a, result) -> None:
        a = self.args if a is None else a
        t = _perf()
        try:
            st, self._st = self._st, None
            if st is not None:
                self._measure(st, a, result)
            if self.fallback and (self.scope.count == self._mark or self._side):
                target, summary = self.describe(a) if self.describe else (None, None)
                self.scope.add("call", status="failed" if failed(result) else "unchanged", target=target,
                               args=summary, result=str(result or "")[:journal.RESULT_MAX])
        except Exception as exc:
            logger.warning("probes: %s not measured (%r)", self.tool, exc)
        finally:
            self.scope.jt += _perf() - t

    def _measure(self, st, a, result) -> None:
        session, app, tree, reopened = a.get("session_name"), None, None, None
        f = _noter(self.m, session, self.tool)
        if any(k in _APP for k, _ in self.parts):
            app = self.m.get_app(session)             # afresh: the call may have reopened it
            tree = _tree(app) if any(k in _TREE for k, _ in self.parts) else None
        for i, (kind, param) in enumerate(self.parts):
            try:
                if kind == "sess" and i in st:
                    reopened = self._sessions_after(st[i])
                elif kind == "file":
                    if reopened is not None:
                        self.scope.file_extra["reopened"] = session in reopened
                elif kind == "run" and app is not None:
                    rf = run_fields(app, result, param or "run", since=self._t0, fault=f)
                    rf["secs"] = round(_perf() - self._t0, 2)
                    runlog.after_run(st.get(i), self.m, rf)
                    self.scope.add(param or "run", **rf)
                elif tree is None or i not in st:
                    continue
                elif kind in ("kid", "row"):
                    self._kid_after(tree, *st[i], "row" if kind == "row" else "element")
                elif kind in ("kids", "rows"):
                    self._kids_after(tree, _fill(param, a), st[i], "row" if kind == "rows" else "element", f)
                elif kind == "port":
                    self._port_after(tree, a, st[i], f)
                elif kind == "args":
                    self._args_after(tree, *st[i])
            except Exception as exc:
                self._noted(a, exc)
                logger.debug("probes: %s after %s not read (%r)", kind, self.tool, exc)

    def _noted(self, a, exc) -> None:
        """A part that raised Aspen's internal fault (``_fault``: a listing here met it) flags the
        call's session -- its runs would never return -- rather than only leaving the part out."""
        if knowledge_tools.server_fault(exc):
            note = _noter(self.m, (a or {}).get("session_name"), self.tool)
            if note is not None:
                note(exc)

    # -- elements
    def _record(self, op, folder, name, default, info=None, node=None, tree=None):
        target = {"kind": _kind(folder, default), "name": name, "path": f"{folder}\\{name}",
                  "type": (info or {}).get("type") if node is None else _type(node)}
        if target["kind"] == "component":              # the name it was added by
            target["aname"] = (info or {}).get("aname") if node is None or tree is None else _aname(tree, name)
        conn = (info or {}).get("connections")
        self.scope.add(op, target={k: v for k, v in target.items() if v is not None},
                       before={"connections": conn} if conn is not None else None, status="changed")

    def _kid_after(self, tree, path, info, default):
        path, node = _el(tree, path)
        folder, _, name = path.rpartition("\\")
        if info is not None and node is None:
            self._record("remove", folder, name, default, info=info)
        elif info is None and node is not None:
            self._record("add", folder, name, default, node=node, tree=tree)

    def _kids_before(self, tree, folder, a, fault=None):
        names = self._last.pop(folder, None) if self.batch else None
        if names is None:
            names = _names(_find(tree, folder), fault)
        if names is None:
            return None
        said = {str(v).upper() for k, v in a.items()
                if k not in _NOT_NAMES and isinstance(v, (str, int)) and not isinstance(v, bool)}
        info = {}
        for n in names:                                # what a removal would take with it
            if n.upper() in said and len(info) < LIST_MAX:
                node = _find(tree, f"{folder}\\{n}")
                info[n] = _details(tree, folder, n, node, fault) if node is not None else {}
        return names, info

    def _kids_after(self, tree, folder, state, default, fault=None):
        if state is None:
            return
        names, info = state
        now = _names(_find(tree, folder), fault)
        if now is None:
            return
        if self.batch:
            self._last[folder] = now
        for n in _minus(names, now)[:LIST_MAX]:
            self._record("remove", folder, n, default, info=info.get(n))
        for n in _minus(now, names)[:LIST_MAX]:
            node = _find(tree, f"{folder}\\{n}")
            if node is not None:
                self._record("add", folder, n, default, node=node, tree=tree)
            else:
                self._record("add", folder, n, default)

    # -- port
    def _port_after(self, tree, a, state, fault=None):
        before, (name, ends) = state
        block, stream = _block(tree, a.get("block_name")), name or a.get("stream_name")
        port, node = _port(tree, block, a.get("port_name"), fault)
        now = _names(node, fault)
        if before is None or now is None:
            return
        if now == before:                  # the port as it was: refused, or on it already -- yet
            self._detached(tree, name, ends, block, port, fault)    # V15 may have taken the stream off anyway
            return
        target = journal.label(rf"\Data\Blocks\{block}\Ports\{port}")
        target.update(kind="port", port=port, stream=stream)
        gone = _minus(before, now)
        self.scope.add("connect", target={k: v for k, v in target.items() if v is not None}, before=before,
                       after=now, displaced=gone or None, moved_from=_left(tree, name, ends, block, port),
                       status="changed")

    def _detached(self, tree, stream, ends, block, port, fault=None):
        """A connect that left its port as it was but took the stream off the port its moving end
        was on -- V15 refusing a stream into the block at its other end has already done that
        (wb_plan's ``loop``). One record of it, shaped as a disconnect's: ``connect`` on
        the port it left, ``before`` / ``after`` that port's streams, ``displaced`` [the stream] --
        so an undo puts it back (a reconnect) and the timeline shows it --, ``detached`` true and
        ``asked`` {block, port}: the connect Aspen refused. The call's own record (failed) follows
        it (``_side``). Nothing when the stream left no end."""
        left = _left(tree, stream, ends, block, port)
        if not left:
            return
        b = _block(tree, left["block"])
        p, node = _port(tree, b, left["port"], fault)
        now = _names(node, fault)
        if now is None or any(x.upper() == str(stream).upper() for x in now):
            return
        target = journal.label(rf"\Data\Blocks\{b}\Ports\{p}")
        target.update(kind="port", port=p, stream=stream)
        self.scope.add("connect", target={k: v for k, v in target.items() if v is not None}, before=now + [stream],
                       after=now, displaced=[stream], moved_from={}, detached=True,
                       asked={"block": block, "port": port}, status="changed")
        self._side = True

    # -- args
    def _args_after(self, tree, path, before):
        node = _find(tree, path)
        if node is None:
            return
        now = recorder.read_state(node)
        if before is None:
            self.scope.add("value", target=journal.label(path), after=now, created=True, status="changed")
        else:
            self.scope.add("value", target=journal.label(path), before=before, after=now,
                           status="unchanged" if before == now else "changed")

    # -- sessions
    def _sessions_after(self, before) -> set:
        """open / close records; returns the sessions whose Aspen was replaced (reopened)."""
        now, reopened = _sessions(self.m), set()
        for name, (mid, _, path) in before.items():
            if name not in now or now[name][0] != mid:
                self.scope.add("close", session=name, model=mid, file=path, status="changed")
        for name, (mid, ref, path) in now.items():
            old = before.get(name)
            if old is None or old[0] != mid:
                self.scope.add("open", session=name, model=mid, file=path, status="changed")
            elif old[1] is not None and ref is not None and old[1]() is not ref():
                reopened.add(name)
        return reopened
