"""Where the GUI's Next would take an incomplete object: the form sheet Aspen marks incomplete,
and the fields on it that are empty -- the way the GUI itself decides it.

Each form sheet's ViewModel declares completion flags (nodes under the object's CC Nodes): the
sheet is complete when every one of them is 1 or absent, shown when one of its access flags is
1 (or it has none). A sheet's fields are its bound Input nodes; one counts as empty when it
holds no value (a list: no row with one), the user can enter it (HAP_ENTERABLE, attribute 7) and
no CC condition of the sheet disables or hides it (a 0). Unlabelled rows that hold values come
first, then fields with a GUI prompt (attribute 19), scalars before lists.

The table (data/gui_forms_v15.json.gz) holds identifiers only -- form and sheet classes, CC
flag paths, keywords, resource keys, collection names, object containers; no AspenTech text --
taken from the V15 form assemblies (build 41.0) and a live probe of the subobject collections;
``applies()`` is false on any other version, and check_inputs falls back to its field walk
(tools/inputs_check.py). A sheet's title is its header resource key, looked up in the strings
read from the user's own Aspen (tools/aspen_strings.py ``headers``); without them, the sheet
class's last part.

    forms:  {form class: [[sheet class, header key, [complete flags], [access flags]], ...]}
            every input tab; one without complete flags is always complete; a "" class: the
            table cannot name the tab's sheet (look reads every sheet of the form)
    sheets: {sheet class: [[field path] | [field path, [CC condition paths]], ...]}
    hide:   [form or sheet class]  never shown: Dynamics, EO, Costing, wizards
    subs:   {form prefix: {collection: [form class]}}  a block's subobject collections
            ("Pumparounds", nested "Pumparounds/Hcurves") and the forms of each member
    kinds:  {container | singleton path: {"g": group, "one": 1 | 0, "t": {record type | "*":
            form prefix}}}  which forms an object has (_prefix), the workbench's model objects

Paths are dotted from the object ("CC Nodes.REACT", "Input.PS_VENDOR.@id"): an "@id" segment
is a subobject id (the ids a flag list was read under, else every child), "@parent" one level
up, any other "@name" every child. A collection member's forms take its ids for their "@"
segments, the deepest last ("CC Nodes.CASPEC.@option_id.@id": internals INT-1, section CS-1).

    applies()                                  the table is there and fits this Aspen
    look(via, tree, path, rectype, container)  -> [sheet] | None (no forms for the object)
    outline(rectype, container)                -> the object's forms and sheets, no COM
    status(via, tree, path, rectype, container) -> each sheet done / todo / hidden, flags only
    kinds(), container_of(path)                -> the object kinds the table knows (forms, model objects)
    sheet_paths(via, tree, path, cls, ids)      -> the tree paths of one sheet's fields
    off_fields(via, tree, path, rectype, container) -> the inputs a CC condition turns off (greyed)
    sheet_of(rectype, container, rel)          -> (form, sheet class) that binds a field

``via`` is tools/inputs_check.py's reader (raw Invokes or attributes). Stdlib and tools.* only;
the table is read on first use.
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import re
import threading
import time
from pathlib import Path

from tools import aspen_labels, aspen_strings, knowledge_tools

try:
    import win32api
except ImportError:                                # not Windows: applies() is false anyway
    win32api = None

logger = logging.getLogger(__name__)

TABLE = Path(__file__).resolve().parent / "data" / "gui_forms_v15.json.gz"
_ENV = "ASPEN_MCP_SHEETS"                          # "0": never (check_inputs' field walk only)
BS = "\\"
EXPAND_MAX = 60                                    # paths one table path expands to at most
LIST_KIDS = 40                                     # rows of a list read to see whether it holds a value
KIDS = 400                                         # children of one node read at most
SHEET_NODES = 600                                  # field nodes one sheet reads at most
ROWS = 50                                          # rows read for a label
MS = 3000.0                                        # one object's look stops reading after this
STATUS_MS = 150.0                                  # ... its status after this

# Forms the GUI shows first (setup) and last (options, subroutines, curves); the rest between.
_FIRST = re.compile(r"Setup|setup|Input|Inp|In|Spec_Input|Specif|Specification|Spec|Config")
_LAST = re.compile(r"Blocko\w*|BlockO|EOPort|Subrou|Subro|Subr|subrou|Hcurve|RebHcu|ICSHcu|Perfcu|perfcu|Advanc|UserSu")
# Forms whose title is not the one the user's Aspen gives by its class (form_title): a whole class first
# (the object's own form), else its part after the prefix where the strings have no title (this project's words).
_FORM_NAMES = {
    "MMSetup_Setup": "Specifications", "MMComp_Spec_Input": "Specifications", "MMProp_Spec_Input": "Specifications",
    "Subrou": "User Subroutine", "Subro": "User Subroutine", "Subr": "User Subroutine", "UserSu": "User Subroutine",
    "User": "User Subroutine", "HeatXfer": "Heat Transfer", "Perfcu": "Performance Curves", "Connec": "Connections",
    "Simopt": "Simulation Options", "Strcla": "Stream Class", "CusUom": "Custom Units", "Order": "Conv Order",
    "Option_Method": "Methods", "ColumnInternals": "Column Internals",
}
_NAMES_LOW = {k.lower(): v for k, v in _FORM_NAMES.items()}

_LOCK = threading.Lock()
_TAB: dict | None = None                           # the table once read ({} when it cannot be)
_FORMS_LOW: dict = {}                              # lower-case form class -> form class
_SHEETS_LOW: dict = {}                             # lower-case sheet class -> sheet class
_FITS: bool | None = None                          # the running Aspen is the table's
_TAILS: dict | None = None                         # form_tails() once worked out


def _table() -> dict:
    global _TAB
    if _TAB is None:
        with _LOCK:
            if _TAB is None:
                try:
                    with gzip.open(TABLE, "rt", encoding="utf-8") as f:
                        tab = json.load(f)
                except (OSError, ValueError) as exc:
                    logger.warning("gui-sheets: table not read (%r)", exc)
                    tab = {}
                _FORMS_LOW.update({k.lower(): k for k in tab.get("forms") or {}})
                _SHEETS_LOW.update({k.lower(): k for k in tab.get("sheets") or {}})
                _TAB = tab
    return _TAB


def header_keys() -> set:
    """Every sheet header key the table names (tools/aspen_strings.py keeps their texts)."""
    return {t[1] for tabs in (_table().get("forms") or {}).values() for t in tabs if t[1]}


def form_tails() -> dict:
    """{form class: its part after the object's prefix} of every form the table has: 'MMRadfrac_TraSiz'
    -> 'TraSiz', 'MMComp_Spec_Input' -> 'Input' (the longest prefix ``kinds`` names), 'ConSep' ->
    'ConSep' (tools/aspen_strings.py titles them from the strings read from the user's Aspen)."""
    global _TAILS
    if _TAILS is None:
        pres = sorted({p for k in kinds().values() for p in (k.get("t") or {}).values()}, key=len, reverse=True)
        out = {}
        for form in _table().get("forms") or {}:
            low = form.lower()
            pre = next((p for p in pres if low.startswith(f"mm{p}_")), None)
            out[form] = form[len(pre) + 3:] if pre else form.split("_", 1)[1] if "_" in form else form
        _TAILS = out
    return _TAILS


def _file_build(dll: str) -> str | None:
    """'41.0' of a DLL whose file version is 41.0.x.y; None when it cannot be read."""
    if win32api is None:
        return None
    try:
        info = win32api.GetFileVersionInfo(dll, "\\")
        ms = info["FileVersionMS"]
        return f"{ms >> 16}.{ms & 0xFFFF}"
    except Exception:  # noqa: BLE001 -- pywin32 raises its own error type
        return None


def fits() -> bool:
    """The Aspen COM starts is the table's version and build (its Localization.dll's file
    version), once per process."""
    global _FITS
    if _FITS is None:
        tab, ok = _table(), False
        try:
            found = aspen_strings.find_dll()
            if found and tab and found.get("aspen") == tab.get("aspen"):
                build = _file_build(found["dll"])
                ok = build is None or build == tab.get("build")
                if build is None:
                    logger.info("gui-sheets: %s file version unread; taking %s as the table's",
                                found["dll"], found.get("aspen"))
        except Exception:  # noqa: BLE001
            logger.debug("gui-sheets: version not read", exc_info=True)
        _FITS = ok
    return _FITS


def applies() -> bool:
    """check_inputs may use the sheet layer: not turned off (ASPEN_MCP_SHEETS=0), the table
    read, and the running Aspen its version (``fits``)."""
    if os.environ.get(_ENV, "1").strip() == "0":
        return False
    return bool(_table().get("forms")) and fits()


def kinds() -> dict:
    """The table's ``kinds``: {container or singleton path: {"g" group, "one" 1 for a singleton,
    "t" {record type | "*": form prefix}}}."""
    return _table().get("kinds") or {}


def container_of(path: str) -> str:
    """The path ``kinds`` names an object by: a singleton's own, else its container."""
    k = kinds().get(path)
    return path if k and k.get("one") else path.rsplit(BS, 1)[0]


def _prefix(rectype, container: str) -> str:
    """The object's forms' class prefix (lower case, after "MM"): the table's ``kinds`` for its
    ``container`` (a singleton's own path, or the container of others) and record type, else the
    record type itself; "" for neither."""
    t = str(rectype or "").strip().upper()
    by = (kinds().get(container) or {}).get("t") or {}
    return str(by.get(t) or by.get("*") or t).lower()


def forms_for(rectype, container: str) -> list[str]:
    """The table's forms of an object (_prefix), setup forms first."""
    tab = _table()
    pre = _prefix(rectype, container)
    if not pre:
        return []
    head = "mm" + pre + "_"
    out = [f for low, f in _FORMS_LOW.items() if low.startswith(head)]
    order = {f: i for i, f in enumerate(tab.get("forms") or {})}
    def rank(f):
        tail = f.split("_", 1)[1] if "_" in f else ""
        return 0 if _FIRST.fullmatch(tail) else 2 if _LAST.fullmatch(tail) else 1

    return sorted(out, key=lambda f: (rank(f), order.get(f, 0)))


# ----------------------------------------------------------------------------- reading
class _Stop(Exception):
    """The look's time is spent."""


class _Reader:
    """Tree reads of one look, cached by path; Aspen's internal fault is raised."""

    def __init__(self, via, tree, deadline: float):
        self.via, self.tree, self.deadline = via, tree, deadline
        self.nodes: dict = {}
        self.names: dict = {}
        self.reads = 0

    def _guard(self, exc):
        if knowledge_tools.server_fault(exc):
            raise exc

    def node(self, p: str):
        if p not in self.nodes:
            if time.perf_counter() > self.deadline:
                raise _Stop()
            self.reads += 1
            try:
                self.nodes[p] = self.via.find(self.tree, p)
            except Exception as exc:
                self._guard(exc)
                self.nodes[p] = None
        return self.nodes[p]

    def val(self, p: str):
        n = self.node(p)
        if n is None:
            return None
        try:
            return self.via.value(n)
        except Exception as exc:
            self._guard(exc)
            return None

    def attr(self, p: str, i: int):
        n = self.node(p)
        if n is None:
            return None
        try:
            return self.via.attr(n, i)
        except Exception as exc:
            self._guard(exc)
            return None

    def dim(self, p: str) -> int:
        n = self.node(p)
        if n is None:
            return 0
        try:
            d = self.via.dim(n)
            return d if isinstance(d, int) else 0
        except Exception as exc:
            self._guard(exc)
            return 0

    def kids(self, p: str) -> list[str]:
        """The child names (KIDS at most), cached."""
        if p in self.names:
            return self.names[p]
        n, out = self.node(p), []
        if n is not None:
            try:
                col = self.via.elements(n)
                out = [self.via.name(self.via.item(col, i)) for i in range(min(self.via.count(col), KIDS))]
            except Exception as exc:
                self._guard(exc)
        self.names[p] = out
        return out

    def labels(self, p: str):
        """The labels of dimension 0's first ROWS rows; None for a scalar, an empty list, or a
        dimension without labels (a positional list: Label raises there, live V15)."""
        n = self.node(p)
        if n is None:
            return None
        try:
            col = self.via.elements(n)
            nr = self.via.rowcount(col, 0)
            return [self.via.label(col, 0, i) for i in range(min(nr, ROWS))] or None
        except Exception as exc:
            self._guard(exc)
            return None


def _flag(v) -> bool | None:
    """A completion flag: True (1), False (0), None (absent / anything else)."""
    return True if v in (1, "1") else False if v in (0, "0") else None


def _expand(r: _Reader, obj: str, dotted: str, ids=None) -> list[tuple[str, tuple]]:
    """A table path as [(tree path, the "@id" values taken)], at most EXPAND_MAX."""
    paths = [(obj, ())]
    for seg in dotted.split("."):
        nxt = []
        for p, got in paths:
            if seg == "@parent":
                nxt.append((p.rsplit(BS, 1)[0], got))
            elif seg.startswith("@id"):
                if ids and len(got) < len(ids):
                    nxt.append((p + BS + ids[len(got)], got + (ids[len(got)],)))
                else:
                    nxt.extend((p + BS + k, got + (k,)) for k in r.kids(p))
            elif seg.startswith("@"):
                nxt.extend((p + BS + k, got) for k in r.kids(p))
            else:
                nxt.append((p + BS + seg, got))
        paths = nxt[:EXPAND_MAX]
    return paths


def _empty(r: _Reader, p: str, depth: int = 0):
    """True when the field holds no value (a list: no row with one, LIST_KIDS rows and two
    levels read); None when there is no such node."""
    if r.node(p) is None:
        return None
    if not r.dim(p):
        v = r.val(p)
        return v is None or (isinstance(v, str) and not v.strip())
    if depth > 1:
        return False
    ks = r.kids(p)
    return not ks or all(_empty(r, p + BS + k, depth + 1) for k in ks[:LIST_KIDS])


def _fields(r: _Reader, obj: str, sheet: str, ids) -> list[dict]:
    """The empty, enterable, enabled fields of one sheet (see the module docstring)."""
    props = (_table().get("sheets") or {}).get(sheet) or []
    base = obj + BS + "Input" + BS
    out, seen, tops = [], set(), []
    for prop in props:
        dotted, cond = prop[0], (prop[1] if len(prop) > 1 else ())
        top = base + dotted.split(".")[1]
        if top not in tops:
            tops.append(top)
        for p, _ in _expand(r, obj, dotted, ids):
            if p in seen or len(seen) >= SHEET_NODES:
                continue
            seen.add(p)
            if not _empty(r, p) or r.attr(p, 7) == 0:            # HAP_ENTERABLE
                continue
            if any(_flag(r.val(cp)) is False for c in cond for cp, _ in _expand(r, obj, c, ids)):
                continue
            prompt = str(r.attr(p, 19) or "").strip()            # HAP_PROMPT
            out.append({"field": p[len(base):], "path": p, "kind": "list" if r.dim(p) else "value",
                        "prompt": prompt})
    named = {f["field"] for f in out}
    for top in tops:                       # a labelled table's row with no label (the GUI shows it red)
        kw = top[len(base):]
        if kw in named or len(seen) >= SHEET_NODES or not r.dim(top):
            continue                       # (a scalar's Elements raises: slow, ~ms a node)
        labels = r.labels(top)
        i = next((i for i, lab in enumerate(labels or ()) if lab in (None, "")), None)
        if i is not None:
            out.append({"field": kw, "path": top, "kind": "row", "row": i + 1, "prompt": ""})
    out.sort(key=lambda f: (f["kind"] != "row", not f["prompt"], f["kind"] == "list"))
    return out


def _sheets(r: _Reader, obj: str, forms) -> list[dict]:
    tab = _table()
    out, done = [], set()
    for form in forms:
        for sheet, header, complete, access in tab["forms"].get(form) or ():
            comp = [(p, _flag(r.val(p)), ids) for d in complete for p, ids in _expand(r, obj, d)]
            if not comp:
                continue
            acc = [(_flag(r.val(p)), ids) for d in access for p, ids in _expand(r, obj, d)]
            by_id: dict = {}
            for p, v, ids in comp:
                by_id.setdefault(ids, []).append((p, v))
            for ids, lst in by_id.items():
                zeros = tuple(p.split(BS + "CC Nodes" + BS, 1)[-1] for p, v in lst if v is False)
                if not zeros or (ids, zeros) in done:
                    continue
                here = [v for v, i2 in acc if not i2 or i2 == ids[:len(i2)]]
                if here and not any(v is True for v in here):
                    continue                                     # the sheet is not shown
                done.add((ids, zeros))
                shs = [sheet] if sheet else [s for low, s in _SHEETS_LOW.items() if low.startswith(form.lower() + "_")]
                fields, names = [], set()
                for s in shs:
                    for f in _fields(r, obj, s, ids):
                        if f["field"] not in names:
                            names.add(f["field"])
                            fields.append(f)
                out.append({"form": form, "sheet": sheet or None, "header": header or None,
                            "ids": list(ids), "flags": list(zeros), "fields": fields})
    return out


def _bit(r: _Reader, p: str) -> bool:
    v = r.attr(p, 12)                                            # HAP_COMPSTATUS
    return isinstance(v, int) and bool(v & 0x40)


def look(via, tree, path: str, rectype, container: str, budget_ms: float = MS) -> dict | None:
    """The incomplete sheets of one object, in the GUI's order -- a subobject's (a column
    internals section, a pack sizing) among its block's, under its ids: {"sheets": [{"form",
    "sheet", "header", "ids", "flags" (the CC flags at 0), "fields": [{"field", "path",
    "kind" value | list | row, "prompt", "row"?}]}], "flagged" (the object's own COMPSTATUS
    bit), "reads", "cut" (the budget ran out)}; None when the table has no form for it."""
    forms = forms_for(rectype, container)
    if not forms:
        return None
    r = _Reader(via, tree, time.perf_counter() + budget_ms / 1000)
    res = {"sheets": [], "flagged": None, "reads": 0, "cut": False}
    try:
        res["flagged"] = _bit(r, path)
        res["sheets"] = _sheets(r, path, forms)
    except _Stop:
        res["cut"] = True
    res["reads"] = r.reads
    return res


# ----------------------------------------------------------------------------- outline and status
def collections(rectype, container: str) -> dict:
    """{collection: [form class]} of the object's type (the table's ``subs``)."""
    return dict((_table().get("subs") or {}).get(_prefix(rectype, container)) or {})


def _shown(rectype, container: str):
    """[(form, [row])] the workbench shows: not hidden, not a collection's own list (its flags
    all read from above the member, "@parent..."; the collection itself stands for it)."""
    tab = _table()
    hide = set(tab.get("hide") or ())
    out = []
    for form in forms_for(rectype, container):
        flags = [p for row in tab["forms"][form] for p in row[2] + row[3]]
        if form in hide or (flags and all(p.startswith("@parent") for p in flags)):
            continue
        rows = [row for row in tab["forms"][form] if row[0] not in hide]
        if rows:
            out.append((form, rows))
    return out


def outline(rectype, container: str) -> list[dict]:
    """The object's input forms as the GUI shows them, setup forms first, no COM: [{"form",
    "title", "coll" (the collection whose members each have these sheets, else None), "sheets":
    [{"cls" ("" when the table cannot name it), "header", "title", "fields": [dotted Input
    paths]}]}]; the forms and sheets ``hide`` names left out. [] when the table has no form."""
    sheets, owner = _table().get("sheets") or {}, {}
    for coll, forms in collections(rectype, container).items():
        owner.update(dict.fromkeys(forms, coll))
    out = []
    for form, rows in _shown(rectype, container):
        coll = owner.get(form)
        out.append({"form": form, "title": form_title(form), "coll": coll,
                    "sheets": [{"cls": cls, "header": head, "title": sheet_title({"sheet": cls, "header": head}),
                                "fields": list(dict.fromkeys(p[0] for p in sheets.get(cls) or ()))}
                               for cls, head, _c, _a in rows]})
    return out


def _members(r: _Reader, obj: str, coll: str) -> list[tuple]:
    """The id paths of a collection's members: ("P-1",), nested ("INT-1", "CS-1")."""
    ids, parts = [()], coll.split("/")
    for part in parts:
        ids = [got + (k,) for got in ids for k in r.kids(
            obj + "".join(f"{BS}Subobjects{BS}{q}{BS}{g}" for q, g in zip(parts, got)) + f"{BS}Subobjects{BS}{part}")]
    return ids


def _member_path(obj: str, dotted: str, ids: tuple):
    """A table path for one member: its "@" segments take the member's ids, the deepest last;
    None when it has more of them than the member has ids."""
    segs = dotted.split(".")
    n = sum(s.startswith("@") for s in segs)
    if n > len(ids):
        return None
    take = iter(ids[len(ids) - n:])
    return obj + "".join(BS + (next(take) if s.startswith("@") else s) for s in segs)


def _judge(r: _Reader, obj: str, row, member) -> list[tuple]:
    """[(ids, state, zeros)] of one sheet: per member (``member`` an id path), else per id its
    "@" flags hold (as look), else once. Access flags first: a hidden sheet's completion flags
    are not read."""
    _cls, _head, complete, access = row
    if member is not None:
        comp = [(p, member) for p in (_member_path(obj, d, member) for d in complete) if p]
        acc = [(p, member) for p in (_member_path(obj, d, member) for d in access) if p]
        groups = [member]
    else:
        comp = [x for d in complete for x in _expand(r, obj, d)]
        acc = [x for d in access for x in _expand(r, obj, d)]
        held = any("@" in d for d in complete + access)
        groups = list(dict.fromkeys(ids for _p, ids in comp + acc)) if held else [()]
    out = []
    for ids in groups:
        here = [_flag(r.val(p)) for p, i2 in acc if not i2 or i2 == ids[:len(i2)]]
        if here and True not in here:
            out.append((ids, "hidden", ()))
            continue
        zeros = tuple(p.split(BS + "CC Nodes" + BS, 1)[-1] for p, i2 in comp if i2 == ids and _flag(r.val(p)) is False)
        out.append((ids, "todo" if zeros else "done", zeros))
    return out


def _here(r: _Reader, obj: str, rows) -> bool:
    """Some of a form is under the object: a flag of one of its sheets (the reads cached for
    _judge), else, none being there, a field keyword of a sheet without flags. A prefix names
    forms of neighbouring objects too (Setup's Units-Sets, Conv-Options' Order, held by
    Conv-Order): theirs are not."""
    sheets = _table().get("sheets") or {}
    if any(r.node(p) is not None for row in rows for d in row[2] + row[3] for p, _ in _expand(r, obj, d)):
        return True
    for cls, _h, complete, access in rows:
        tops = [p[0].split(".")[:2] for p in sheets.get(cls) or () if not (complete or access)]
        if any(len(t) == 2 and not t[1].startswith(("@", "#")) and r.node(obj + BS + BS.join(t)) is not None
               for t in tops[:4]):
            return True
    return False


def status(via, tree, path: str, rectype, container: str, budget_ms: float = STATUS_MS) -> dict | None:
    """Each shown sheet's state by its CC flags alone, no field read: {"sheets": [{"form",
    "sheet", "header", "ids", "state" done | todo | hidden, "flags" (todo: those at 0)}],
    "subs": {collection: [member ids "P-1", nested "INT-1/CS-1"]}, "absent": [forms none of
    whose flags or fields is under the object (_here): left out of "sheets"], "reads", "ms",
    "cut" (the budget ran out)}. A collection's forms appear once per member, under its ids.
    None when the table has no form for the object."""
    shown = _shown(rectype, container)
    if not shown:
        return None
    t0 = time.perf_counter()
    r = _Reader(via, tree, t0 + budget_ms / 1000)
    res = {"sheets": [], "subs": {}, "absent": [], "reads": 0, "ms": 0.0, "cut": False}
    try:
        members, owner = {}, {}
        for coll, forms in collections(rectype, container).items():
            members[coll] = _members(r, path, coll)
            res["subs"][coll] = ["/".join(m) for m in members[coll]]
            owner.update(dict.fromkeys(forms, coll))
        for form, rows in shown:
            if form not in owner and not _here(r, path, rows):
                res["absent"].append(form)
                continue
            for member in members[owner[form]] if form in owner else [None]:
                for row in rows:
                    for ids, state, zeros in _judge(r, path, row, member):
                        res["sheets"].append({"form": form, "sheet": row[0] or None, "header": row[1] or None,
                                              "ids": list(ids), "state": state, "flags": list(zeros)})
    except _Stop:
        res["cut"] = True
    res["reads"], res["ms"] = r.reads, round((time.perf_counter() - t0) * 1000, 1)
    return res


def sheet_paths(via, tree, path: str, cls: str, ids=(), budget_ms: float = STATUS_MS) -> list[str]:
    """The tree paths of one sheet's fields in the table's order, at most SHEET_NODES: a collection
    member's "@" segments take its ``ids`` (_member_path), others every child there; a "#n" row
    left out where the sheet binds its keyword otherwise too. Nodes are not looked up."""
    fields = list(dict.fromkeys(p[0] for p in (_table().get("sheets") or {}).get(cls) or ()))
    tops = [f.split(".")[1] for f in fields if "." in f]
    r, out = _Reader(via, tree, time.perf_counter() + budget_ms / 1000), []
    try:
        for d in fields:
            segs = d.split(".")
            if any(s.startswith("#") for s in segs) and tops.count(segs[1]) > 1:
                continue
            got = [_member_path(path, d, tuple(ids))] if ids and "@" in d else [p for p, _ in _expand(r, path, d)]
            out += [p for p in got if p and p not in out]
            if len(out) >= SHEET_NODES:
                break
    except _Stop:
        pass
    return out[:SHEET_NODES]


def off_fields(via, tree, path: str, rectype, container: str, budget_ms: float = STATUS_MS) -> dict | None:
    """The input fields the current settings turn off, as the GUI greys them: a field a sheet's
    ViewModel binds under a CC condition that reads 0 (Flash2's TEMP under CC Nodes.EXISTT when
    SPEC_OPT is PD or PV; a stream's VFRAC under CC Nodes.FRAC.MIXED with MIXED_SPEC TP) --
    Aspen's HAP_ENTERABLE stays 1 there (live V15). {tree path relative to Input ("TEMP",
    "VFRAC\\MIXED"): [the flags at 0]}, the sheets of the forms the workbench shows, a
    collection's left out; None when the table has no form for the object. Flags only, cached
    reads, ``budget_ms`` at most."""
    shown = _shown(rectype, container)
    if not shown:
        return None
    owned = {f for fs in collections(rectype, container).values() for f in fs}
    sheets, base = _table().get("sheets") or {}, path + BS + "Input" + BS
    r, out = _Reader(via, tree, time.perf_counter() + budget_ms / 1000), {}
    try:
        for form, rows in shown:
            for cls, *_ in rows if form not in owned else ():
                for prop in sheets.get(cls) or ():
                    if len(prop) < 2 or not prop[1]:
                        continue
                    zeros = [cp.split(BS + "CC Nodes" + BS, 1)[-1] for c in prop[1] for cp, _ in _expand(r, path, c) if _flag(r.val(cp)) is False]
                    if zeros:
                        for p, _ in _expand(r, path, prop[0]):
                            if p.startswith(base):
                                out.setdefault(p[len(base):], zeros)
    except _Stop:
        pass
    return out


def sheet_of(rectype, container: str, rel: str) -> tuple | None:
    """(form, sheet class) of the first sheet the workbench shows that binds the field ``rel``
    ("Input\\BASIS_D", "Input\\FEED_STAGE\\F1") -- a collection's forms left out; None."""
    key, sheets = (rel.split(BS) + [""])[1], _table().get("sheets") or {}
    owned = {f for fs in collections(rectype, container).values() for f in fs}
    for form, rows in _shown(rectype, container) if key else ():
        for cls, *_ in rows if form not in owned else ():
            if any(p[0].split(".")[1:2] == [key] for p in sheets.get(cls) or ()):
                return form, cls
    return None


# ----------------------------------------------------------------------------- words
def _plain(part: str) -> str:
    """A class part as words, where nothing names it: 'SpecSummary' -> 'Spec Summary', 'perfcu' -> 'Perfcu'."""
    return " ".join(w if w.isupper() else w.capitalize() for w in aspen_strings._CAMEL.findall(part)) or part


def form_title(form: str) -> str:
    """'MMRCSTR_Setup' -> 'Setup'; 'MMRadfrac_PacSiz' -> 'Packing Sizing' (the title the user's Aspen
    gives it, aspen_labels.form_name); a collection's form the collection's (the outer one's when
    nested): 'MMRadfrac_PumInp' -> 'Pumparounds'; else _FORM_NAMES (any case), else its class part
    (its first, of several) as words."""
    pre = form[2:].split("_", 1)[0].lower()
    coll = next((c for c, fs in ((_table().get("subs") or {}).get(pre) or {}).items() if form in fs), None)
    if coll:
        return coll.split("/", 1)[0]
    tail = form_tails().get(form) or form
    first = tail.split("_")[0]
    return (_NAMES_LOW.get(form.lower()) or aspen_labels.form_name(form) or _NAMES_LOW.get(tail.lower())
            or _NAMES_LOW.get(first.lower()) or _plain(first))


def sheet_title(sh: dict) -> str:
    """The sheet's title in the user's Aspen (its header key in the strings read from it), else
    its class's last part as words."""
    key = sh.get("header")
    text = aspen_labels.header(key) if key else None
    if text:
        return text
    cls = str(sh.get("sheet") or "")
    return _plain(cls.rsplit("_", 1)[-1]) if cls else "?"


def where(sh: dict) -> str:
    """'Setup › Kinetics', a subobject id after the form: 'Pack Sizing 1 › Specifications'."""
    form = form_title(sh["form"])
    if sh.get("ids"):
        form += " " + "/".join(sh["ids"])
    return form + aspen_labels.ARROW + sheet_title(sh)


def check_line() -> str:
    """One line for `aspen-mcp --check`."""
    tab = _table()
    if not tab.get("forms"):
        return f"gui-sheets table missing ({TABLE}): check_inputs uses its field walk"
    head = (f"gui-sheets {tab.get('aspen')} build {tab.get('build')} ({len(tab['forms'])} forms, "
            f"{len(tab.get('sheets') or {})} sheets)")
    if os.environ.get(_ENV, "1").strip() == "0":
        return head + f": off ({_ENV}=0)"
    return head + (": fits this Aspen" if fits() else ": not this Aspen's version -- check_inputs uses its field walk")
