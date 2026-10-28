"""Recording scopes: every change to a model measured where it happens, and handed to
the journal (tools/journal.py) in one append per scope and model.

    with recorder.scope(actor="ai", via="mcp", session="demo", model=mid, group=g,
                        call=c, tool="set_value", reason=r) as s:
        manager.set_node_value(...)         # measured before and after, one record each
    # on exit: flush -> journal.append once per model touched

The hook is ``AspenPlusManager.set_node_value`` / ``set_node_attribute``: they call
``current()`` -- None outside a scope, so there it costs one ContextVar lookup and no COM
read -- and hand the node they already found to ``Scope.before`` / ``value`` / ``attr``.
``checkpoints.py`` reports its backups and writes through ``event()``.

``Scope``: one record per write (``value`` / ``attr``), one ``save`` record for the file
events, and whatever ``add()`` is given (probes, errors). ``Aggregate`` (a sweep, a seek, an
optimization): each path read once before its first write and once when the scope ends,
then a single ``summary``. The innermost scope is current; a scope opened inside an
Aggregate joins it. A summary goes into the enclosing scope when there is one (one append
per call), else straight to the journal.

What a write costs: a value-only
write reads the node's Value before and after -- two COM round trips -- and nothing else,
because it cannot change the unit or the basis (so its record has neither). A write that
sets a unit or a basis reads Value, UnitString and basis (AttributeValue 13) before and
after. The after side is read when the scope settles (its flush, or the same path written
again, whose before-read then serves as the earlier write's after), not right after the
write. Each read is one IDispatch::Invoke by DISPID (tools/dispid.py).

A call's single write (not a batch) also reads USERENTERED (attribute 11)
on both sides, its ``ue``: a field at its default reads the default, not None, so only ue
tells "typed 25" from "left at 25" -- any write makes it 1, emptying the field makes it 0
(V15) -- and an undo knows to empty the field again. The first write of a flush
reads it; a second write in the same flush makes the call a batch, whose items carry no ue
(the first one's is dropped), so a batch costs one read more in all.

``ASPEN_MCP_JOURNAL=0`` makes scopes inert: no reads, no records. Nothing here raises into
the write it measures; a failure is logged and that record degrades or is dropped.
Stdlib only, no I/O at import; COM only through the nodes the manager passes in.
"""
from __future__ import annotations

import contextvars
import logging
import math
import numbers
import time

from tools import dispid, journal

logger = logging.getLogger(__name__)

_CUR: contextvars.ContextVar = contextvars.ContextVar("aspen_mcp_recorder", default=None)
_perf = time.perf_counter
_FILE = object()                  # where a scope's file record goes among its records
LIST_MAX = 50                     # file events / other ops kept per record
BASIS = 13                        # HAP_BASIS
UE = 11                           # HAP_USERENTERED: 1 a value someone entered, 0 default / empty


def current():
    """The innermost recording scope of this task / thread, or None."""
    return _CUR.get()


def event(kind: str, **fields) -> None:
    """A file event (``checkpoint``: a backup or export was made; ``write``: the server wrote
    or failed to write a model file) for the current scope; nothing outside one."""
    s = _CUR.get()
    if s is not None:
        try:
            s.event(kind, fields)
        except Exception as exc:
            logger.warning("recorder: %s event lost (%r)", kind, exc)


# ---------------------------------------------------------------------------- COM reads
def read_state(node, unit: bool = True, basis: bool = True, ue: bool = False) -> dict:
    """{"value", "unit", "basis", "ue"} of a node as it is now (unit / basis / ue only where
    asked); "" reads as None; a read that fails is left out, and so is a ue the node has none
    of."""
    out = {}
    for key, name, args, want in (("value", "Value", (), True), ("unit", "UnitString", (), unit),
                                  ("basis", "AttributeValue", (BASIS,), basis)):
        if want:
            try:
                v = dispid.get(node, name, *args)
                out[key] = None if v == "" else v
            except Exception:
                pass
    if ue:
        try:
            v = dispid.get(node, "AttributeValue", UE)
            if v is not None and v != "":
                out["ue"] = int(v)
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------- record helpers
def _same(a, b) -> bool:
    if a == b:
        return True
    return isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b)


def _status(before, after, how) -> str:
    """By measurement: changed when a value read on both sides differs; a write that did not
    happen (refused / raised) and changed nothing is failed."""
    if not before or not after:
        return "failed" if how != "written" else "unknown"
    if any(k in before and not _same(before[k], v) for k, v in after.items()):
        return "changed"
    return "unchanged" if how == "written" else "failed"


def _num(x):
    if isinstance(x, bool):
        return None
    if isinstance(x, numbers.Real):
        f = float(x)
        return f if math.isfinite(f) else None
    if isinstance(x, str):
        try:
            f = float(x)
        except ValueError:
            return None
        return f if math.isfinite(f) else None
    return None


def _json(d):
    """A dict of COM reads / request values, JSON-safe; the common case (numbers, short
    strings, None) without journal.clean's walk."""
    if d is None:
        return None
    for v in d.values():
        t = type(v)
        if not (v is None or t is int or t is bool or (t is float and math.isfinite(v))
                or (t is str and len(v) <= journal.VALUE_MAX)):
            return journal.clean(d)
    return d


def _req(value, unit, basis) -> dict:
    return {k: v for k, v in (("value", value), ("unit", unit), ("basis", basis)) if v is not None}


def _cut(s, n):
    s = s if isinstance(s, str) else str(s)
    return s if len(s) <= n else s[:n]


# ---------------------------------------------------------------------------- scopes
class _W:
    """One measured write, until its record is built."""
    __slots__ = ("op", "t", "session", "path", "req", "before", "after", "status", "res", "item",
                 "attr", "node", "how")

    def __init__(self, op, t, session, path, req, before, after, status, res, item, attr=None):
        self.op, self.t, self.session, self.path, self.req = op, t, session, path, req
        self.before, self.after, self.status, self.res, self.item = before, after, status, res, item
        self.attr, self.node, self.how = attr, None, None


class Scope:
    """One tool call, program statement or hand edit: each write inside it is measured and
    becomes a record; ``flush()`` (and leaving the ``with``) appends them to the journal.

    ``group`` is the dict ``journal.GROUPS`` returned (or its id); ``extra`` fields go into
    every record (e.g. ``sid``, a program statement's id). Set ``item`` while running item k
    of a batch (else writes are numbered in order), ``file_op`` when the file events are not a
    ``save`` (a layout's ``patch``) and ``file_extra`` for fields of that file record (its
    ``reopened``). ``count``: records pending or written so far. ``jt``: seconds spent
    measuring and building records -- the ``jms`` of a flush. It is an upper bound: Aspen
    finishes each write asynchronously (~0.2 ms, live V15) and whichever COM call comes next
    waits for it, sometimes one of these reads. The net cost is an A/B against
    ASPEN_MCP_JOURNAL=0."""

    def __init__(self, actor=None, via=None, session=None, model=None, group=None, call=None,
                 tool=None, reason=None, **extra):
        self.actor, self.via, self.session, self.model = actor, via, session, model
        self.group = group.get("id") if isinstance(group, dict) else group
        self.call, self.tool, self.reason = call, tool, reason
        self.extra = {k: v for k, v in extra.items() if v is not None}
        self.on = journal.enabled()
        self.item, self.file_op, self.manager = None, None, None
        self.file_extra: dict = {}
        self.jt, self.n = 0.0, 0
        self._pend: list = []          # writes (_W), added records (no id yet) and _FILE
        self._open: dict = {}          # (session, path) -> its last write, after side not read yet
        self._ev: list = []            # (kind, t, fields) of the file events
        self._k = 0                    # writes seen, the default item number
        self._ue = None                # the flush's first write, its ue read (until a second write)
        self._tok = self._join = None
        self._t0 = None
        self._told = False             # the call's reason is on a record already

    # -- context
    def __enter__(self):
        self._t0 = _perf()
        if self.on:
            cur = _CUR.get()
            if isinstance(cur, Aggregate) and cur.on:
                self._join = cur       # inside a loop: its summary covers this too
            else:
                if cur is not None:
                    cur.settle()       # its open writes' after sides, before this scope writes
                if self.call is None:
                    self.call = getattr(cur, "call", None) or journal.new_id("c")
                self._tok = _CUR.set(self)
        return self

    def __exit__(self, et, ev, tb):
        if self._tok is not None:
            _CUR.reset(self._tok)
            self._tok = None
            try:
                self.flush(ms=(_perf() - self._t0) * 1e3)
            except Exception as exc:
                logger.warning("recorder: flush of %s failed (%r)", self.tool, exc)
        return False

    @property
    def count(self) -> int:
        """Records this scope holds so far, pending or written (a probe's at-least-one mark)."""
        return len(self._pend) + self.n

    # -- the value hook (AspenPlusManager.set_node_value)
    def before(self, session, path, node, unit=None, basis=None):
        """The node before a write: its Value; also UnitString and basis when the write sets
        a unit or a basis; and ue when it is the flush's first write and not a batch item.
        The same read is the after side of this path's previous write in the scope, if that
        one is still open. Never raises."""
        t = _perf()
        try:
            full = unit is not None or basis is not None
            if self._ue is not None:
                self._drop_ue()
            st = read_state(node, unit=full, basis=full, ue=self._k == 0 and self.item is None)
            w = self._open.pop((session, path), None) if self._open else None
            if w is not None:
                self._settle(w, st)
            return st
        except Exception:
            return None
        finally:
            self.jt += _perf() - t

    def value(self, manager, session, path, node, before, req, res, how) -> None:
        """A write ``how`` = "written", "refused" (nothing was written: no node, not
        enterable, unit does not fit...) or "error" (it raised). Refused: after = before. A
        write that raised is read again at once. A written one is read when the scope settles
        (flush, or the same path written again): read right after the write, the read would
        wait for Aspen's own processing of the change -- time the next COM call spends
        anyway -- and count it as the recorder's (live V15: 0.29 ms gross, ~0.07 net). Never
        raises."""
        t = _perf()
        try:
            self.manager = self.manager or manager
            w = _W("value", journal.now(), session, path, _req(*req), before, None, None, res, self._item())
            w.how = how
            if node is None or before is None:
                w.status = _status(before, None, how)
            elif how == "refused":
                w.after, w.status = before, _status(before, before, how)
            elif how == "written":
                w.node = node
                self._open[(session, path)] = w
            else:
                w.after = read_state(node, unit="unit" in before, basis="basis" in before, ue="ue" in before)
                w.status = _status(before, w.after, how)
            if before and "ue" in before:
                self._ue = w
            self._pend.append(w)
        except Exception as exc:
            logger.warning("recorder: write of %s not recorded (%r)", path, exc)
        finally:
            self.jt += _perf() - t

    def settle(self) -> None:
        """Read the after side of every write still open. flush() does it; call it yourself
        before something that could change those inputs other than a write (none known: a
        run leaves inputs as they are). Never raises."""
        if not self._open:
            return
        t = _perf()
        for w in list(self._open.values()):
            self._settle(w)
        self._open.clear()
        self.jt += _perf() - t

    @staticmethod
    def _settle(w, have=None) -> None:
        try:
            if have is not None and all(k in have for k in w.before):
                w.after = {k: have[k] for k in w.before}
            else:
                w.after = read_state(w.node, unit="unit" in w.before, basis="basis" in w.before,
                                     ue="ue" in w.before)
        except Exception:
            w.after = None
        w.status, w.node = _status(w.before, w.after, w.how), None

    def _drop_ue(self) -> None:
        """A second write in the flush: the call is a batch, whose items carry no ue --
        the first write's goes too, and its status is measured without it."""
        w, self._ue = self._ue, None
        try:
            for d in (w.before, w.after):
                if isinstance(d, dict):
                    d.pop("ue", None)
            if w.after is not None and w.node is None:
                w.status = _status(w.before, w.after, w.how)
        except Exception as exc:
            logger.warning("recorder: ue of %s not dropped (%r)", w.path, exc)

    # -- the attribute hook (AspenPlusManager.set_node_attribute)
    def attr_before(self, session, path, node, n):
        t = _perf()
        try:
            w = self._open.pop((session, path), None) if self._open else None
            if w is not None:
                self._settle(w)            # an attribute (a basis) may change how the value reads
            return {"value": dispid.get(node, "AttributeValue", n)}
        except Exception:
            return None
        finally:
            self.jt += _perf() - t

    def attr(self, manager, session, path, node, n, attribute, value, before, after, res, how) -> None:
        """An attribute write; ``after`` is the manager's own read-back when it wrote."""
        t = _perf()
        try:
            self.manager = self.manager or manager
            if node is None or before is None:
                aft = None
            elif how == "written":
                aft = {"value": after}
            elif how == "refused":
                aft = before
            else:
                aft = self.attr_before(session, path, node, n)
            req = {"value": value, "attr": attribute}
            self._pend.append(_W("attr", journal.now(), session, path, req, before, aft,
                                 _status(before, aft, how), res, self._item(), n))
        except Exception as exc:
            logger.warning("recorder: attribute write of %s not recorded (%r)", path, exc)
        finally:
            self.jt += _perf() - t

    def _item(self):
        k = self.item if self.item is not None else self._k
        self._k += 1
        return k

    # -- other records
    def event(self, kind, fields) -> None:
        if self._join is not None:
            return self._join.event(kind, fields)
        if not self.on:
            return
        if not self._ev:
            self._pend.append(_FILE)
        if len(self._ev) < LIST_MAX:
            self._ev.append((kind, journal.now(), fields))

    def add(self, op, **fields) -> dict | None:
        """A record the caller measured itself (a probe, an error): ``op`` plus ``fields``;
        session, model, item and the scope's own fields are filled in unless given."""
        if self._join is not None:
            return self._join.add(op, **fields)
        if not self.on:
            return None
        rec = {"op": op, "t": journal.now(), **{k: v for k, v in fields.items() if v is not None}}
        if "item" not in rec and self.item is not None:
            rec["item"] = self.item
        self._pend.append(rec)
        return rec

    # -- flush
    def flush(self, ms=None, **last) -> list[dict]:
        """Append what is pending, one journal.append per model: the call's ``reason`` on its
        first record, ``ms`` and ``jms`` (and ``last``) on this flush's last. Returns the
        records written (or spilled)."""
        if not self.on or not self._pend:
            return []
        t = _perf()
        try:
            self.settle()
            recs = self._build()
            if recs:
                if self.reason is not None and not self._told and str(self.reason).strip():
                    recs[0]["reason"] = _cut(self.reason, journal.REASON_MAX)
                    self._told = True
                if ms is not None:
                    recs[-1]["ms"] = round(ms, 1)
                if last:
                    recs[-1].update(journal.clean({k: v for k, v in last.items() if v is not None}))
                recs[-1]["jms"] = round((self.jt + _perf() - t) * 1e3, 2)
            self._append(recs)
            self.n += len(recs)
            return recs
        except Exception as exc:
            logger.warning("recorder: %d records of %s lost (%r)", len(self._pend), self.tool, exc)
            return []
        finally:
            self._pend, self._ev, self._open, self.jt = [], [], {}, 0.0
            self.file_extra, self._k, self._ue = {}, 0, None     # items are numbered within a flush (a call)

    def _append(self, recs) -> None:
        by, files = {}, {}
        for r in recs:
            mid = r.get("model")
            if mid:
                by.setdefault(mid, []).append(r)
                files.setdefault(mid, r.get("session"))
        m = self.manager
        for mid, lines in by.items():
            path = None
            if m is not None and files[mid]:
                try:
                    path = m.session_file(files[mid])
                except Exception:
                    pass
            journal.append(mid, lines, path=path)

    def _model(self, session, cache):
        if session in cache:
            return cache[session]
        mid = self.model if session == self.session else None
        if mid is None and self.manager is not None and session:
            try:
                mid = self.manager.model_id(session)
            except Exception:
                mid = None
        cache[session] = mid
        return mid

    def _head(self, t, session, model, srv) -> dict:
        rec = {"v": 1, "kind": "change", "id": journal.new_id("e", t), "t": round(t, 3), "srv": srv}
        for k, v in (("model", model), ("session", session), ("actor", self.actor), ("via", self.via),
                     ("group", self.group), ("call", self.call), ("tool", self.tool)):
            if v is not None:
                rec[k] = v
        if self.extra:
            rec.update(self.extra)
        return rec

    def _build(self) -> list[dict]:
        srv, models, out = journal.srv(), {}, []
        for p in self._pend:
            if p is _FILE:
                rec = self._file_record(srv, models)
            elif isinstance(p, _Built):
                rec = dict(p)
                rec["id"] = journal.new_id("e", rec["t"])     # in order with this flush's records
            elif isinstance(p, dict):
                p = dict(p)
                session = p.pop("session", None) or self.session
                model = p.pop("model", None) or self._model(session, models)
                rec = self._head(p.pop("t"), session, model, srv)
                rec.update(journal.clean(p))
            else:
                rec = self._head(p.t, p.session, self._model(p.session, models), srv)
                target = journal.label(p.path)
                if p.op == "attr":
                    target["attr"] = p.attr
                rec.update(item=p.item, op=p.op, target=target, req=_json(p.req), before=_json(p.before),
                           after=_json(p.after), status=p.status or "unknown",
                           result=_cut(p.res, journal.RESULT_MAX))
                if p.before is None:
                    del rec["before"], rec["after"]
            if rec is not None:
                out.append(rec)
        return out

    def _file_record(self, srv, models) -> dict | None:
        """One record for the scope's file events: ``writes`` [{path, ok, backup, error}] and
        the ``checkpoints`` made, plus ``file_extra``; op ``save`` unless ``file_op`` says
        otherwise."""
        writes, cps, first = [], [], None
        for kind, t, f in self._ev:
            first = first or (t, f)
            if kind == "write":
                w = {"path": f.get("path"), "ok": bool(f.get("ok")), "backup": f.get("backup")}
                if f.get("error"):
                    w["error"] = _cut(f["error"], journal.RESULT_MAX)
                writes.append({k: v for k, v in w.items() if v is not None})
            elif kind == "checkpoint":
                c = {k: f.get(k) for k in ("id", "class", "reason", "source", "orig", "name", "pinned",
                                           "state", "secs")}
                cps.append({k: v for k, v in c.items() if v is not None})
                if f.get("model"):
                    cps[-1]["model"] = f["model"]
        if not first:
            return None
        t, f = first
        wev = next((x[2] for x in self._ev if x[0] == "write"), None) or f
        session = wev.get("session") or self.session
        model = wev.get("model") or self._model(session, models)
        for c in cps:
            if c.get("model") == model:
                del c["model"]
        rec = self._head(t, session, model, srv)
        if wev.get("tool") and "tool" not in rec:
            rec["tool"] = wev["tool"]
        path = (writes[0]["path"] if writes else None) or (cps[0].get("orig") if cps else None)
        rec.update(op=self.file_op or ("save" if writes else "checkpoint"),
                   target={"path": path} if path else None,
                   status="failed" if writes and not any(w["ok"] for w in writes) else "changed")
        if self.item is not None:
            rec["item"] = self.item
        if writes:
            rec["writes"] = writes
            err = next((w["error"] for w in writes if w.get("error")), None)
            if err:
                rec["result"] = err
        if cps:
            rec["checkpoints"] = cps
        rec.update(self.file_extra)
        return {k: v for k, v in journal.clean(rec).items() if v is not None}


class Aggregate(Scope):
    """A loop or an optimization: writes are counted, not recorded one by one. Each path is
    read once before its first write and once at the end; leaving the ``with`` makes one
    record (``op``, default ``summary``): ``writes`` {path: {before, after, n, min, max,
    status, failed}}, ``n`` (all writes), ``range`` (of the first path), ``runs``
    (``add(op="run", status=)``), ``saves`` and ``report`` (set ``.report``). Set ``.status``
    to say how the whole thing ended (failed, error) over what the writes measured; with a
    report or a status the record is made even when nothing was written. Fields left None
    come from the enclosing scope, and its ``extra`` too; an Aggregate inside another joins
    it (``with`` then gives the outer one).

    Entering it writes a ``begin`` record at once (its own append: a server that dies in the
    middle leaves the timeline "started, no end recorded"), with ``.begin``'s fields (what the
    opener knows up front: the arguments; None: no begin record, for a short one); the
    summary, with the same ``call``, ends it -- or an ``end`` record when there is nothing to
    summarize."""

    def __init__(self, do, actor=None, via=None, session=None, model=None, group=None, call=None,
                 tool=None, target=None, reason=None, op="summary", **extra):
        super().__init__(actor, via, session, model, group, call, tool, reason, **extra)
        self.do, self.target, self.report, self.op, self.status = do, target, None, op, None
        self.runs: dict = {}
        self.ops: dict = {}
        self.saves = {"n": 0, "ok": 0, "files": []}
        self.begin: dict = {}          # more fields for the begin record
        self._p: dict = {}             # (session, path, attr or None) -> {"before", "n", ...}
        self._parent = None
        self._begun = False

    def __enter__(self):
        self._t0 = _perf()
        if self.on:
            cur = _CUR.get()
            if isinstance(cur, Aggregate) and cur.on:
                self._join = cur
                return cur
            if cur is not None and getattr(cur, "on", False):
                cur.settle()
                self._parent = cur
                for k in ("actor", "via", "session", "model", "group", "call", "tool"):
                    if getattr(self, k) is None:
                        setattr(self, k, getattr(cur, k))
                self.extra = {**cur.extra, **self.extra}
                self.manager = self.manager or cur.manager
            if self.call is None:
                self.call = journal.new_id("c")
            self._tok = _CUR.set(self)
            self._mark("begin")
        return self

    def __exit__(self, et, ev, tb):
        if self._tok is not None:
            _CUR.reset(self._tok)
            self._tok = None
            try:
                self._finish((_perf() - self._t0) * 1e3)
            except Exception as exc:
                logger.warning("recorder: %s summary lost (%r)", self.do, exc)
        return False

    def _mark(self, kind, **fields) -> None:
        """The ``begin`` record (entering) or an ``end`` one (nothing to summarize), appended
        at once. Never raises."""
        if (kind == "end" and not self._begun) or (kind == "begin" and self.begin is None):
            return
        t = _perf()
        try:
            model = self._model(self.session, {})
            if not model:
                return
            f = {"model": model, "session": self.session, "actor": self.actor, "via": self.via,
                 "group": self.group, "call": self.call, "tool": self.tool, "do": self.do, **self.extra}
            if kind == "begin":
                f["target"] = self.target if isinstance(self.target, dict) else \
                    journal.label(self.target) if self.target else None
                if self.reason is not None and str(self.reason).strip():
                    f["reason"] = self.reason
                f.update(self.begin)
            self._append([journal.entry(kind, **f, **fields)])
            self._begun = self._begun or kind == "begin"
        except Exception as exc:
            logger.warning("recorder: %s record of %s lost (%r)", kind, self.do, exc)
        finally:
            self.jt += _perf() - t

    # -- hooks: count, read each path once before
    def _entry(self, key):
        e = self._p.get(key)
        if e is None:
            e = self._p[key] = {"before": None, "n": 0, "min": None, "max": None, "failed": 0}
        return e

    def before(self, session, path, node, unit=None, basis=None):
        key = (session, path, None)
        if key not in self._p:
            t = _perf()
            try:
                self._entry(key)["before"] = read_state(node)
            except Exception:
                pass
            self.jt += _perf() - t
        return None

    def attr_before(self, session, path, node, n):
        key = (session, path, n)
        if key not in self._p:
            self._entry(key)["before"] = Scope.attr_before(self, session, path, node, n)
        return None

    def _count(self, key, value, res, how):
        e = self._entry(key)
        e["n"] += 1
        v = _num(value)
        if v is not None:
            e["min"] = v if e["min"] is None else min(e["min"], v)
            e["max"] = v if e["max"] is None else max(e["max"], v)
        if how != "written":
            e["failed"] += 1
            e["error"] = _cut(res, journal.RESULT_MAX)

    def value(self, manager, session, path, node, before, req, res, how) -> None:
        try:
            self.manager = self.manager or manager
            self._count((session, path, None), req[0], res, how)
        except Exception as exc:
            logger.warning("recorder: write of %s not counted (%r)", path, exc)

    def attr(self, manager, session, path, node, n, attribute, value, before, after, res, how) -> None:
        try:
            self.manager = self.manager or manager
            self._count((session, path, n), value, res, how)
        except Exception as exc:
            logger.warning("recorder: attribute write of %s not counted (%r)", path, exc)

    def event(self, kind, fields) -> None:
        if self._join is not None:
            return self._join.event(kind, fields)
        if kind == "write":
            self.saves["n"] += 1
            self.saves["ok"] += bool(fields.get("ok"))
            if fields.get("path") and fields["path"] not in self.saves["files"] and len(self.saves["files"]) < 5:
                self.saves["files"].append(fields["path"])

    def add(self, op, **fields) -> None:
        """Inside a loop a record is only counted: ``run`` / ``reinit`` by status in ``runs``,
        anything else in ``ops``."""
        if self._join is not None:
            return self._join.add(op, **fields)
        if not self.on:
            return None
        if op in journal.RUN_OPS:
            st = str(fields.get("status") or "unknown")
            self.runs["n"] = self.runs.get("n", 0) + 1
            self.runs[st] = self.runs.get(st, 0) + 1
        else:
            self.ops[op] = self.ops.get(op, 0) + 1
        return None

    def flush(self, ms=None, **last) -> list[dict]:
        return []                      # an Aggregate writes once, when it ends

    # -- the summary
    def _finish(self, ms) -> None:
        t = _perf()
        writes, n, first, changed, failed = {}, 0, None, False, 0
        apps = {}
        for (session, path, attr), e in self._p.items():
            after = None
            try:
                if session not in apps:
                    apps[session] = self.manager.get_app(session) if self.manager is not None else None
                app = apps[session]      # the session's app now: it may have been reopened meanwhile
                node = app.Tree.FindNode(path) if app is not None else None
                if node is not None:
                    after = read_state(node) if attr is None else {"value": dispid.get(node, "AttributeValue", attr)}
            except Exception:
                pass
            st = _status(e["before"], after, "written" if e["n"] > e["failed"] else "refused")
            w = {"before": _json(e["before"]), "after": _json(after), "n": e["n"], "status": st}
            for k in ("min", "max", "error"):
                if e.get(k) is not None:
                    w[k] = e[k]
            if e["failed"]:
                w["failed"] = e["failed"]
            if session != self.session:
                w["session"] = session
            key = path if attr is None else f"{path}#{attr}"
            writes[key] = w
            n += e["n"]
            failed += e["failed"]
            changed |= st == "changed"
            first = first or (key, w)
        if not (writes or self.runs or self.ops or self.saves["n"]) and self.report is None and self.status is None:
            self._mark("end", status="unchanged")
            return
        rec = self._head(journal.now(), self.session, self._model(self.session, {}), journal.srv())
        target = self.target if isinstance(self.target, dict) else \
            journal.label(self.target) if self.target else journal.label(first[0]) if first else None
        rec.update(op=self.op, do=self.do, target=target, n=n, status=self.status or (
            "changed" if changed else ("failed" if n and failed == n else "unchanged")))
        if first and first[1].get("min") is not None:
            rec["range"] = [first[1]["min"], first[1]["max"]]
        if writes:
            rec["writes"] = writes
        for k, v in (("runs", self.runs), ("ops", self.ops), ("saves", self.saves if self.saves["n"] else None),
                     ("report", self.report)):
            if v:
                rec[k] = v
        if self.reason is not None and str(self.reason).strip() and self._parent is None:
            rec["reason"] = _cut(self.reason, journal.REASON_MAX)
        rec = {k: v for k, v in journal.clean(rec).items() if v is not None}
        parent = self._parent
        if parent is not None and parent.on:
            parent._pend.append(_Built(rec))      # written with the enclosing call's records,
            parent.jt += self.jt + _perf() - t    # whose ms / jms cover this
        else:
            rec["ms"] = round(ms, 1)
            rec["jms"] = round((self.jt + _perf() - t) * 1e3, 2)
            self._append([rec])
        self.n += 1


class _Built(dict):
    """A finished record queued in an enclosing scope (its id and time are kept)."""


def scope(actor=None, via=None, session=None, model=None, group=None, call=None, tool=None,
          reason=None, **extra) -> Scope:
    """A recording scope; use as ``with recorder.scope(...) as s:``. Inert (no reads, no
    records) when ASPEN_MCP_JOURNAL=0."""
    return Scope(actor, via, session, model, group, call, tool, reason, **extra)
