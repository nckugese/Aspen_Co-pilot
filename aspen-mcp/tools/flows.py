"""Component flows read for the flowsheet: the flow width layer's -- one component,
or every component, in every stream -- and one stream's composition (the inspector, the hover card).

    fl = flows.Flows()
    fl.ask(session, tab, on, comp)        # the window's ``flows {tab, on, comp}``: True when the layer's data changed
    fl.ask_stream(session, stream)        # the window's ``stream_comp {tab, stream}``: one stream's composition
    fl.drop_tab(tab) / fl.clear()         # a tab closed / the window closed: their requests end
    fl.ran(session)                       # the session's results were read again: read them once more
    fl.tick(manager, sessions, block)     # the sync loop's pass: a chunk of reads where the session is idle

The window's Total flow needs nothing here: it is the stream values' ``f`` (no read). The layer's
component (``comp``, or ALL: every component of the model) is read into the session's ``flows``:

    {"comp", "basis": "mass" | "mole", "unit", "at", "run_seq", "partial", "reading", "busy",
     "v": {stream: number | None}}                       # one component
     "comps": [component, ...], "v": {stream: [number | None, ...] | None}   # ALL: in the order of comps

One path a stream and component: ``Output\\MASSFLOW\\MIXED\\{comp}``; a model whose streams have no mass
flows reads ``MOLEFLOW`` instead (basis mole). ``v`` None: the stream has no such result (a heat or work
stream, no results yet) -- for ALL, a stream whose first component has none is not looked up further.
``partial``: some streams could not be read (an error) or the model has more than STREAMS_MAX (ALL:
more than LOOKS_MAX lookups). One request a session -- the latest tab's component; it ends with the
last tab asking.

A stream's composition (``ask_stream``) is both bases, every component, into the session's
``stream_comp``, at most KEEP streams (the latest asked):

    {"s": {stream: {"comps": [...], "mass": [number | None, ...] | None, "mole": [...] | None,
                    "mu": unit, "nu": unit, "reading", "stale", "partial", "run_seq"}}, "busy"}

``mass`` / ``mole`` None: the stream has no such results. A run marks every stream kept ``stale`` (its
values stay); the window asks again for the one it shows. A stream asked is read before the layer's.

The reads are low priority and stay off the run path: none while the session is held (a program, the
AI's optimize) or Aspen computes for a call -- ``busy`` says so --, none while any tool call is in
flight and until QUIET_S after the last one ended (the AI's next call goes first), and at most CHUNK
lookups a pass (CHUNK_VISIBLE on a session Aspen shows), stopping once a pass has spent
runlog.BUDGET_MS -- a run's own after-read budget. A later run reads the layer again (``ran``): the
values read before stay until the new ones are in (``reading``), then change at once. Stdlib only;
COM only through the manager's apps; nothing raises into the sync loop.
"""
from __future__ import annotations

import logging
import math
import time

from tools import dispid, nodes, runlog

logger = logging.getLogger(__name__)

_perf = time.perf_counter
CHUNK = 50                # paths one idle pass looks up at most (a hidden session)
CHUNK_VISIBLE = 15        # ... a session Aspen shows (each read costs several times as much)
QUIET_S = 1.0             # no reads until this long after the last tool call ended
STREAMS_MAX = 500         # streams one request reads; more: partial
LOOKS_MAX = 6000          # lookups one ALL request makes at most (streams x components); more: partial
KEEP = 8                  # streams whose composition a session keeps
ALL = "*"                 # the layer's request for every component
_BASIS = (("mass", "MASSFLOW"), ("mole", "MOLEFLOW"))
_NONE = object()          # (a lookup that found no node)


def _path(stream: str, field: str, comp: str) -> str:
    return rf"\Data\Streams\{stream}\Output\{field}\MIXED\{comp}"


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    return None


def _short(v):
    """A value kept to 6 significant digits (state.json carries every stream x component)."""
    return float(f"{v:.6g}") if isinstance(v, float) else v


class Flows:
    """The sessions' flow requests and their reads (one Flows a workspace)."""

    def __init__(self):
        self._r: dict = {}        # session -> {"comp", "tabs": set, "todo": list | None, "got", "basis", "unit", "err", "cut"}
        self._c: dict = {}        # session -> {"todo": [(stream, field, i)], "s": {stream: entry}, "dirty", "busy"}

    # -- requests ----------------------------------------------------------------------
    def ask(self, session: str, tab: str, on: bool, comp, comps=None) -> bool:
        """The window's flows event. ``on`` with a component the model has (``comps``: the
        flowsheet's, None: not checked), or ALL, starts reading it for the session, replacing
        another component asked before; off from a tab ends that tab's request (the session's once
        no tab asks). Returns whether the session's ``flows`` must change."""
        r = self._r.get(session)
        if on and (not isinstance(comp, str) or not comp or (comp != ALL and comps is not None and comp not in comps)):
            return False                           # (not a component of the model: nothing changes)
        if not on:
            if r is None or tab not in r["tabs"]:
                return False
            r["tabs"].discard(tab)
            if r["tabs"]:
                return False
            del self._r[session]
            return True
        if r is not None and r["comp"] == comp:
            r["tabs"].add(tab)
            return False
        self._r[session] = {"comp": comp, "tabs": {tab}, "todo": None, "got": {}, "basis": None, "unit": None,
                            "err": 0, "cut": False}
        return True

    def ask_stream(self, session: str, stream, streams=None) -> bool:
        """The window's stream_comp event: ``stream``'s composition read (again where it is stale or
        not kept), ahead of what else is asked. ``streams``: the flowsheet's names (None: not
        checked). Returns whether a read was queued."""
        if not isinstance(stream, str) or not stream or (streams is not None and stream not in streams):
            return False
        c = self._c.setdefault(session, {"todo": [], "s": {}, "dirty": False, "busy": False})
        e = c["s"].get(stream)
        if e is not None and (e["reading"] or not e["stale"]):
            c["s"][stream] = c["s"].pop(stream)    # (the latest asked: kept longest)
            return False
        c["todo"] = [x for x in c["todo"] if x[0] != stream]
        c["s"].pop(stream, None)
        c["s"][stream] = dict(e or {"comps": None, "mass": None, "mole": None, "mu": None, "nu": None,
                                    "partial": False, "run_seq": None}, reading=True, stale=bool(e), new=True)
        while len(c["s"]) > KEEP:                  # (the oldest go, their reads with them)
            old = next(iter(c["s"]))
            del c["s"][old]
            c["todo"] = [x for x in c["todo"] if x[0] != old]
        c["dirty"] = True
        return True

    def drop_tab(self, tab: str) -> list:
        """A tab closed: its requests end. Returns the sessions whose request ended."""
        gone = []
        for s, r in list(self._r.items()):
            r["tabs"].discard(tab)
            if not r["tabs"]:
                del self._r[s]
                gone.append(s)
        return gone

    def clear(self) -> list:
        """The window closed: every request ends. Returns the sessions that had one."""
        gone = list(self._r)
        self._r.clear()
        self._c.clear()
        return gone

    def asked(self, session: str):
        """The component asked for on ``session``, or None."""
        r = self._r.get(session)
        return r["comp"] if r else None

    def ran(self, session: str) -> None:
        """The session's results were read again (a run, a refresh): read the layer's every stream once
        more; the compositions kept are stale (the window asks for the one it shows)."""
        r = self._r.get(session)
        if r is not None:
            r.update(todo=None, got={}, err=0, cut=False, unit=None)   # (the unit as the model now shows it)
        c = self._c.get(session)
        if c is not None and c["s"]:
            for k, e in c["s"].items():
                e["stale"] = True
                if e["reading"]:                   # (half read before the run: from the start again)
                    e["new"] = True
                    c["todo"] = [x for x in c["todo"] if x[0] != k]
            c["dirty"] = True

    # -- the reads ---------------------------------------------------------------------
    def tick(self, manager, sessions: dict, block) -> bool:
        """The sync loop's pass. ``sessions``: state.json's; ``block(session)`` None when the
        session is free to read, "busy" while Aspen works on it, "call" while a tool call is in
        flight or just ended. Writes each asked session's ``flows`` and ``stream_comp`` (and None where
        a request ended). Returns whether one changed."""
        changed = False
        for name, sess in sessions.items():
            if isinstance(sess, dict) and sess.get("flows") is not None and name not in self._r:
                sess["flows"] = None
                changed = True
            if isinstance(sess, dict) and sess.get("stream_comp") is not None and name not in self._c:
                sess["stream_comp"] = None
                changed = True
        for name in set(self._r) | set(self._c):
            sess = sessions.get(name)
            if not isinstance(sess, dict):
                continue
            pass_ = {"looks": 0, "end": None, "n": None, "app": None, "why": False}
            try:
                if name in self._c:
                    changed |= self._streams(manager, name, sess, self._c[name], block, pass_)
                if name in self._r:
                    changed |= self._one(manager, name, sess, self._r[name], block, pass_)
            except Exception:
                logger.warning("flows: the reads on %s failed", name, exc_info=True)
        return changed

    def _free(self, manager, name: str, block, p: dict):
        """This pass's app on ``name`` and how many lookups it may make, once: (app, None) when it may
        read, (None, why) when not ("busy", "call", or None: no app)."""
        if p["why"] is False:
            why = block(name)
            app = manager.get_app(name) if why is None else None
            if why is None and app is not None:
                try:
                    p["n"] = CHUNK_VISIBLE if manager.visible(name) else CHUNK
                except Exception:
                    p["n"] = CHUNK
                p["end"] = _perf() + runlog.BUDGET_MS / 1e3
            p["app"], p["why"] = app, why
        return p["app"], p["why"]

    def _room(self, p: dict) -> bool:
        return p["looks"] < p["n"] and _perf() < p["end"]

    def _one(self, manager, name: str, sess: dict, r: dict, block, p: dict) -> bool:
        view = sess.get("flows") if isinstance(sess.get("flows"), dict) else None
        if view is not None and view.get("comp") != r["comp"]:
            view = None
        if r["todo"] is None:                      # a new request, or a run since: every stream again
            streams = [s.get("name") for s in ((sess.get("flowsheet") or {}).get("streams") or [])
                       if isinstance(s, dict) and isinstance(s.get("name"), str)]
            if r["comp"] == ALL:
                comps = [c for c in ((sess.get("flowsheet") or {}).get("components") or []) if isinstance(c, str) and c]
                most = max(1, LOOKS_MAX // max(1, len(comps)))
                r.update(comps=comps, skip=set(), cut=len(streams) > min(most, STREAMS_MAX),
                         todo=[(s, i) for s in streams[:min(most, STREAMS_MAX)] for i in range(len(comps))] if comps else [],
                         got={s: [None] * len(comps) for s in streams[:min(most, STREAMS_MAX)]} if comps else {}, err=0)
            else:
                r.update(todo=streams[:STREAMS_MAX], got={}, err=0, cut=len(streams) > STREAMS_MAX)
            if not r["todo"]:                      # (no stream to read: done at once, not reading for ever)
                return self._done(sess, r)
            sess["flows"] = dict(view or {"comp": r["comp"], "v": {}}, reading=True, busy=False)
            return True
        if not r["todo"]:
            return False
        app, why = self._free(manager, name, block, p)
        if app is None:
            if why is None:
                return False
            busy = why == "busy"
            if view is not None and bool(view.get("busy")) != busy:
                sess["flows"] = dict(view, busy=busy)
                return True
            return False
        while r["todo"] and self._room(p):
            item = r["todo"].pop(0)
            s, i = item if isinstance(item, tuple) else (item, None)
            comp = r["comp"] if i is None else r["comps"][i]
            if i is not None and s in r["skip"]:
                continue
            try:
                v = self._read(name, app, s, comp, r, p)
            except Exception as exc:
                logger.debug("flows: %s of %s not read (%r)", comp, s, exc)
                v = None
                r["err"] += 1
            if i is None:
                r["got"][s] = None if v is _NONE else v
            elif v is _NONE:
                if i == 0:                         # (no such result on its first component: none on the rest)
                    r["skip"].add(s)
            else:
                r["got"][s][i] = v
        if r["todo"]:
            if view is not None and view.get("busy"):
                sess["flows"] = dict(view, busy=False)
                return True
            return False
        return self._done(sess, r)

    @staticmethod
    def _done(sess: dict, r: dict) -> bool:
        """Every stream read: the session's flows in one write."""
        s = (sess.get("journal") or {}) if isinstance(sess.get("journal"), dict) else {}
        run = s.get("run") if isinstance(s.get("run"), dict) else {}
        out = {"comp": r["comp"], "basis": r["basis"] or "mass", "unit": r["unit"],
               "at": round(time.time(), 3), "run_seq": run.get("seq"), "partial": bool(r["err"] or r["cut"]),
               "reading": False, "busy": False}
        if r["comp"] == ALL:
            skip = r.get("skip") or set()
            out["comps"] = list(r.get("comps") or [])
            out["v"] = {k: None if k in skip or all(x is None for x in v) else [_short(x) for x in v]
                        for k, v in r["got"].items()}
        else:
            out["v"] = dict(r["got"])
        sess["flows"] = out
        return True

    def _read(self, session: str, app, stream: str, comp: str, r: dict, p: dict):
        """One stream's flow of a component (the basis found on the first stream that has either:
        until then a stream costs two lookups), None (no value), or _NONE (no such node)."""
        fields = [f for b, f in _BASIS if b == r["basis"]] if r["basis"] else [f for _, f in _BASIS]
        for field in fields:
            p["looks"] += 1
            node = nodes.find(session, app, _path(stream, field, comp))
            if node is None:
                continue
            if r["basis"] is None:
                r["basis"] = next(b for b, f in _BASIS if f == field)
            v = _num(dispid.get(node, "Value"))
            if v is not None and r["unit"] is None:
                r["unit"] = dispid.get(node, "UnitString") or None
            return v
        return _NONE

    # -- one stream's composition --------------------------------------------------------
    def _streams(self, manager, name: str, sess: dict, c: dict, block, p: dict) -> bool:
        changed = False
        comps = [x for x in ((sess.get("flowsheet") or {}).get("components") or []) if isinstance(x, str) and x]
        for s, e in c["s"].items():                # (a stream newly asked: its reads queued)
            if e.pop("new", False):
                e.update(comps=comps, _m=[None] * len(comps), _n=[None] * len(comps), _skip=set(), _err=0,
                         _mu=None, _nu=None)
                c["todo"] = [(s, f, i) for i in range(len(comps)) for _, f in _BASIS] + c["todo"]
                if not comps:
                    self._stream_done(sess, e)
        if not c["todo"] and c["busy"]:
            c["busy"], c["dirty"] = False, True
        if c["todo"]:
            app, why = self._free(manager, name, block, p)
            busy = why == "busy"
            if busy != c["busy"]:
                c["busy"], c["dirty"] = busy, True
            while app is not None and c["todo"] and self._room(p):
                s, field, i = c["todo"].pop(0)
                e = c["s"].get(s)
                if e is None:
                    continue
                if field not in e["_skip"]:
                    p["looks"] += 1
                    try:
                        self._look(name, app, s, field, i, e)
                    except Exception as exc:
                        logger.debug("flows: %s of %s not read (%r)", e["comps"][i], s, exc)
                        e["_err"] += 1
                if not any(x[0] == s for x in c["todo"]):
                    self._stream_done(sess, e)
                    c["dirty"] = True
        if c["dirty"]:
            sess["stream_comp"] = {"busy": c["busy"],
                                   "s": {k: {x: v for x, v in e.items() if not x.startswith("_")} for k, e in c["s"].items()}}
            c["dirty"] = False
            changed = True
        return changed

    @staticmethod
    def _look(session: str, app, stream: str, field: str, i: int, e: dict) -> None:
        """One component's flow of a stream in one basis into its entry ``e``."""
        node = nodes.find(session, app, _path(stream, field, e["comps"][i]))
        if node is None:
            if i == 0:                             # (no such result on the first component: none on the rest)
                e["_skip"].add(field)
            return
        v = _num(dispid.get(node, "Value"))
        e["_m" if field == "MASSFLOW" else "_n"][i] = v
        u = "_mu" if field == "MASSFLOW" else "_nu"
        if v is not None and e[u] is None:
            e[u] = dispid.get(node, "UnitString") or None

    @staticmethod
    def _stream_done(sess: dict, e: dict) -> None:
        """A stream's every lookup made: its lists (None for a basis it has no results in)."""
        j = (sess.get("journal") or {}) if isinstance(sess.get("journal"), dict) else {}
        run = j.get("run") if isinstance(j.get("run"), dict) else {}
        side = lambda k, f: None if f in e.get("_skip", ()) or all(x is None for x in e.get(k) or []) \
            else [_short(x) for x in e[k]]          # noqa: E731
        e.update(mass=side("_m", "MASSFLOW"), mole=side("_n", "MOLEFLOW"), mu=e.get("_mu"), nu=e.get("_nu"),
                 partial=bool(e.get("_err")), reading=False, stale=False, run_seq=run.get("seq"))


def quiet(snapshot: dict, now: float) -> bool:
    """No tool call in flight, and none ended within QUIET_S (activity.snapshot())."""
    if snapshot.get("act"):
        return False
    last = snapshot.get("last") or {}
    end = last.get("end")
    return not isinstance(end, (int, float)) or now - end >= QUIET_S
