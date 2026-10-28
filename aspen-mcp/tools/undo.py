"""Undo planner (values, and inverses of additions): journal
records in, an ordered plan of inverse steps out. Planning only -- it reads the journal and
the restore-point index, never Aspen, and writes nothing; ``check`` / ``apply`` / ``revert``
hand the plan to tools/undo_apply.py, which reads it against the live model and writes it back.

    p = undo.plan(model_id, ids=["e..."])                  # these records (the window's "Undo")
    p = undo.plan(model_id, group="g...")                  # a whole change group
    p = undo.plan(model_id, records=recs, later=newer)     # records in hand; ``later``: newer ones
    undo.preview(p)                                        # the fixed-size dict state.json carries
    undo.check(p, manager, session)                        # live: conflicts, already, gone (no write)
    undo.apply(p, manager, session, on_conflict="skip")    # write it back, journaled (revert_of)
    undo.revert(manager, session, group="g...", dry=True)  # plan + check (+ apply unless dry)

Rules (and the live V15 facts behind them):
  * Repeated changes of one field fold into one step: its target is the earliest record's
    ``before`` (a unit or basis a value-only write did not read is taken from a later before --
    such a write cannot change them; never ``ue``, which every write sets), its ``expect`` the
    latest ``after`` merged over the earlier ones. A loop's / optimization's ``summary`` is its
    ``writes``, one field each.
  * Steps run newest change first. A RadFrac spec switch (clear BR, set QN) comes back as clear
    QN, set BR -- the legal order, and exactly the start again: no exclusion table.
  * A field is emptied by writing "": target value None -> ``how`` "clear". Any write
    sets USERENTERED (attr 11) to 1 and clearing puts the field back to its default with 0,
    so a field recorded with ``ue`` 0 is cleared too; one recorded without ``ue``
    carries ``maybe: ["ue_unknown"]`` -- approximate only when its default (attr 10) equals the
    target, which only a live read tells.
  * Inverses of structure: place_block / place_stream -> remove it; connect_stream ->
    disconnect, reconnect what it displaced, and put back a stream it moved off another port
    (connecting a stream that is already connected moves it, silently). Connects are
    not folded: each is undone in reverse order, so every port it touched comes back as the
    records went. The port a stream was moved off comes from the record's ``moved`` (also read
    as ``moved_from`` / ``other_end`` / ``was_on`` / ``from``: [{"block", "port"}] or port paths;
    [] = it was on no port) or from this plan's own earlier connects; a stream placed in the
    plan was on none; otherwise the step is ``other_end_unknown``.
    A list's row added by insert_row (+ set_label, the inspector's +) -> remove_row it by its label; a
    subobject added by add_element (a pumparound, an internals section) -> remove_element it; a
    value written into that row goes with it. Everything else structural
    -- a removal, another kind of addition, a file patch, any record of a tool whose undo is a
    restore point -- is blocked ``checkpoint_only``, with the group's restore point.
  * An object added and removed within the plan is no change; one the plan found existing and
    removed can only come back from a restore point, and so can every record about it.

Plan:
    {"model", "group", "of": [ids undone], "groups": [the groups of those records, the newest
     first], "redo": bool (every record undone is itself an undo), "steps": [...], "blocked": [...],
     "moot": [...], "info": [...], "conflicts": [...], "conflicts_more": n, "restore_before": {...} | None,
     "needs_checkpoint": bool, "exact": bool, "suggest": "undo" | "restore" | "partial" | "blocked" | "nothing"}

Step (in the order to do them):
    {"key", "kind": value | attr | remove_block | remove_stream | remove_row | remove_element | disconnect
     | reconnect | restore,
     "how": write | clear | remove | disconnect | connect | restore, "session",
     "path" (the field, the object, the port), "attr" (attr), "name" (object; the stream of a
     (dis)connect), "block", "port", "type" (the recorded type of an object to remove),
     "to": what it becomes -- {"value", "unit", "basis", "ue"} (the keys recorded), {"port": [...]}
     "expect": what should be there now, same shape -- None: not measured,
     "of": [record ids], "t": the newest one's time, "n": records folded,
     "approx": [codes] -- known now not to come back exactly; "maybe": [codes] -- checked live,
     "conflict": {"code", "by", "via", "tool", "t", "id", "now", "n"} -- the journal shows a
                 change since by someone else (the live check has the last word),
     "why": displaced | moved, "inferred": bool (reconnect); "checkpoint": id (restore)}
Blocked / moot / info entries: {"code", "key", "of", "t", "op", "path" | "name", ...}; gone /
already / reverted add "since" ({"by", "via", "tool", "t", "id"} of the later record); blocked
checkpoint_only adds "checkpoint" ({"id", "t", "rid", "on_disk"} or {"id": None, "why"}),
no_before_cp "restored" (the point that restore brought back).
``restore_before``: the restore point before the earliest checkpoint_only change, with "then"
(the ids older than it, to undo after restoring: "restore to before this group") and
"later_groups" (groups after it the restore also takes back).

Codes:
    blocked   checkpoint_only, no_before (nothing measured before), gone (removed since),
              no_before_cp (a restore made without saving first), unsupported
    moot      removed_with (a field of an object the plan removes), no_net_change (1.5 -> 2 ->
              1.5; an object added and removed), already (a later change put it back), reverted
              (a later undo did), covered_by_restore (newer than a restore the plan undoes)
    info      results_stay (run / reinit), file_stays (save), session (open / close),
              other_session (a loop's write to another model), or the record's own status when
              it changed nothing: failed | refused | unchanged | error | skipped | unknown
    conflict  changed_since, used_since (an object to remove was edited / connected since),
              displaced_taken, restored_since, later_lost (undoing a restore takes back what
              came after it)
    approx    unit_unknown, basis_unknown (the unit / basis changed; the original was not read),
              other_end_unknown
    maybe     ue_unknown

Stdlib only; no COM. Never raises for bad records: they become info / blocked entries.
"""
from __future__ import annotations

import hashlib
import logging
import math

from tools import checkpoints, journal

logger = logging.getLogger(__name__)

SCAN = 5000                       # journal records collect() reads (newest first)
PREVIEW_MAX, CONFLICTS_MAX, IDS_MAX, GROUPS_MAX = 50, 20, 20, 20
THEN_MAX = 500                    # ids of restore_before.then a preview keeps (the window sends them back)
REL = 1e-9                        # numbers equal within this relative difference
_DONE = frozenset({"changed", "unknown"})      # did something (unknown: written, after not read)
_FIELD = ("value", "unit", "basis", "ue")
_OBJ = ("block", "stream")
_PARTS = ("row", "element")      # a list's row, a subobject: by path -- of these tools only
_PART_TOOLS = frozenset({"insert_row", "remove_row", "add_element", "remove_element"})
_STRUCT = frozenset({"remove_block", "remove_stream", "remove_row", "remove_element", "disconnect", "reconnect"})
_MOVED = ("moved", "moved_from", "other_end", "was_on", "from")


# ---------------------------------------------------------------------------- helpers
def _rk(r) -> tuple:
    t = r.get("t")
    return (float(t) if isinstance(t, (int, float)) else 0.0, str(r.get("id") or ""))


def _up(x) -> str:
    return "" if x is None else str(x).upper()


def _set(x):
    if x is None:
        return None
    return {str(x)} if isinstance(x, (str, int)) else {str(v) for v in x}


def _num(x):
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x))
    except ValueError:
        return None


def _same(a, b) -> bool:
    """Equal as Aspen holds it: "35" is 35.0; numbers within REL."""
    if a == b:
        return True
    x, y = _num(a), _num(b)
    if x is None or y is None:
        return False
    return x == y or (math.isfinite(x) and math.isfinite(y) and math.isclose(x, y, rel_tol=REL, abs_tol=0.0))


def _state(d) -> dict | None:
    """The {"value", "unit", "basis", "ue"} a record measured (ue as 0 / 1)."""
    if not isinstance(d, dict):
        return None
    out = {k: d[k] for k in _FIELD if k in d}
    if "ue" in out:
        u = _num(out["ue"])
        out["ue"] = None if u is None else int(u)
    return out


def _eq(a, b) -> bool:
    """Two states agree on every key both hold (and hold one at least)."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    keys = [k for k in a if k in b]
    return bool(keys) and all(_same(a[k], b[k]) for k in keys)


def _names(v) -> list:
    return [str(x) for x in v] if isinstance(v, list) else []


def _minus(a, b) -> list:
    left = [_up(x) for x in b]
    out = []
    for x in a:
        if _up(x) in left:
            left.remove(_up(x))
        else:
            out.append(x)
    return out


def _has(lst, name) -> bool:
    return any(_up(x) == _up(name) for x in lst)


def _way(port) -> str | None:
    p = _up(port)
    return "in" if p.endswith("(IN)") else "out" if p.endswith("(OUT)") else None


def _port_path(block, port) -> str:
    return rf"\Data\Blocks\{block}\Ports\{port}"


def _okey(tg, tool=None) -> str | None:
    """The object an add / remove record is about: a block or stream by name, a row or a
    subobject by path (a record of _PART_TOOLS: add_reaction's rows stay a restore point's);
    None for any other."""
    k = tg.get("kind")
    if k in _OBJ and tg.get("name"):
        return f"{k}:{_up(tg['name'])}"
    return f"{k}:{_up(tg['path'])}" if k in _PARTS and tg.get("path") and tool in _PART_TOOLS else None


def _obj_key(path) -> str | None:
    lab = journal.label(path)
    for k in _OBJ:
        if lab.get(k):
            return f"{k}:{_up(lab[k])}"
    return None


def _ports(v) -> list:
    """(block, port) pairs from a connect record's moved-from field (see the docstring)."""
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        return [p for x in v for p in _ports(x)]
    if isinstance(v, dict):
        if v.get("block") and v.get("port"):
            return [(str(v["block"]), str(v["port"]))]
        if v.get("path"):
            return _ports(v["path"])
        return [p for x in v.values() for p in _ports(x)]
    s = [x for x in str(v).split("\\") if x]
    if len(s) >= 5 and s[1] == "Blocks" and s[3] == "Ports":
        return [(s[2], s[4])]
    b, sep, p = str(v).partition(":")
    return [(b.strip(), p.strip())] if sep and b.strip() and p.strip() else []


def _undo_class(tool):
    """The tool's ``undo`` column in intercept.TOOLS (value | inverse | checkpoint | none |
    program), None for a name it does not list (the window's own edits, a revert)."""
    if not tool:
        return None
    try:
        from tools import intercept      # server.py has it loaded; read lazily: no import cycle
        spec = intercept.TOOLS.get(str(tool))
    except Exception:
        return None
    return getattr(spec, "undo", None)


def _cp_id(r) -> str | None:
    """The restore point a journal ``checkpoint`` record made or reused."""
    if r.get("reuse"):
        return str(r["reuse"])
    for c in r.get("checkpoints") or ():
        if isinstance(c, dict) and c.get("id") and c.get("reason") != "before-overwrite":
            return str(c["id"])
    return None


def _field_key(path, attr=None) -> str:
    return f"attr:{str(path).lower()}#{attr}" if attr is not None else f"value:{str(path).lower()}"


def _rec_key(r) -> str:
    """The key of what a record changed: a field, an object, a port's stream, else op:id."""
    op = r.get("op")
    tg = r.get("target") if isinstance(r.get("target"), dict) else {}
    if op in ("value", "attr") and tg.get("path"):
        return _field_key(tg["path"], tg.get("attr", r.get("attr")) if op == "attr" else None)
    if op in ("add", "remove") and (_okey(tg, r.get("tool")) or (tg.get("kind") and tg.get("name"))):
        return _okey(tg, r.get("tool")) or f"{tg['kind']}:{_up(tg['name'])}"
    if op == "connect" and tg.get("block"):
        return f"port:{_up(tg['block'])}:{_up(tg.get('port'))}:{_up(tg.get('stream'))}"
    return f"{op}:{r.get('id')}"


def _who(r) -> dict:
    """Who changed it and when: {"by", "via", "tool", "t", "id"} of a later record."""
    out = {"by": r.get("actor"), **{k: r.get(k) for k in ("via", "tool", "t", "id")}}
    return {k: v for k, v in out.items() if v is not None}


def _reverts(r) -> set:
    v = r.get("revert_of")
    return {str(v)} if isinstance(v, str) else {str(x) for x in v} if isinstance(v, list) else set()


# ---------------------------------------------------------------------------- collect
def collect(model: str, ids=None, group=None, scan: int = SCAN) -> tuple[list, list]:
    """(records, later) from the journal: the change records with these ids or of these
    groups (with their groups' ``checkpoint`` records), and every newer record -- what the
    plan checks "changed since" against. One read of the newest ``scan`` records; older ones
    are not found. Never raises: ([], []) when the journal cannot be read."""
    want, gids = _set(ids), _set(group)
    if want is None and gids is None:
        return [], []
    try:
        allr = journal.read(model, limit=scan, kinds=("change",))
    except Exception as exc:
        logger.warning("undo: journal of %r not read (%r)", model, exc)
        return [], []
    mine = [r for r in allr if (want is not None and r.get("id") in want)
            or (gids is not None and r.get("group") in gids)]
    if not mine:
        return [], []
    got, groups = {r.get("id") for r in mine}, {r.get("group") for r in mine if r.get("group")}
    ctx = [r for r in allr if r.get("op") == "checkpoint" and r.get("group") in groups and r.get("id") not in got]
    lo = min(_rk(r) for r in mine)
    return mine + ctx, [r for r in allr if r.get("id") not in got and _rk(r) > lo]


def plan(model: str, ids=None, group=None, *, records=None, later=None, cps=None, scan: int = SCAN) -> dict:
    """The undo plan of records ``ids`` / change group(s) ``group`` (read with ``collect``), or
    of ``records`` (one record or a list; ``ids`` / ``group`` then filter it, keeping every
    ``checkpoint`` record as context) against ``later`` (newer records; none when not given).
    ``cps``: the model's restore points (checkpoints.list_checkpoints; read when needed)."""
    if records is None:
        records, later = collect(model, ids, group, scan)
    else:
        records = [records] if isinstance(records, dict) else list(records or ())
        want, gids = _set(ids), _set(group)
        if want is not None or gids is not None:
            records = [r for r in records if isinstance(r, dict) and (r.get("op") == "checkpoint" or (
                (want is None or r.get("id") in want) and (gids is None or r.get("group") in gids)))]
        later = list(later or ())
    return _Plan(model, group, records, later, cps).run()


# ---------------------------------------------------------------------------- the planner
class _Plan:
    def __init__(self, model, group, records, later, cps):
        recs = sorted((r for r in records if isinstance(r, dict) and r.get("kind", "change") == "change"), key=_rk)
        self.model, self.group, self._cps = model, group, cps
        self.cp_recs = [r for r in recs if r.get("op") == "checkpoint"]
        self.recs = [r for r in recs if r.get("op") != "checkpoint"]
        self.ids = {r.get("id") for r in recs}
        self.later = sorted((r for r in later if isinstance(r, dict) and r.get("kind", "change") == "change"
                             and r.get("id") not in self.ids and r.get("op") != "checkpoint"), key=_rk)
        self.steps, self.blocked, self.moot, self.info = [], [], [], []
        self.folds, self.objs, self.conns, self.restores = {}, {}, [], []
        self.state = {}               # object key -> new | none | removed (by this plan's records)
        tops = [_rk(r) for r in self.recs if r.get("op") == "restore" and r.get("before_cp")
                and isinstance(r.get("target"), dict) and r["target"].get("checkpoint")
                and (r.get("status") or "unknown") in _DONE]
        self.top = min(tops) if tops else None     # the oldest restore this plan undoes

    # -- entries
    def _entry(self, lst, code, rs, key=None, **f):
        rs = rs if isinstance(rs, list) else [rs]
        e = {"code": code, "key": key, "of": [r.get("id") for r in rs], "t": rs[-1].get("t"),
             "op": rs[-1].get("op"), "_rk": _rk(rs[-1]), "_first": rs[0]}
        e.update({k: v for k, v in f.items() if v is not None})
        lst.append(e)
        return e

    def _info(self, code, r, **f):
        return self._entry(self.info, code, r, **f)

    def _block(self, code, rs, key=None, **f):
        rs = rs if isinstance(rs, list) else [rs]
        tg = rs[-1].get("target") if isinstance(rs[-1].get("target"), dict) else {}
        f.setdefault("path", tg.get("path"))
        f.setdefault("name", tg.get("name"))
        return self._entry(self.blocked, code, rs, key or _rec_key(rs[-1]), **f)

    def _step(self, key, kind, how, rs, sub=0, **f):
        rs = rs if isinstance(rs, list) else [rs]
        s = {"key": key, "kind": kind, "how": how, "session": rs[-1].get("session"),
             "of": list(dict.fromkeys(r.get("id") for r in rs)), "t": rs[-1].get("t"), "n": len(rs),
             "approx": [], "maybe": [], "_rk": _rk(rs[-1]), "_sub": sub, "_first": rs[0]}
        s.update({k: v for k, v in f.items() if v is not None})
        self.steps.append(s)
        return s

    def _drop(self, s, lst, code, **f):
        """Move step ``s`` to ``blocked`` / ``moot``."""
        self.steps.remove(s)
        e = {"code": code, "key": s["key"], "of": s["of"], "t": s["t"], "op": s["kind"], "_rk": s["_rk"],
             "_first": s["_first"]}
        for k in ("path", "name", "block", "port", "attr"):
            if s.get(k) is not None:
                e[k] = s[k]
        e.update({k: v for k, v in f.items() if v is not None})
        lst.append(e)

    # -- sorting records out
    def run(self) -> dict:
        for r in self.recs:
            try:
                self._classify(r)
            except Exception as exc:         # a malformed record: say so, plan the rest
                logger.warning("undo: record %s not planned (%r)", r.get("id"), exc)
                self._block("unsupported", r)
        self._objects()
        self._connects()
        self._fields()
        self._restore_steps()
        self._since()
        return self._out()

    def _classify(self, r) -> None:
        op, st = r.get("op"), r.get("status") or "unknown"
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        if op in journal.RUN_OPS:
            return self._info(st if st in ("refused", "failed") else "results_stay", r)
        if op in ("open", "close"):
            return self._info("session", r)
        if op == "save":
            return self._info("file_stays" if st in _DONE else st, r)
        if st not in _DONE:
            return self._info(st, r)
        if self.top is not None and _rk(r) > self.top:
            return self._entry(self.moot, "covered_by_restore", r, _rec_key(r))
        if op == "restore" and tg.get("checkpoint"):
            self.restores.append(r)
            return
        if op in ("add", "remove"):         # blocks, streams, rows, subobjects: added and removed is no change
            if _okey(tg, r.get("tool")):
                self.objs.setdefault(_okey(tg, r.get("tool")), []).append(r)
                return
            return self._block("checkpoint_only", r)
        if _undo_class(r.get("tool")) == "checkpoint":
            return self._block("checkpoint_only", r)
        if op in ("value", "attr"):
            if not tg.get("path"):
                return self._block("unsupported", r)
            n = tg.get("attr", r.get("attr")) if op == "attr" else None
            return self._fold(r, str(tg["path"]), n, r.get("before"), r.get("after"), r.get("req"))
        if op in ("summary", "restore"):
            ws = r.get("writes") if isinstance(r.get("writes"), dict) else {}
            done = 0
            for p, w in ws.items():
                if not isinstance(w, dict):
                    continue
                b, a = w.get("before"), w.get("after")
                wst = w.get("status") or ("changed" if isinstance(b, dict) and isinstance(a, dict) and any(
                    k in a and not _same(v, a[k]) for k, v in b.items()) else "unchanged")
                if wst not in _DONE:
                    continue
                if w.get("session") and w["session"] != r.get("session"):
                    self._info("other_session", r, path=str(p), session=w["session"])
                    continue
                path, n = journal.split_key(p)
                self._fold(r, path, n, b, a, None)
                done += 1
            if not done and not any(e["code"] == "other_session" and r.get("id") in e["of"] for e in self.info):
                self._info("unchanged", r)
            return
        if op == "connect" and tg.get("block") and tg.get("port"):
            self.conns.append(r)
            return
        if op == "patch":
            return self._block("checkpoint_only", r)
        self._block("unsupported", r)

    def _fold(self, r, path, attr, before, after, req) -> None:
        key = _field_key(path, attr)
        f = self.folds.setdefault(key, {"kind": "attr" if attr is not None else "value", "path": path,
                                        "attr": attr, "parts": []})
        f["path"] = path                     # as the latest record spelled it
        f["parts"].append((r, before, after, req if isinstance(req, dict) else {}))

    # -- objects added or removed
    def _objects(self) -> None:
        for key, rs in self.objs.items():
            kind = key.split(":", 1)[0]
            first, last = rs[0].get("op"), rs[-1].get("op")
            if first != "add":
                self.state[key] = "removed"
                self._block("checkpoint_only", rs, key)
            elif last == "add":
                self.state[key] = "new"
                tg = rs[-1]["target"]
                self._step(key, "remove_" + kind, "remove", rs, name=tg.get("name"), path=tg.get("path"),
                           type=tg.get("type"), expect={"exists": True, "type": tg.get("type")},
                           to={"exists": False})
            else:
                self.state[key] = "none"
                self._entry(self.moot, "no_net_change", rs, key, name=rs[-1]["target"].get("name"))

    def _obj_state(self, *keys) -> str | None:
        sts = {self.state.get(k) for k in keys if k}
        return "removed" if "removed" in sts else "none" if "none" in sts else None

    # -- connects: disconnect, put back what it displaced / moved
    def _moved(self, i, c):
        """(ports the stream was moved off, known, inferred) for connect record ``c``."""
        tg = c["target"]
        s, b, p = tg.get("stream"), _up(tg.get("block")), _up(tg.get("port"))
        if not s:
            return [], True, False
        for k in _MOVED:
            if k in c:
                return _ports(c[k]), True, False
        way = _way(p)
        for j in range(i - 1, -1, -1):
            t2 = self.conns[j]["target"]
            b2, p2 = _up(t2.get("block")), _up(t2.get("port"))
            if _up(t2.get("stream")) == _up(s) and way and _way(p2) == way and (b2, p2) != (b, p) \
                    and _has(_names(self.conns[j].get("after")), s):
                for k in range(j + 1, i):
                    t3 = self.conns[k]["target"]
                    if (_up(t3.get("block")), _up(t3.get("port"))) == (b2, p2) and \
                            _has(_names(self.conns[k].get("displaced")) or
                                 _minus(_names(self.conns[k].get("before")), _names(self.conns[k].get("after"))), s):
                        return [], True, False
                return [(t2.get("block"), t2.get("port"))], True, True
        placed = self.objs.get(f"stream:{_up(s)}")
        if placed and placed[0].get("op") == "add" and _rk(placed[0]) < _rk(c):
            return [], True, False
        return [], False, False

    def _connects(self) -> None:
        for i, c in enumerate(self.conns):
            tg = c["target"]
            blk, port, s = tg["block"], tg["port"], tg.get("stream")
            bk, sk = f"block:{_up(blk)}", f"stream:{_up(s)}" if s else None
            before, after = _names(c.get("before")), _names(c.get("after"))
            displaced = _names(c.get("displaced")) or _minus(before, after)
            moved, known, inferred = self._moved(i, c)
            path, pk, sub = tg.get("path") or _port_path(blk, port), f"port:{_up(blk)}:{_up(port)}", 0
            cur = list(after)
            plan = []
            if s and _has(after, s) and not _has(before, s):
                nxt = [x for x in cur if _up(x) != _up(s)]
                plan.append((f"{pk}:{_up(s)}", "disconnect", "disconnect", (bk, sk),
                             dict(block=blk, port=port, name=s, path=path, expect={"port": cur}, to={"port": nxt}),
                             [] if known else ["other_end_unknown"]))
                cur = nxt
            for d in displaced:
                nxt = cur + [d]
                plan.append((f"{pk}:{_up(d)}", "reconnect", "connect", (bk, f"stream:{_up(d)}"),
                             dict(block=blk, port=port, name=d, path=path, why="displaced", expect={"port": cur},
                                  to={"port": nxt}), []))
                cur = nxt
            for b1, p1 in moved:
                plan.append((f"port:{_up(b1)}:{_up(p1)}:{_up(s)}", "reconnect", "connect", (f"block:{_up(b1)}", sk),
                             dict(block=b1, port=p1, name=s, path=_port_path(b1, p1), why="moved",
                                  inferred=inferred or None), []))
            for key, kind, how, objs, f, approx in plan:
                st = self._obj_state(*objs)
                where = {k: f[k] for k in ("name", "block", "port", "path")}
                if st == "removed":
                    self._block("checkpoint_only", c, key, **where)
                elif st == "none":
                    self._entry(self.moot, "no_net_change", c, key, **where)
                else:
                    self._step(key, kind, how, c, sub=sub, **f)["approx"] += approx
                sub += 1

    # -- values and attributes
    def _fields(self) -> None:
        for key, f in self.folds.items():
            parts = f["parts"]
            rs = [p[0] for p in parts]
            where = dict(path=f["path"], attr=f["attr"])
            obj = _obj_key(f["path"])
            if self.state.get(obj) is None and self.state.get("row:" + _up(f["path"])):
                obj = "row:" + _up(f["path"])          # a value of a row the plan adds
            st = self.state.get(obj)
            if st == "removed":
                self._block("checkpoint_only", rs, key, **where)
                continue
            if st in ("new", "none"):
                self._entry(self.moot, "removed_with" if st == "new" else "no_net_change", rs, key,
                            with_=obj, **where)
                continue
            to = _state(parts[0][1])
            if not to or "value" not in to:
                self._block("no_before", rs, key, **where)
                continue
            for _, b, _, _ in parts[1:]:      # not ue: any write sets it to 1
                for k, v in (_state(b) or {}).items():
                    if k in ("unit", "basis"):
                        to.setdefault(k, v)
            expect = None
            for _, _, a, _ in parts:
                a = _state(a)
                if a is not None:
                    expect = {**(expect or {}), **a}
            if f["kind"] == "attr":
                to, expect = {"value": to["value"]}, None if expect is None else {"value": expect.get("value")}
            if expect is not None and _eq(to, expect):
                self._entry(self.moot, "no_net_change", rs, key, **where)
                continue
            approx, maybe = [], []
            if f["kind"] == "value":
                for k, code in (("unit", "unit_unknown"), ("basis", "basis_unknown")):
                    if k not in to and any(k in req or (isinstance(a, dict) and k in a and (
                            not isinstance(b, dict) or k not in b or not _same(b[k], a[k])))
                            for _, b, a, req in parts):
                        approx.append(code)
                how = "clear" if to.get("value") is None or to.get("ue") == 0 else "write"
                if how == "write" and "ue" not in to:
                    maybe.append("ue_unknown")
            else:
                how = "write"
            s = self._step(key, f["kind"], how, rs, to=to, **where)
            s["expect"], s["approx"], s["maybe"] = expect, approx, maybe

    # -- restores of a restore point (H): undone by restoring what was saved before it
    def _restore_steps(self) -> None:
        for r in self.restores:
            key = f"restore:{r.get('id')}"
            if not r.get("before_cp"):
                self._block("no_before_cp", r, key, restored=r["target"].get("checkpoint"))
            else:
                self._step(key, "restore", "restore", r, checkpoint=str(r["before_cp"]),
                           restored=r["target"].get("checkpoint"))

    # -- what the journal says happened since
    def _index(self):
        ix = {"field": {}, "objop": {}, "touch": {}, "port": {}, "stream": {}, "restore": [], "input": []}

        def put(kind, k, item):
            ix[kind].setdefault(k, []).append(item)
        for r in self.later:
            op, st, rk = r.get("op"), r.get("status") or "unknown", _rk(r)
            if st not in _DONE:
                continue
            tg = r.get("target") if isinstance(r.get("target"), dict) else {}
            if op in journal.INPUT_OPS:
                ix["input"].append((rk, r))
            if op == "restore" and tg.get("checkpoint"):
                ix["restore"].append((rk, r))
                continue
            fields = []
            if op in ("value", "attr") and tg.get("path"):
                n = tg.get("attr", r.get("attr")) if op == "attr" else None
                fields.append((str(tg["path"]), n, r.get("before"), r.get("after")))
            elif op in ("summary", "restore") and isinstance(r.get("writes"), dict):
                for p, w in r["writes"].items():
                    if isinstance(w, dict) and w.get("status", "changed") in _DONE and not w.get("session"):
                        path, n = journal.split_key(p)
                        fields.append((path, n, w.get("before"), w.get("after")))
            for path, n, b, a in fields:
                put("field", _field_key(path, n), (rk, r, b, a))
                obj = _obj_key(path)
                if obj:
                    put("touch", obj, (rk, r))
            if op in ("add", "remove") and _okey(tg, r.get("tool")):
                put("objop", _okey(tg, r.get("tool")), (rk, r, op))
            if op == "connect" and tg.get("block"):
                put("port", f"port:{_up(tg['block'])}:{_up(tg.get('port'))}", (rk, r))
                put("touch", f"block:{_up(tg['block'])}", (rk, r))
                moved = {_up(x) for x in _names(r.get("displaced"))} | ({_up(tg["stream"])} if tg.get("stream") else set())
                for x in moved:                   # the streams it connected or took off a port
                    put("stream", x, (rk, r))
                    put("touch", f"stream:{x}", (rk, r))
        return ix

    def _since(self) -> None:
        if not self.later:
            return
        ix = self._index()

        def after(kind, k, rk):
            return [x for x in ix[kind].get(k, ()) if x[0] > rk]

        def removed(objs, rk):
            """The latest later remove of any of these objects, else None."""
            hits = [x for o in objs if o for x in after("objop", o, rk) if x[2] == "remove"]
            return max(hits, key=lambda x: x[0])[1] if hits else None

        for s in list(self.steps):
            rk, kind = s["_rk"], s["kind"]
            if kind == "restore":
                lost = [x for x in ix["input"] if x[0] > rk]
                if lost:
                    groups = list(dict.fromkeys(x[1].get("group") for x in lost if x[1].get("group")))
                    s["conflict"] = {"code": "later_lost", "n": len(lost), "groups": groups[:GROUPS_MAX],
                                     **_who(lost[-1][1])}
                continue
            if kind in ("value", "attr"):
                gone = removed([_obj_key(s["path"]), "row:" + _up(s["path"])], rk)
                if gone is not None:
                    self._drop(s, self.blocked, "gone", since=_who(gone))
                    continue
                if self._field_since(s, after("field", s["key"], rk)):
                    continue
            elif kind in ("remove_block", "remove_stream", "remove_row", "remove_element"):
                ops = after("objop", s["key"], rk)
                if ops and ops[-1][2] == "remove":
                    self._drop(s, self.moot, "already", since=_who(ops[-1][1]))
                    continue
                used = {id(x[1]): x for x in ops + after("touch", s["key"], rk)}
                if used:
                    last = max(used.values(), key=lambda x: x[0])[1]
                    s["conflict"] = {"code": "used_since", "n": len(used), **_who(last)}
            else:                                     # disconnect / reconnect
                gone = removed([f"block:{_up(s['block'])}", f"stream:{_up(s['name'])}"], rk)
                if gone is not None:
                    self._drop(s, self.moot if kind == "disconnect" else self.blocked,
                               "already" if kind == "disconnect" else "gone", since=_who(gone))
                    continue
                self._port_since(s, after("port", f"port:{_up(s['block'])}:{_up(s['port'])}", rk),
                                 after("stream", _up(s["name"]), rk))
            rest = [x for x in ix["restore"] if x[0] > rk]
            if rest and "conflict" not in s:
                s["conflict"] = {"code": "restored_since", **_who(rest[-1][1])}

    def _field_since(self, s, later) -> bool:
        """Later writes of the step's field: an undo of its own records moves what is expected;
        anyone else's is a conflict, unless the field came back. True: the step was dropped."""
        if not later:
            return False
        mine, cur, foreign, rev = set(s["of"]), s.get("expect"), None, False
        for _, r, _b, a in later:
            rev = bool(mine & _reverts(r))
            a = _state(a)
            if a is not None:
                cur = {**(cur or {}), **a} if s["kind"] == "value" else {"value": a.get("value")}
            if not rev:
                foreign = r
        if _eq(s["to"], cur):
            self._drop(s, self.moot, "reverted" if rev else "already", since=_who(later[-1][1]))
            return True
        if foreign is not None and not _eq(cur, s.get("expect")):
            s["conflict"] = {"code": "changed_since", "now": cur, "n": len(later), **_who(foreign)}
        elif cur is not None:
            s["expect"] = cur
        return False

    def _port_since(self, s, on_port, of_stream) -> None:
        """Later connects on the step's port or of its stream. A disconnect minds only those
        that took its stream off the port (another stream added beside it moves ``expect``);
        a reconnect minds any: the stream may be taken, the port may hold another now."""
        name, hits = _up(s["name"]), {}
        for x in sorted(on_port + of_stream, key=lambda x: x[0]):
            r = x[1]
            if s["kind"] == "disconnect" and x in on_port and _up(r["target"].get("stream")) != name:
                aft = _names(r.get("after"))
                if _has(aft, name) and not _has(_names(r.get("displaced")), name):
                    s["expect"] = {"port": aft}
                    s["to"] = {"port": [v for v in aft if _up(v) != name]}
                    continue
            hits[id(r)] = r
        if hits:
            last = list(hits.values())[-1]
            code = "displaced_taken" if s.get("why") == "displaced" else "changed_since"
            s["conflict"] = {"code": code, "n": len(hits), **_who(last)}

    # -- restore points of the blocked changes
    def _cps_live(self) -> list:
        if self._cps is None:
            try:
                self._cps = checkpoints.list_checkpoints(self.model)
            except Exception as exc:
                logger.warning("undo: restore points of %r not read (%r)", self.model, exc)
                self._cps = []
        return self._cps

    def _cp_for(self, r) -> dict | None:
        """The restore point made (or reused) for record ``r``'s group before ``r``: the
        group's journaled checkpoint record, else the index's point of that group."""
        g, rk = r.get("group"), _rk(r)
        if not g:
            return None
        best = None
        for c in self.cp_recs:
            if c.get("group") == g and _rk(c) <= rk:
                best = c
        if best is not None:
            cid = _cp_id(best)
            if cid is None:
                return {"id": None, "why": best.get("why") or best.get("status") or "none",
                        "est_s": best.get("est_s"), "t": best.get("t"), "rid": best.get("id")}
            return {"id": cid, "t": best.get("t"), "rid": best.get("id"), "_rk": _rk(best)}
        hits = [e for e in self._cps_live() if e.get("group") == g and e.get("id")
                and float(e.get("t") or 0) <= rk[0]]
        if hits:
            e = max(hits, key=lambda e: float(e.get("t") or 0))
            return {"id": e["id"], "t": e.get("t"), "rid": None, "_rk": (float(e.get("t") or 0), "")}
        return None

    def _checkpoints(self) -> dict | None:
        def view(cp):
            return {k: v for k, v in cp.items() if not k.startswith("_") and (v is not None or k == "id")}
        first, first_cp = None, None
        for e in self.blocked:
            if e["code"] != "checkpoint_only":
                continue
            cp = self._cp_for(e["_first"])
            if cp is not None and cp.get("id"):
                cp["on_disk"] = any(x.get("id") == cp["id"] for x in self._cps_live())
            e["checkpoint"] = view(cp) if cp else None
            if first is None or _rk(e["_first"]) < _rk(first):
                first, first_cp = e["_first"], cp
        if first_cp is None or not first_cp.get("id"):
            return view(first_cp) if first_cp else None
        crk = first_cp["_rk"]
        older = {r.get("id") for r in self.recs if _rk(r) < crk}
        then = [i for s in sorted(self.steps, key=lambda s: s["_rk"]) for i in s["of"] if i in older]
        groups = [r.get("group") for r in self.later if _rk(r) > crk and r.get("group")
                  and r.get("op") in journal.INPUT_OPS and (r.get("status") or "unknown") in _DONE]
        return {**view(first_cp), "then": list(dict.fromkeys(then)),
                "later_groups": list(dict.fromkeys(groups))[:GROUPS_MAX]}

    # -- the result
    def _out(self) -> dict:
        rb = self._checkpoints()
        self.steps.sort(key=lambda s: (s["_rk"], -s["_sub"]), reverse=True)
        for lst in (self.steps, self.blocked, self.moot, self.info):
            for e in lst:
                if "with_" in e:
                    e["with"] = e.pop("with_")
                for k in [k for k in e if k.startswith("_")]:
                    del e[k]
        conflicts = [{"key": s["key"], "kind": s["kind"], **{k: s[k] for k in ("path", "name", "attr") if k in s},
                      "expect": s.get("expect"), **s["conflict"]} for s in self.steps if s.get("conflict")]
        done = {i for s in self.steps for i in s["of"]}
        undone = [r for r in self.recs if r.get("id") in done]
        blocked_cp = any(e["code"] == "checkpoint_only" for e in self.blocked)
        if self.steps and not self.blocked:
            suggest = "undo"
        elif blocked_cp and rb and rb.get("id") and rb.get("on_disk"):
            suggest = "restore"
        elif self.steps:
            suggest = "partial"
        else:
            suggest = "blocked" if self.blocked else "nothing"
        return {"model": self.model, "group": self.group, "of": [r.get("id") for r in undone],
                "groups": list(dict.fromkeys(r["group"] for r in reversed(undone) if r.get("group"))),
                "redo": bool(undone) and all(r.get("revert_of") for r in undone),
                "steps": self.steps, "blocked": self.blocked, "moot": self.moot, "info": self.info,
                "conflicts": conflicts[:CONFLICTS_MAX], "conflicts_more": max(0, len(conflicts) - CONFLICTS_MAX),
                "restore_before": rb,
                "needs_checkpoint": any(s["kind"] in _STRUCT or s["kind"] == "restore" for s in self.steps),
                "exact": not self.blocked and not any(s["approx"] for s in self.steps),
                "suggest": suggest}


# ---------------------------------------------------------------------------- the window's copy
def _short(e: dict) -> dict:
    e = dict(e)
    if isinstance(e.get("of"), list) and len(e["of"]) > IDS_MAX:
        e["of_n"], e["of"] = len(e["of"]), e["of"][:IDS_MAX]
    return e


def sig(p) -> str:
    """The steps of plan ``p`` (or a list of step keys) in order, as a short hash: what the window
    sends back as ``seen`` when the user confirms a preview -- revert() applies only a plan
    whose steps are still those."""
    keys = [s.get("key") for s in p.get("steps") or ()] if isinstance(p, dict) else list(p or ())
    return hashlib.sha1("\n".join(str(k) for k in keys).encode("utf-8")).hexdigest()[:16]


def preview(p: dict, limit: int = PREVIEW_MAX) -> dict:
    """A plan cut to a fixed size for state.json's ``undo_req.preview``: at most ``limit`` steps,
    blocked and moot entries, info folded by code ({"code", "n", "of"}), the conflicts as
    planned, id lists cut to IDS_MAX (``of_n`` / ``then_n``: how many there were; the restore's
    ``then`` to THEN_MAX -- the window's "restore to before this group" sends them back);
    ``n`` counts everything; ``sig`` the steps' ``sig`` (``seen``)."""
    info = {}
    for e in p.get("info") or ():
        i = info.setdefault(e.get("code"), {"code": e.get("code"), "n": 0, "of": []})
        i["n"] += 1
        i["of"] = (i["of"] + (e.get("of") or []))[:IDS_MAX]
    lists = {k: p.get(k) or [] for k in ("steps", "blocked", "moot")}
    out = {k: p.get(k) for k in ("model", "group", "redo", "suggest", "exact", "needs_checkpoint",
                                 "conflicts", "conflicts_more")}
    rb = p.get("restore_before")
    if rb and len(rb.get("then") or ()) > THEN_MAX:
        rb = {**rb, "then": rb["then"][:THEN_MAX], "then_n": len(rb["then"])}
    out["restore_before"] = rb
    out.update({k: [_short(e) for e in v[:limit]] for k, v in lists.items()})
    out["info"] = list(info.values())[:limit]
    out["n"] = {**{k: len(v) for k, v in lists.items()}, "info": len(p.get("info") or ()),
                "approx": sum(bool(s.get("approx")) for s in lists["steps"]),
                "conflicts": len(p.get("conflicts") or ()) + (p.get("conflicts_more") or 0)}
    out["sig"] = sig(p)
    return out


# ---------------------------------------------------------------------------- carrying it out
# tools/undo_apply.py reads Aspen and writes; it is imported on first use (it imports this module).
def check(p: dict, manager, session=None) -> dict:
    """undo_apply.check: plan ``p`` against the live model -- conflicts, already, gone; no write."""
    from tools import undo_apply
    return undo_apply.check(p, manager, session)


def apply(p: dict, manager, session=None, **kw) -> dict:
    """undo_apply.apply: carry plan ``p`` out (``on_conflict`` abort | skip | force, ``actor``,
    ``via``, ``checked``, ``restore``), every write journaled with ``revert_of``."""
    from tools import undo_apply
    return undo_apply.apply(p, manager, session, **kw)


def revert(manager, session=None, model=None, ids=None, group=None, **kw) -> dict:
    """undo_apply.revert: plan (from the journal), check and -- unless ``dry`` -- apply."""
    from tools import undo_apply
    return undo_apply.revert(manager, session, model, ids, group, **kw)
