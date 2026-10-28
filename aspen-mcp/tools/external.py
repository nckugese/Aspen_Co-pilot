"""Changes made in Aspen's own window: found by comparing, recorded with actor ``external``.

    external.configure(paths_of=fn)             # server.py, once: listen to the journal, start FOCUS
    external.pre_call(manager, tool, args)      # before an AI tool call (intercept's hooks.external)
    external.idle_check(manager, sessions)      # the workbench's sync loop, every tick (Workspace.watch)
    external.check(manager, session, why=...)   # one gated compare: the window's jobs, a program's start
    WATCH.seen(session, path, value, unit, model)   # the AI read an input (manager.get_node_value)
    WATCH.base(manager, session, paths)         # a session's first read (paths_of: workbench watch_paths)
    d = Deep(manager, session, {"kind", "name"})    # the workbench's ext_deep: d.step() until True, d.result
    deep(manager, session, obj)                 # the same in one go: the result
    checked(session)                            # when the session was last compared (model_status)

Nobody edits the model in Aspen's window without that window in front. ``Focus`` -- a daemon
thread, ctypes only, never COM -- notes every TICK_S which process owns the foreground window,
and a session is compared only when its AspenPlus.exe (the pid the manager read at open; any
Aspen when unknown) was in front since the session's last compare, at most once a GAP_S while it
stays there. GetForegroundWindow NULL for NULL_TICKS in a row (a server outside the active
console session gets NULL for ever) means "unknown", never "not in front": then at most once a
FALLBACK_S. A hidden session (opened visible=False) is never compared, nor one a program or an
optimizer holds (tools/activity.py): their own records say what they wrote. A shut gate costs
no COM.

A compare (``Watch.check``) reads by path (tools/nodes.py, ~0.4 ms a value on V15; no node is
kept) within BUDGET_MS:
1. topology -- the names under Blocks, Streams and the component list against those last seen
   (every folder counted, one folder's names read in turn, and any whose count changed): an
   ``add`` / ``remove`` record each (a rename is both; a removed object's known values go).
   Only connections changed: not seen here.
2. an external run -- a dozen results spread over the flowsheet (runlog.peek) moved and the
   journal has no run since they were read: a ``run`` record with the run log's seq / inputs / delta
   (runlog.since_last). A rerun that changes nothing is not seen (and changed nothing).
3. the file -- its mtime moved and no save / patch / open record explains it: a ``save`` record
   (the unsaved count starts again).
4. known values -- input paths whose value the server knows: each value / attr record's after
   and a loop's net writes (journal.listen), the AI's reads (``seen``), ``base`` -- at most
   KNOWN_MAX a session, the AI's reads first, then the longest unverified, as many as the budget
   allows -- all of them when 2 or 3 found something (so the edits come before the run's inputs
   and the save), and when the user has left Aspen's window since the last compare (in front
   at a tick since, not now: an edit made there is in this compare, not a later turn's, and no
   later compare would come until the next visit -- measured, once a visit: 139 known values
   ~130 ms, 282 ~250 ms). A difference is a ``value`` (``attr``) record; the new value
   becomes known.
Measured on V15 (23 blocks, 46 streams, 179 known values): a compare that finds nothing ~25 ms
(max ~50); one that finds a value, an add or a remove ~26-40 ms; a run ~340 ms and a save
~160 ms (every known value read, and the run log's after-read); a shut gate ~3 us.
Records: actor external, via aspen, ``detect`` (topology | results | file | watch | deep),
``since`` (when the old state was last known -- the change happened after it), ``known``
(journal | read | base | deep: where that state came from), ``why`` (what asked); in
``journal.GROUPS.external``'s group; one append per compare (two when a run is found: the edits
first). Only reported, never paused. What Aspen changes by itself after a
write or a run is not re-read (nothing on V15). ``ASPEN_MCP_EXTERNAL=0``, or the journal
off: none of it.

The deep compare (``Deep``) is for the fields no one watches: only when the user asks
(the inspector's button: the workbench's ``ext_deep`` job), never on its own. It reads every
node under one block's or stream's Input (knowledge_tools' walk; value and unit by DISPID; at
most DEEP_MAX nodes / DEEP_S of reading, then ``partial``) in turns of DEEP_TURN_MS, so its
caller can let the event loop run between them. The first press only notes what is there -- a
baseline, journal/<model>/deep/<kind>-<name>.json.gz -- and says so; a later one records what
differs from it that the journal does not explain (a value / summary / restore record since the
baseline whose after is the value now, or is on a node below it with that value: the parent's
echo of a write) as ``value`` records, detect deep, then notes the new state. A baseline
older than the model's last ``open`` record, or than an add / remove of the object itself, is
not used: a new one is noted. No background baselines: a whole model took ~15.6 s on V15,
far too long to run unasked.
Stdlib only; no I/O or COM at import; COM only on the caller's thread.
"""
from __future__ import annotations

import ctypes
import gzip
import itertools
import json
import logging
import math
import os
import re
import sys
import threading
import time
from collections import OrderedDict

from tools import activity, dispid, journal, knowledge_tools, nodes, probes, runlog

logger = logging.getLogger(__name__)

_perf = time.perf_counter
now = time.time                   # the gates' clock (the Focus thread's too); a module attribute, so it can be overridden
BUDGET_MS, VALUES_MIN_MS = 25.0, 5.0   # a compare's reads; known values get at least the second
GAP_S = 1.0                       # Aspen in front all along: compares at least this far apart
FALLBACK_S = 5.0                  # the foreground unknown: compares at least this far apart
IDLE_GAP_S, IDLE_FRONT_S = 2.0, 10.0   # idle_check: after Aspen left the front / while it stays
KNOWN_MAX, BASE_MAX = 400, 300    # known values a session keeps; base reads at most
TICK_S, NULL_TICKS = 0.5, 6       # Focus: a tick; NULL this many ticks in a row = unknown
RUN_EPS = 0.001                   # s: a record's time is rounded to the ms
SKIP_TOOLS = frozenset({"open_aspen_plus", "create_new_simulation", "set_reopen_interval", "record_error"})
FOLDERS = ((r"\Data\Blocks", "block"), (r"\Data\Streams", "stream"),
           (r"\Data\Components\Specifications\Input\TYPE", "component"))
DEEP_MAX, DEEP_S = 6000, 10.0     # a deep compare reads at most these nodes / seconds (then partial)
DEEP_TURN_MS = 20.0               # ... in turns this long, the caller's event loop running between them
DEEP_FILES = 200                  # deep baselines kept per model (the least recently written go)
_DEEP_ROOTS = {"block": "Blocks", "stream": "Streams"}
STATS = {"checks": 0, "skipped": 0, "read": 0, "found": 0, "deep": 0}
_ORDER = itertools.count(1)       # when a known value was last learned or read back, in order
_PATHS_OF = None                  # fn(manager, session) -> the paths base reads (the catalog's)


def enabled() -> bool:
    """``ASPEN_MCP_EXTERNAL`` not 0 / off / false / no, and the journal on (read every call)."""
    return os.environ.get("ASPEN_MCP_EXTERNAL", "1").strip().lower() not in ("0", "off", "false", "no") \
        and journal.enabled()


# ---------------------------------------------------------------------------- the foreground
class _Win32:
    """user32 / kernel32 through their own WinDLL objects (argtypes nobody else shares)."""

    def __init__(self):
        from ctypes import wintypes as w
        self.w, u, k = w, ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
        u.GetForegroundWindow.restype = w.HWND
        u.GetWindowThreadProcessId.argtypes = (w.HWND, ctypes.POINTER(w.DWORD))
        k.OpenProcess.restype = w.HANDLE
        k.OpenProcess.argtypes = (w.DWORD, w.BOOL, w.DWORD)
        k.QueryFullProcessImageNameW.argtypes = (w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD))
        k.CloseHandle.argtypes = (w.HANDLE,)
        self.u, self.k = u, k

    def fg(self):
        return self.u.GetForegroundWindow()

    def pid(self, hwnd) -> int:
        d = self.w.DWORD()
        self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(d))
        return d.value

    def image(self, pid) -> str:
        h = self.k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf, n = ctypes.create_unicode_buffer(1024), self.w.DWORD(1024)
            ok = self.k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
            return os.path.basename(buf.value).lower() if ok else ""
        finally:
            self.k.CloseHandle(h)


class Focus:
    """Who owns the foreground window, every TICK_S on a daemon thread. ``ok``: running and the
    foreground known; ``front(pid, since)``: that AspenPlus.exe (None: any) is in front now or
    was at a tick at or after ``since``; ``showing(pid)``: in front at the last tick;
    ``last(pid)``: when it last was."""

    def __init__(self, api=None):
        self.ok = False
        self._api, self._thread = api, None
        self._lock = threading.Lock()
        self._last: dict = {}                  # Aspen pid -> the last tick it was in front
        self._cur = None                       # the Aspen pid in front at the last tick
        self._nulls, self._said = 0, False
        self._aspen: OrderedDict = OrderedDict()   # pid -> is AspenPlus.exe (at most 64)

    def start(self) -> bool:
        with self._lock:
            if self._thread is None:
                self._thread = False
                try:
                    if self._api is None:
                        if sys.platform != "win32":
                            raise OSError("not Windows")
                        self._api = _Win32()
                    self._thread = threading.Thread(target=self._loop, name="aspen-mcp-focus", daemon=True)
                    self._thread.start()
                except Exception as exc:
                    logger.info("external: no foreground watch (%r): compares at most every %.0f s", exc, FALLBACK_S)
            return bool(self._thread)

    def _loop(self) -> None:
        while True:
            try:
                self.tick()
            except Exception as exc:
                self.ok = False
                logger.warning("external: the foreground watch stopped (%r)", exc)
                return
            time.sleep(TICK_S)

    def _is_aspen(self, pid) -> bool:
        hit = self._aspen.get(pid)
        if hit is None:
            hit = self._aspen[pid] = self._api.image(pid) == "aspenplus.exe"
            while len(self._aspen) > 64:
                self._aspen.popitem(last=False)
        return hit

    def tick(self) -> None:
        hwnd, t = self._api.fg(), now()
        if not hwnd:
            self._nulls += 1
            with self._lock:
                self._cur = None
                if self._nulls >= NULL_TICKS and (self.ok or not self._said):
                    self.ok, self._said = False, True
                    logger.info("external: the foreground window is unknown (NULL): compares at most every %.0f s",
                                FALLBACK_S)
            return
        self._nulls = 0
        pid = self._api.pid(hwnd)
        aspen = self._is_aspen(pid)
        with self._lock:
            self.ok = True
            self._cur = pid if aspen else None
            if aspen:
                self._last[pid] = t

    def last(self, pid=None):
        with self._lock:
            return self._last.get(pid) if pid is not None else max(self._last.values(), default=None)

    def showing(self, pid=None) -> bool:
        cur = self._cur
        return cur is not None and (pid is None or cur == pid)

    def front(self, pid=None, since=None) -> bool:
        t = self.last(pid)
        return self.showing(pid) or (t is not None and (since is None or t >= since))


FOCUS = Focus()


# ---------------------------------------------------------------------------- the watch
def _watchable(key) -> bool:
    """An input: a path with an Input segment and no Output one (results change with runs)."""
    segs = journal.split_key(key)[0].split("\\")
    return "Input" in segs and "Output" not in segs


def _plain(v):
    return None if v == "" else journal.clean(v)


def _same(a, b) -> bool:
    if a == b:
        return True
    try:
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) \
            and math.isclose(a, b, rel_tol=1e-12, abs_tol=0.0)
    except TypeError:
        return False


def _differs(known: dict, now_: dict) -> bool:
    return any(k in known and k in now_ and not _same(known[k], now_[k]) for k in ("value", "unit", "basis"))


def _read(session, app, key, known):
    """{"value", "unit"[, "basis"]} at ``key`` now (``path#n``: {"value": attribute n}); None
    when Aspen has no such node."""
    path, n = journal.split_key(key)             # ...\CID\#0: the table's row 0, a value
    node = nodes.find(session, app, path)
    if node is None:
        return None
    if n is not None:
        return {"value": _plain(dispid.get(node, "AttributeValue", n))}
    out = {"value": _plain(dispid.get(node, "Value")), "unit": _plain(dispid.get(node, "UnitString"))}
    if "basis" in known:
        out["basis"] = _plain(dispid.get(node, "AttributeValue", 13))
    return out


def _bare(r):
    return r if r is None or hasattr(r, "_oleobj_") else nodes.Node(r)


def _elements(node):
    """A folder's Elements by DISPID (a bare collection), else through win32com; None: no node."""
    if node is None:
        return None
    r = dispid.raw(node, "Elements")
    return node.Elements if r is dispid.LATE else _bare(r)


def _item(els, i):
    r = dispid.raw(els, "Item", i)
    return els.Item(i) if r is dispid.LATE else _bare(r)


def _mtime(f):
    try:
        return os.stat(f).st_mtime_ns if f else None
    except OSError:
        return None


def _pid(manager, session):
    p = (getattr(manager, "_pids", None) or {}).get(session)
    return p[0] if p else None


class _K:
    """A known value: ``state`` {"value", "unit"?, "basis"?}, known at ``t`` (the journal's
    clock) from ``src``, learned or last read back ``v``-th (_ORDER), ``seen``: the AI read it
    since."""
    __slots__ = ("state", "t", "src", "v", "seen")

    def __init__(self, state, t, src, v, seen=False):
        self.state, self.t, self.src, self.v, self.seen = state, t, src, v, seen


class _S:
    """A session's watch: its model, known values (LRU), inputs Aspen does not have, the
    topology {folder: {NAME: name}} and when read, the file and its mtime, the results
    baseline, the last compare (gates' clock)."""
    __slots__ = ("model", "known", "missing", "topo", "topo_t", "turn", "file", "mtime", "mtime_t", "res",
                 "checked", "busy", "based")

    def __init__(self, model):
        self.model, self.known, self.missing = model, OrderedDict(), set()
        self.topo, self.topo_t, self.turn = {}, None, 0
        self.file = self.mtime = self.mtime_t = self.res = None
        self.checked, self.busy, self.based = 0.0, False, False

    def put(self, key, state, t, src, seen=False) -> None:
        if not _watchable(key) or not isinstance(state, dict) or "value" not in state:
            return
        k = self.known.get(key)
        if k is not None and t < k.t - RUN_EPS:        # an older record reaching us late (t: ms)
            return
        new = dict(k.state) if k is not None else {}
        new.update((x, _plain(state[x])) for x in ("value", "unit", "basis") if x in state)
        self.known[key] = _K(new, t, src, next(_ORDER), seen)
        self.known.move_to_end(key)
        self.missing.discard(key)
        while len(self.known) > KNOWN_MAX:
            self.known.popitem(last=False)

    def drop(self, path) -> None:
        """Forget everything under ``path`` (an object removed)."""
        pre = str(path).upper() + "\\"
        for key in [x for x in self.known if x.upper().startswith(pre)]:
            del self.known[key]
        self.missing = {x for x in self.missing if not x.upper().startswith(pre)}

    def kin(self, path, wide=False) -> None:
        r"""Forget the values above ``path`` and their attributes, written just now: Aspen echoes
        a write into the parent, which is not a change made in its window. ``wide`` (a unit
        or basis written): the siblings too -- a component flow's unit and basis are its
        FLOW\MIXED's (on V15: DEXTROSE to kg/hr with MASS-FLOW moves CO2, WATER and the parent)."""
        parts = str(path).split("\\")
        ups = {"\\".join(parts[:i]).upper() for i in range(2, len(parts))}
        own, pre = str(path).upper(), "\\".join(parts[:-1]).upper() + "\\"
        for key in [k for k in self.known if (p := journal.split_key(k)[0].upper()) in ups
                    or (wide and p.startswith(pre) and p != own)]:
            del self.known[key]


class Watch:
    """The sessions' known state, in memory only (a restart starts from ``base`` again)."""

    def __init__(self):
        self._lock = threading.RLock()
        self._s: dict = {}                              # session -> _S

    def state(self, session, model, create=True):
        with self._lock:
            st = self._s.get(session)
            if (st is None or st.model != model) and create and model:
                st = self._s[session] = _S(model)
            return st if st is not None and st.model == model else None

    # -- what the server knows
    def learn(self, model, recs) -> None:
        """journal.listen: a value / attr record's after (a write that failed: its before), a
        loop's or restore's net writes, adds and removes (the topology), an open or a restore to
        a restore point (the session starts over), a close, a save / patch (the file's mtime is
        the server's)."""
        if not enabled():
            return
        with self._lock:
            for r in recs or ():
                if r.get("kind") == "change":
                    try:
                        self._learn(model, r)
                    except Exception as exc:
                        logger.debug("external: record %s not learned (%r)", r.get("id"), exc)

    def _learn(self, model, r) -> None:
        op, session = r.get("op"), r.get("session")
        t = r.get("t") if isinstance(r.get("t"), (int, float)) else journal.now()
        if op == "restore" and isinstance(r.get("target"), dict) and r["target"].get("checkpoint"):
            op = "open"                      # the model put back to a restore point, reopened
        if op in ("open", "close"):
            if session and (op == "open" or (self._s.get(session) and self._s[session].model == model)):
                self._s.pop(session, None)
            return
        sts = [st for s, st in self._s.items() if st.model == model and (not session or s == session)]
        if not sts and session and op in ("value", "attr", "summary", "restore"):
            sts = [self.state(session, model)]
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        for st in sts:
            if op in ("value", "attr") and tg.get("path"):
                key = tg["path"] if op == "value" else f"{tg['path']}#{tg.get('attr', r.get('attr'))}"
                state = r.get("before") if r.get("status") in ("failed", "refused", "error") else r.get("after")
                b, a = r.get("before") or {}, r.get("after") or {}
                if op == "value":                # Aspen echoes a write in the parent (TEMP <- TEMP\MIXED)
                    st.kin(key, wide=isinstance(a, dict) and isinstance(b, dict)
                           and any(b.get(x) != a.get(x) for x in ("unit", "basis") if x in a))
                elif r.get("status") == "changed":
                    st.drop(tg["path"])          # an attribute (a basis) moves the units below it
                if isinstance(state, dict) and "value" in state:
                    st.put(key, state, t, "journal")
                else:
                    st.known.pop(key, None)      # written, but not read back: no longer known
            elif op in ("summary", "restore"):
                for p, w in (r.get("writes") or {}).items():
                    if isinstance(w, dict) and not w.get("session"):
                        st.put(str(p), w.get("after"), t, "journal")
            elif op in ("add", "remove") and tg.get("path") and r.get("status") == "changed":
                folder, _, name = tg["path"].rpartition("\\")
                names = st.topo.get(folder)
                if op == "remove":
                    st.drop(tg["path"])
                if names is not None:
                    if op == "add":
                        names[name.upper()] = name
                    else:
                        names.pop(name.upper(), None)
            elif op in ("save", "patch") and st.file:
                st.mtime, st.mtime_t = _mtime(st.file), t

    def seen(self, session, path, value, unit=None, model=None) -> None:
        """The AI read an input at ``path`` (``model``: the session's): compared first next time."""
        if enabled() and session and _watchable(path):
            with self._lock:
                st = self.state(session, model) if model else self._s.get(session)
                if st is not None:
                    state = {"value": value} if unit is None else {"value": value, "unit": unit}
                    st.put(path, state, journal.now(), "read", seen=True)

    def forget(self, session=None) -> None:
        with self._lock:
            self._s.clear() if session is None else self._s.pop(session, None)

    # -- reading Aspen
    def base(self, manager, session, paths=None, force=False) -> int:
        """A session's first read (the default paths once; ``paths`` given: those not known yet):
        the topology, the file's mtime and the values of ``paths`` (configure's ``paths_of``
        when None; inputs only, at most BASE_MAX; a path Aspen lacks is not looked up again) as
        they are now -- what later compares look for changes against. No gate, no record.
        Returns the values read."""
        if not enabled() or not session:
            return 0
        model = manager.model_id(session)
        with self._lock:
            st = self.state(session, model)
            if st is None or st.busy or (st.based and paths is None and not force):
                return 0
            st.busy = True
        try:
            app = manager.get_app(session)
            if app is None:
                return 0
            if paths is None and _PATHS_OF is not None:
                paths = _PATHS_OF(manager, session)
            if st.topo_t is None:
                self._topology(session, app, st)
            self._file(manager, session, st)
            t, n = journal.now(), 0
            for p in [p for p in paths or () if _watchable(p)][:BASE_MAX]:
                if p in st.known or p in st.missing:
                    continue
                state = _read(session, app, p, {})
                with self._lock:
                    if state is None:
                        st.missing.add(p)
                    elif p not in st.known:
                        st.put(p, state, t, "base")
                n += state is not None
            st.based = True
            STATS["read"] += n
            return n
        except Exception as exc:
            logger.warning("external: base of %s failed (%r)", session, exc)
            return 0
        finally:
            st.busy = False

    def _due(self, manager, session, st, t, idle=False) -> bool:
        if manager.visible(session) is False:           # hidden: nobody edits it in Aspen's window
            return False
        f = FOCUS
        if not getattr(f, "ok", False):
            return t - st.checked >= FALLBACK_S
        pid = _pid(manager, session)
        if not f.front(pid, st.checked):
            return False
        if not idle:
            return t - st.checked >= GAP_S
        return t - st.checked >= (IDLE_FRONT_S if f.showing(pid) else IDLE_GAP_S)

    @staticmethod
    def _back(manager, session, st) -> bool:
        """The user has left Aspen's window since the last compare: it was in front at a tick
        since then and is not now (the foreground known)."""
        f = FOCUS
        if not getattr(f, "ok", False):
            return False
        pid = _pid(manager, session)
        return not f.showing(pid) and f.front(pid, st.checked)

    def check(self, manager, session, why=None, call=None, force=False, idle=False) -> list:
        """Compare ``session`` if the gates let it (``force``: past the focus and time gates;
        ``idle``: idle_check's rules) and record what differs. Returns the records written."""
        if not enabled() or not session or activity.holder(session) is not None:
            return []
        model = manager.model_id(session)
        t = now()
        with self._lock:
            st = self.state(session, model)
            if st is None or st.busy or not (force or self._due(manager, session, st, t, idle)):
                STATS["skipped"] += 1
                return []
            st.busy = True
            back = self._back(manager, session, st)
        try:
            app = manager.get_app(session)
            return [] if app is None else self._compare(manager, session, app, st, model, why, call, back)
        except Exception as exc:
            logger.warning("external: compare of %s failed (%r)", session, exc)
            return []
        finally:
            st.checked, st.busy = t, False

    def _compare(self, manager, session, app, st, model, why, call, back=False) -> list:
        STATS["checks"] += 1
        t0 = _perf()
        objs = self._topology(session, app, st)
        ran = self._results(manager, session, st, model)
        saved = self._file(manager, session, st)
        full = ran is not None or saved is not None or back      # back: the user left Aspen's window
        limit = max(t0 + BUDGET_MS / 1e3, _perf() + VALUES_MIN_MS / 1e3)
        vals = self._values(session, app, st, None if full else limit)
        if not (objs or vals or full):
            return []
        jt = journal.now()
        g = journal.GROUPS.external(jt, session)
        common = {"actor": "external", "via": "aspen", "session": session, "model": model,
                  "group": g["id"] if g else None, "call": call, "why": why}
        recs = [journal.entry("change", op=op, target=tg, status="changed", detect="topology", since=since, **common)
                for op, tg, since in objs]
        for key, before, after, since, src in vals:
            path, n = journal.split_key(key)
            tg = journal.label(path)
            if n is not None:
                tg["attr"] = n
            recs.append(journal.entry("change", op="attr" if n is not None else "value", target=tg, before=before,
                                      after=after, status="changed", detect="watch", since=since, known=src, **common))
        out = []
        if recs:
            journal.append(model, recs)              # the edits first: the run's inputs include them
            out += recs
        tail = []
        if ran is not None:
            b = runlog.since_last(manager, session)
            f = probes.run_state(app)
            runlog.after_run(b, manager, f)
            tail.append(journal.entry("change", op="run", detect="results", since=ran, **f, **common))
        if saved is not None:
            tail.append(journal.entry("change", op="save", target={"path": saved[0]}, file=saved[0], status="changed",
                                      detect="file", since=saved[1], **common))
        if tail:
            journal.append(model, tail)
            out += tail
        STATS["found"] += len(out)
        return out

    def _topology(self, session, app, st) -> list:
        """[(op, target, since)] for the elements added or removed since the names were last
        read (none the first time). Each compare counts every folder's children and reads the
        names of one folder in turn -- and of any whose count changed: a folder's names cost
        ~0.3 ms a child by DISPID (23 blocks 9 ms, 46 streams 14, components 13), its count one
        Invoke, so a rename (the count unchanged) is found within len(FOLDERS) compares."""
        out, t = [], journal.now()
        turn, st.turn = st.turn % len(FOLDERS), st.turn + 1
        for i, (folder, kind) in enumerate(FOLDERS):
            try:
                els = _elements(nodes.find(session, app, folder))
                if els is None:
                    continue
                count, old = dispid.get(els, "Count"), st.topo.get(folder)
                if old is not None and i != turn and count == len(old):
                    continue
                names = [str(dispid.get(_item(els, k), "Name")) for k in range(count)]
            except Exception as exc:
                logger.debug("external: the names under %s not read (%r)", folder, exc)
                continue
            cur = {n.upper(): n for n in names}
            with self._lock:
                old, st.topo[folder] = st.topo.get(folder), cur
                if old is None:
                    continue
                for up, n in cur.items():
                    if up not in old:
                        out.append(("add", {"kind": kind, "name": n, "path": f"{folder}\\{n}"}, st.topo_t))
                for up, n in old.items():
                    if up not in cur:
                        out.append(("remove", {"kind": kind, "name": n, "path": f"{folder}\\{n}"}, st.topo_t))
                        st.drop(f"{folder}\\{n}")
        for op, tg, _ in out:
            if op == "add":
                typ = probes._type(nodes.find(session, app, tg["path"]))
                if typ:
                    tg["type"] = typ
        st.topo_t = t
        return out

    def _file(self, manager, session, st):
        """(file, since) when the session's file changed since the server knew it; else None."""
        f = manager.session_file(session)
        m, t = _mtime(f), journal.now()
        with self._lock:
            if f != st.file or st.mtime is None or m is None:
                st.file, st.mtime, st.mtime_t = f, m, t    # first seen, or the server bound another
                return None
            if m == st.mtime:
                return None
            since = st.mtime_t
            st.mtime, st.mtime_t = m, t
            return f, since

    def _results(self, manager, session, st, model):
        """When the model ran with no run in the journal since its results were last read: the
        time of that read (the run happened after it); else None. The last read is runlog's
        after-read of the last measured run, or this watch's own read of the same results since
        (``st.res``: which after-read it followed, and the journal's last run time then)."""
        p = runlog.peek(manager, session)
        if p is None:
            st.res = None
            return None
        ran = (journal.summary(model) or {}).get("last_run_t") or 0.0
        mine = st.res
        if mine and mine["run"] == p["run"] and mine["paths"] == p["paths"]:
            base, newer = mine, mine["ran"] != ran                # a run recorded since my read
        else:
            base = {"vals": p["was"], "t": p.get("t") or 0.0}
            newer = ran > base["t"] + RUN_EPS                     # a run recorded after the after-read's
        st.res = {"run": p["run"], "paths": p["paths"], "vals": p["now"], "t": journal.now(), "ran": ran}
        if newer:                                                 # its results: nothing to find
            return None
        moved = any(runlog._moved(x, a, b) is not None for x, a, b in zip(p["paths"], base["vals"], p["now"]))
        return base["t"] if moved else None

    def _values(self, session, app, st, limit) -> list:
        """[(key, before, after, since, src)] of the known values that differ now, reading the
        AI's reads first, then the longest unverified, until ``limit`` (None: all)."""
        with self._lock:
            snap = sorted(((key, k, k.t) for key, k in st.known.items()), key=lambda x: (not x[1].seen, x[1].v))
        found, n = [], 0
        for key, k, kt in snap:
            if limit is not None and n and _perf() > limit:
                break
            state = _read(session, app, key, k.state)
            n += 1
            with self._lock:
                if st.known.get(key) is not k or k.t != kt:     # learned meanwhile: that is newer
                    continue
                if state is None:
                    del st.known[key]
                    st.missing.add(key)
                    continue
                k.v, k.seen = next(_ORDER), False
                if _differs(k.state, state):
                    found.append((key, dict(k.state), state, k.t, k.src))
                    k.state, k.t, k.src = {**k.state, **state}, journal.now(), "journal"
                else:
                    for x, v in state.items():
                        k.state.setdefault(x, v)
        STATS["read"] += n
        return found


WATCH = Watch()


# ---------------------------------------------------------------------------- entry points
def learn(model, recs) -> None:
    """journal.listen's function: WATCH.learn (the WATCH of the moment)."""
    WATCH.learn(model, recs)


def configure(paths_of=None, start=True) -> None:
    """server.py, once: the journal tells ``learn`` what it records, and (``start``) the
    foreground watch starts. ``paths_of(manager, session)``: the paths ``base`` reads."""
    global _PATHS_OF
    if paths_of is not None:
        _PATHS_OF = paths_of
    journal.listen(learn)
    if start and enabled():
        FOCUS.start()


def check(manager, session, why=None, call=None, force=False) -> list:
    """One gated compare of ``session`` (``Watch.check``): the records written."""
    return WATCH.check(manager, session, why=why, call=call, force=force)


def _sessions(manager, session=None) -> list:
    return [session] if session else list(getattr(manager, "_sessions", None) or ())    # no COM


def pre_call(manager, tool, args=None, call=None) -> list:
    """Before an AI tool call: compare the session it names (every open one when it names none),
    gated; a session touched for the first time is read as the baseline instead. Not before the
    tools that open a model or only configure the server. Returns the records written -- in the
    journal before anything of the call's own."""
    if tool in SKIP_TOOLS or not enabled():
        return []
    out = []
    for s in _sessions(manager, (args or {}).get("session_name")):
        st = WATCH._s.get(s)
        if st is None or not st.based:
            WATCH.base(manager, s)
        else:
            out += WATCH.check(manager, s, why=f"ai_call:{tool}", call=call)
    return out


def idle_check(manager, sessions=None) -> list:
    """The sync loop's tick: compare a session (already read by ``base``) once Aspen has left the
    front after being there -- the user came back -- IDLE_GAP_S after its last compare, or after
    IDLE_FRONT_S while Aspen stays in front; the foreground unknown, every FALLBACK_S."""
    if not enabled():
        return []
    out = []
    for s in sessions if sessions is not None else _sessions(manager):
        st = WATCH._s.get(s)
        if st is not None and st.based:
            out += WATCH.check(manager, s, why="idle", idle=True)
    return out


def checked(session):
    """When ``session`` was last compared (the gates' clock), or None: not since this server
    began watching it."""
    st = WATCH._s.get(session)
    return (st.checked or None) if st is not None else None


# ---------------------------------------------------------------------------- the deep compare
_ENUM_IID = "{00020404-0000-0000-C000-000000000046}"     # IEnumVARIANT


class _ByDispid:
    """The deep walk's way through the tree (knowledge_tools._iter_tree ``access``): members by
    DISPID on bare nodes, a collection's children one at a time -- by position, and from its
    _NewEnum only for a table keyed by label (``Item(integer)`` None there, knowledge_tools'
    note). V15, a RadFrac's Input (~1270 children): win32com's wrapper costs Name 0.35 ms and
    Elements 0.68 ms a node, listing the children at once (knowledge_tools._children) 0.3-0.6 s
    and making the enumerator ~0.1 s, each one step the event loop cannot interrupt; this way
    the same nodes and values in ~0.3 of the time. An object with no DISPIDs gets
    win32com's access. ``errors``: collections whose listing failed (the walk is then not whole).
    Aspen's internal fault (knowledge_tools.server_fault) is not one of them: it is raised, so the
    walk stops there and Deep flags the session (Item(i) faults V15 on some label-keyed tables)."""

    def __init__(self):
        self.errors = 0

    @staticmethod
    def elements(node):
        r = dispid.raw(node, "Elements")
        return node.Elements if r is dispid.LATE else _bare(r)

    @staticmethod
    def name(child):
        return dispid.get(child, "Name")

    def children(self, els):
        i = 0
        try:
            n = dispid.get(els, "Count")
            while i < n:
                c = _item(els, i)
                if c is None:
                    break                            # keyed by label: its enumerator from here
                yield c
                i += 1
            if i < n:
                r = dispid._fast(els, "_NewEnum", dispid.GET_ARGS, ())    # (METHOD | PROPERTYGET, as win32com)
                kids = iter(els) if r is dispid.LATE else _enum(r.QueryInterface(_ENUM_IID))
                for k, c in enumerate(kids):
                    if k >= i:
                        yield c
        except Exception as exc:
            if knowledge_tools.server_fault(exc):
                raise
            self.errors += 1
            logger.debug("external: a collection's children not listed (%r)", exc)


def _enum(en):
    while True:
        batch = en.Next(1)
        if not batch:
            return
        yield _bare(batch[0])


def _vu(node) -> list:
    """[value, unit] of a node, by DISPID (two reads); None for what does not read."""
    out = []
    for m in ("Value", "UnitString"):
        try:
            out.append(_plain(dispid.get(node, m)))
        except Exception:
            out.append(None)
    return out


def _base_file(model, kind, name):
    """journal/<model>/deep/<kind>-<NAME>.json.gz (a character a file name may not hold: %XXXX)."""
    safe = re.sub(r"[^A-Za-z0-9_-]", lambda m: "%%%04X" % ord(m.group()), str(name).upper())
    return journal._dir(model) / "deep" / f"{kind}-{safe}.json.gz"


def _load_base(f):
    """The baseline in ``f`` {"v", "t", "n", "partial", "nodes": {rel: [value, unit]}}, or None
    (none yet, or unreadable: a new one is noted)."""
    try:
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            d = json.load(fh)
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.warning("external: deep baseline %s unreadable (%r)", f, exc)
        return None
    ok = isinstance(d, dict) and d.get("v") == 1 and isinstance(d.get("t"), (int, float)) \
        and isinstance(d.get("nodes"), dict)
    return d if ok else None


def _save_base(f, t, vals, partial) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f"{f.name}.{os.getpid()}.tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump({"v": 1, "t": t, "n": len(vals), "partial": bool(partial), "nodes": vals}, fh,
                  ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, f)
    for old in sorted(f.parent.glob("*.json.gz"), key=lambda p: _mtime(str(p)) or 0)[:-DEEP_FILES]:
        try:
            old.unlink()
        except OSError:
            pass


def _told(model, t, root, obj):
    """What the journal has since ``t`` (the baseline's): (why the baseline is not to be used --
    "reopened": an open record, "replaced": the object itself added or removed -- or None,
    {PATH: (after, t)} the latest write to each input under ``root`` -- value records, a loop's
    or restore's net writes, the watch's own external records -- {NAME} of the other elements
    added or removed)."""
    pg = journal.page(model, limit=5000, after=t - 2 * RUN_EPS, scan=20000)
    pre, kind, name = root.upper() + "\\", obj["kind"], obj["name"].upper()
    writes, names = {}, set()
    for r in pg.get("records") or ():                          # newest first: setdefault keeps the latest
        if r.get("kind") != "change":
            continue
        op, rt, ok = r.get("op"), r.get("t") if isinstance(r.get("t"), (int, float)) else 0.0, \
            r.get("status") == "changed"
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        if op == "open" and ok:
            return "reopened", {}, set()
        if op in ("add", "remove") and ok:
            if tg.get("kind") == kind and str(tg.get("name") or "").upper() == name:
                return "replaced", {}, set()
            if tg.get("name"):
                names.add(str(tg["name"]).upper())
        elif op == "value" and ok and isinstance(r.get("after"), dict):
            p = str(tg.get("path") or "").upper()
            if p.startswith(pre):
                writes.setdefault(p, (r["after"], rt))
        elif op in ("summary", "restore"):
            for p, w in (r.get("writes") or {}).items():
                p = str(p).upper()
                if journal.split_key(p)[1] is None and p.startswith(pre) and isinstance(w, dict) \
                        and isinstance(w.get("after"), dict):
                    writes.setdefault(p, (w["after"], rt))
    if pg.get("more"):
        logger.info("external: the journal since the deep baseline of %s was read in part", root)
    return None, writes, names


def _match(state, vu, unit=True) -> bool:
    """A journaled state {"value", "unit"?} is the node's [value, unit] now (the unit only
    when both have one; ``unit`` False: the value alone)."""
    return _same(_plain(state.get("value")), vu[0]) and \
        (not unit or not state.get("unit") or not vu[1] or state.get("unit") == vu[1])


def _deep_diff(root, base, vals, partial, writes, names) -> list:
    """[(path, before, after, since, known)]: the inputs under ``root`` that differ from the
    baseline and the journal does not explain. A node added or removed counts when it holds a
    value, and not when it is an element's own (a component's row). A node only read now or
    only then (``partial``, a partial baseline) is not compared. One edit shows on a node and
    its parent's echo: the node is kept."""
    old = base["nodes"]
    keys = set(vals) & set(old)
    if not partial:
        keys |= set(old) - set(vals)                            # removed since
    if not base.get("partial"):
        keys |= set(vals) - set(old)                            # added since
    out = []
    for rel in sorted(keys):
        b, a = old.get(rel), vals.get(rel)
        if b is not None and a is not None and _same(b[0], a[0]) and _same(b[1], a[1]):
            continue
        if b is None or a is None:
            if (a or b)[0] is None or names & set(rel.upper().split("\\")):
                continue
        b, a = b or [None, None], a or [None, None]
        path = f"{root}\\{rel}"
        up = path.upper()
        w = writes.get(up)
        if w is not None and _match(w[0], a):
            continue                                            # the server's own change (or the watch's find)
        if any(k.startswith(up + "\\") and _match(v[0], a, unit=False) for k, v in writes.items()):
            continue                                            # the parent's echo of a write below it
        before, since, known = (w[0], w[1], "journal") if w is not None else \
            ({"value": b[0], "unit": b[1]}, base["t"], "deep")
        out.append((path, before, {"value": a[0], "unit": a[1]}, since, known))
    return [x for x in out if not any(y[0].upper().startswith(x[0].upper() + "\\")
                                      and _same(y[2]["value"], x[2]["value"]) for y in out)]


class Deep:
    """One deep compare of a block's or stream's inputs (``obj`` {"kind": block | stream,
    "name"}), in turns: ``step()`` reads for about DEEP_TURN_MS (``ms``; the compare, its
    records and the new baseline take one more) and returns True once done, the outcome in
    ``result`` -- {"obj", "status", "t" (its start), "n" (nodes read), "secs" (all turns),
    "turns", "turn_ms" (the longest); when done also "baseline" new | used ("reason" it is new:
    none | reopened | replaced), "found", "ids" (the records), "partial", "gaps" (collections
    not listed, when any)}. status: done | off (the watch off) | bad (not a block or stream) | gone (no
    session, or another model or Aspen in it now) | missing (no such object) | busy (a program
    or the optimizer holds the session) | changed (a structure record during the walk: table
    rows may have moved; nothing noted) | stopped (``stop()``) | error ("fault": Aspen's internal
    fault ended the walk, the session is flagged: manager.note_fault). The caller may run
    anything between two steps (the event loop): each later step first checks the session is
    the same and free. Measured on V15 (20 ms turns): a Heater's ~175 input nodes 0.17 s,
    a RadFrac's ~1290 1.05 s in ~52 turns, a stream's ~155 0.16 s."""

    def __init__(self, manager, session, obj, why="deep"):
        self.m, self.session, self.why = manager, session, why
        obj = obj if isinstance(obj, dict) else {}
        self.obj = {"kind": str(obj.get("kind") or "").strip().lower(), "name": str(obj.get("name") or "").strip()}
        k, n = self.obj["kind"], self.obj["name"]
        self.root = rf"\Data\{_DEEP_ROOTS[k]}\{n}\Input" if k in _DEEP_ROOTS and n else None
        self.model = self.app = self.it = self.result = None
        self.acc = _ByDispid()
        self.vals: dict = {}                     # relative path -> [value, unit], as read now
        self.t0, self.spent, self.turns, self.longest, self.partial = journal.now(), 0.0, 0, 0.0, False
        self.walked = False                      # every node read (or the cap): the compare's turn next

    def step(self, ms=None) -> bool:
        if self.result is not None:
            return True
        t = _perf()
        try:
            if self.it is None:
                if not self._start():
                    return True
            elif self._stale():
                return True
            if not self.walked:
                end = t + (DEEP_TURN_MS if ms is None else ms) / 1e3
                for rel, node in self.it:
                    self.vals[rel[1:]] = _vu(node)
                    if len(self.vals) >= DEEP_MAX or self.spent + _perf() - t > DEEP_S:
                        self.partial = True
                        break
                    if _perf() >= end:
                        return False
                self.walked = True
                return False                     # the compare, record and save: a turn of their own
            self._finish()
        except Exception as exc:
            logger.warning("external: deep compare of %s %s failed (%r)", self.obj["kind"], self.obj["name"], exc)
            fault = knowledge_tools.server_fault(exc)
            if fault:                                # its runs would never return (aspen_manager.note_fault)
                note = getattr(self.m, "note_fault", None)
                if note is not None:
                    note(self.session, exc, tool="deep compare")
            self._end("error", error=f"{type(exc).__name__}: {exc}"[:200], **({"fault": True} if fault else {}))
        finally:
            dt = _perf() - t
            self.spent, self.turns, self.longest = self.spent + dt, self.turns + 1, max(self.longest, dt)
            if self.result is not None:
                self.result.update(secs=round(self.spent, 3), turns=self.turns, turn_ms=round(self.longest * 1e3, 1))
        return True

    def stop(self) -> None:
        """Give up a compare not done (status "stopped": nothing recorded or noted)."""
        if self.result is None:
            self._end("stopped")

    def _end(self, status, **kw) -> bool:
        """The outcome; returns False (``return self._end(...)`` in a step that cannot go on)."""
        if self.it is not None:
            self.it.close()                      # the walk's nodes let go
        self.result = {"obj": dict(self.obj), "status": status, "t": self.t0, "n": len(self.vals), **kw}
        STATS["deep"] += 1
        return False

    def _start(self) -> bool:
        """The first step: the session, its model, the object's Input node. False: ended."""
        if not enabled():
            return self._end("off")
        if self.root is None:
            return self._end("bad")
        app = self.m.get_app(self.session)
        self.model = self.m.model_id(self.session) if app is not None else None
        if app is None or not self.model:
            return self._end("gone")
        if activity.holder(self.session) is not None:
            return self._end("busy")
        root = nodes.find(self.session, app, self.root)
        if root is None:
            return self._end("missing")
        self.app = nodes._ref(app)               # (never the app itself)
        self.it = knowledge_tools._iter_tree(root, "", input_only=True, access=self.acc)
        return True

    def _stale(self) -> bool:
        """A later step: True (ended) when the session holds another Aspen or model now, a
        writer holds it, or a structure record came since the walk began."""
        app = self.m.get_app(self.session)
        if app is None or not nodes._owns(self.app, app) or self.m.model_id(self.session) != self.model:
            return not self._end("gone")
        if activity.holder(self.session) is not None:
            return not self._end("busy")
        if runlog._DIRTY.get(self.model, 0.0) >= self.t0 - RUN_EPS:
            return not self._end("changed")
        return False

    def _finish(self) -> None:
        """The walk is over: compare with the baseline, record, note the new baseline."""
        f = _base_file(self.model, self.obj["kind"], self.obj["name"])
        base, reason, writes, names = _load_base(f), "none", {}, set()
        if base is not None:
            reason, writes, names = _told(self.model, base["t"], self.root, self.obj)
            if reason is not None:
                base = None
        recs, whole = [], not (self.partial or self.acc.errors)      # every node read: a removal is one
        diff = _deep_diff(self.root, base, self.vals, not whole, writes, names) if base is not None else []
        if diff:
            g = journal.GROUPS.external(journal.now(), self.session)
            common = {"actor": "external", "via": "aspen", "session": self.session, "model": self.model,
                      "group": g["id"] if g else None, "why": self.why}
            recs = [journal.entry("change", op="value", target=journal.label(p), before=b, after=a, status="changed",
                                  detect="deep", since=s, known=k, **common) for p, b, a, s, k in diff]
            journal.append(self.model, recs)
        keep = dict(base["nodes"]) if base is not None and not whole else {}
        keep.update(self.vals)                   # not whole: what was not read now stays as noted then
        extra = {"gaps": self.acc.errors} if self.acc.errors else {}
        try:
            _save_base(f, self.t0, keep, base.get("partial") if base is not None and not whole else not whole)
        except OSError as exc:                   # (the records stand: the journal explains them next time)
            logger.warning("external: deep baseline %s not written (%r)", f, exc)
            extra["noted"] = False
        self._end("done", baseline="used" if base is not None else "new", reason=None if base is not None else reason,
                  found=len(recs), ids=[r["id"] for r in recs][:50], partial=self.partial, **extra)


def deep(manager, session, obj, why="deep") -> dict:
    """A deep compare (``Deep``) in one go, for a caller with no event loop to yield to: its result."""
    d = Deep(manager, session, obj, why=why)
    while not d.step():
        pass
    return d.result
