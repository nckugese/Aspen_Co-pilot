"""Who is working on which Aspen session right now: one writer per session and the
calls in flight.

Writers. A workbench program (``workbench_tools.execute``, from its start to its end, also
when the AI started it with workbench_run) and the MCP ``optimize`` (tools/intercept.py,
for its whole call) *hold* their session. While a session is held:

- the AI's other changing calls wait for it, up to ``WRITER_WAIT_S`` (``wait_free``: an
  asyncio wait, so the holder's own task keeps running on the event loop), and are then
  refused with ``refusal()``'s text -- no exception, and journaled as ``refused``;
- the window's own writes (inspector, Run, Save, apply a point) are refused at once, and a
  program started from the window is queued (tools/workbench_tools.py) -- also a write the
  window posted while the session was held but that is read only after the hold ended
  (``held_then``: an optimizer whose evaluations never let the event loop run);
- reads always pass.

A program the user steps through keeps its hold while it waits before a step,
with no timeout; ``note`` marks the hold paused, and the refusal says where and why. One that
waits for the user to set a field (a your-turn step) is marked ``waiting_user``:
the user's own writes pass (the workbench lets them), and the AI's changing calls are refused
at once -- no WRITER_WAIT_S: only the user ends that wait -- saying which field it waits for.

A call that names no session waits on every session (``close_aspen_plus()`` closes them all).

Calls in flight. ``begin`` / ``phase`` / ``end`` keep what each tool call is doing (the AI's
through tools/intercept.py, a workbench program's slow statements through its runner), and
``last`` the one that ended most recently; ``snapshot()`` is all of it, JSON-ready.

The heartbeat. While the workbench's sync loop serves a window, the beacon thread
(``beacon`` / ``stop_beacon``) writes ``heartbeat()`` to its file every ``BEAT_S``, and
within ``GAP_S`` of a change (``poke``: any begin, phase, end, hold or release); the loop
itself only ``tick``s. A sync tool or program statement that keeps the loop waiting inside
COM (pywin32 lets go of the GIL there) cannot stall it: the window reads ``t`` (fresh),
``loop`` (behind) and ``act`` to say "Aspen is calculating" instead of "disconnected".

Stdlib only; importing it does no I/O; never touches COM, the beacon thread included.
Changes come from the event loop thread; readers may be other threads (a copy is taken
under the lock).
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os
import threading
import time
from pathlib import Path

WRITER_WAIT_S = 10.0          # how long a changing call waits for a session's holder
POLL_S = 0.25                 # how often it looks
now = time.time               # the clock of holds, calls and the wait; module attributes, so they can be
_sleep = asyncio.sleep        # ... overridden together (a virtual clock: WRITER_WAIT_S costs nothing)

_lock = threading.Lock()
_ids = itertools.count(1)
_holds: dict[int, dict] = {}  # token -> {"session", "actor", "since", ...}; oldest first
_walls: dict[int, float] = {}  # token -> wall-clock time (time.time()) its hold began
_past: dict[str, list] = {}   # session -> its last PAST_MAX released holds, with "t0" / "t1" (wall clock)
PAST_MAX = 4
_acts: dict[int, dict] = {}   # token -> {"call", "actor", "tool", "session", "phase", "since", ...}
_last: dict | None = None

logger = logging.getLogger(__name__)


def _put(d: dict, info: dict) -> dict:
    d.update((k, v) for k, v in info.items() if v is not None)
    return d


# ---------------------------------------------------------------------------- writers
def hold(session, actor: str, **info) -> int:
    """``session`` is being changed by ``actor`` (program | optimizer ...) until ``release``;
    ``info``: what the refusal and the window show (tab, title, via, tool, algorithm, call)."""
    with _lock:
        token = next(_ids)
        _holds[token] = _put({"session": session, "actor": actor, "since": now()}, info)
        _walls[token] = time.time()
    poke()
    return token


def note(token, **info) -> None:
    """Change what a hold says (``info``; False removes a field) -- a workbench program paused
    before a step: ``paused`` its sid, ``paused_n`` its number, ``paused_since``
    (this module's clock), ``paused_group`` "1 of 2" before a group's first step.
    None, or a hold released already: nothing."""
    if token is None:
        return
    with _lock:
        h = _holds.get(token)
        if h is None:
            return
        for k, v in info.items():
            if v is False:
                h.pop(k, None)
            elif v is not None:
                h[k] = v
    poke()


def release(token) -> None:
    """End a hold (None, or one released already: nothing); its span is kept for ``held_then``."""
    if token is not None:
        with _lock:
            h, t0 = _holds.pop(token, None), _walls.pop(token, None)
            if h is not None and t0 is not None:
                past = _past.setdefault(h["session"], [])
                past.append({**h, "t0": t0, "t1": time.time()})
                del past[:-PAST_MAX]
        poke()


def held_then(session, t) -> dict | None:
    """The hold that had ``session`` at wall-clock time ``t`` (time.time(): when the window
    posted an event), still on or released since; None when none did (or ``t`` is None)."""
    try:
        t = float(t)
    except (TypeError, ValueError):
        return None
    with _lock:
        for token, h in _holds.items():
            if h["session"] == session and _walls.get(token, t + 1) <= t:
                return dict(h)
        for p in reversed(_past.get(session, ())):
            if p["t0"] <= t < p["t1"]:                 # (time.time() may tick ~15 ms at a time)
                return {k: v for k, v in p.items() if k not in ("t0", "t1")}
    return None


def holder(session=None) -> dict | None:
    """Who holds ``session`` (None: any session) -- the oldest hold -- or None."""
    with _lock:
        for h in _holds.values():
            if session is None or h["session"] == session:
                return dict(h)
    return None


async def wait_free(session=None, timeout: float | None = None, act: int | None = None) -> dict | None:
    """Wait until nobody holds ``session`` (None: any), at most ``timeout`` seconds
    (WRITER_WAIT_S); the call ``act`` shows phase ``wait`` meanwhile. Returns None once free,
    right after the check that found it free -- the caller acts (or holds) before anything
    else runs -- or the hold still there when the time is up; a hold waiting for the user
    (``waiting_user``) at once."""
    held = holder(session)
    if held is None or held.get("waiting_user"):        # (the user's turn: refused at once)
        return held
    end = now() + (WRITER_WAIT_S if timeout is None else timeout)
    was = phase(act, "wait", holder=held.get("actor"))
    try:
        while True:
            left = end - now()
            if left <= 0:
                return held
            await _sleep(min(POLL_S, left))
            held = holder(session)
            if held is None or held.get("waiting_user"):
                return held
    finally:
        phase(act, was, holder=False)


def _took(seconds: float) -> str:
    s = max(0, int(seconds))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60} s"
    return f"{s // 3600} h {s % 3600 // 60} min"


def refusal(held: dict) -> str:
    """The answer to a changing call refused because ``held`` holds its session (a program the
    user is stepping through: where it is paused, and that it waits for them)."""
    actor = held.get("actor")
    if held.get("waiting_user"):                        # a your-turn step
        what = held.get("wait_label") or "a field"
        return (f"Not applied: session '{held.get('session')}' is paused at a 'your turn' step: the user is "
                f"setting {what} by hand. Reads work; workbench_read shows the step (last_run.wait). The run "
                f"goes on when they press Done in the workbench.")
    if actor == "program" and held.get("paused"):
        title = held.get("title") or held.get("tab") or "?"
        n = held.get("paused_n")
        at = f"step {n}" if n is not None else f"statement {held['paused']}"
        took = _took(now() - held.get("paused_since", now()))
        if held.get("paused_group"):                    # a proposal applied by group
            return (f"Not applied: session '{held.get('session')}' is held by a workbench program paused at {at}, "
                    f"before group {held['paused_group']}, of tab '{title}' — the user is applying it group by group "
                    f"(paused {took}). Reads still work. It stays paused, with no timeout, until the user applies the "
                    f"group, applies the rest or stops it in the window: ask them to if you need the session "
                    f"(workbench_read shows last_run.paused).")
        return (f"Not applied: session '{held.get('session')}' is held by a workbench program paused at {at} of "
                f"tab '{title}' — the user is stepping through it (paused {took}). Reads still work. It stays "
                f"paused, with no timeout, until the user runs the next step, continues or stops it in the window: "
                f"ask them to if you need the session (workbench_read shows last_run.paused).")
    if actor == "program":
        title = held.get("title") or held.get("tab") or "?"
        if held.get("via") == "mcp":
            who, then = (f"the workbench program you started on tab '{title}'",
                         "Wait for it: its workbench_run answers when it ends.")
        else:
            who, then = (f"the workbench program on tab '{title}'",
                         "Wait for it (workbench_read shows its status), or ask the user to stop it.")
    elif actor == "optimizer":
        algo = held.get("algorithm")
        who, then = "your optimize call" + (f" ({algo})" if algo else ""), "Wait for it to finish."
    else:
        tool = held.get("tool")
        who, then = (actor or "another writer") + (f" ({tool})" if tool else ""), "Wait for it."
    return (f"Not applied: session '{held.get('session')}' is being changed by {who} "
            f"(running {_took(now() - held.get('since', now()))}). Reads still work. {then}")


# ---------------------------------------------------------------------------- calls in flight
def begin(actor: str, tool: str, session=None, phase: str = "call", target=None, **info) -> int:
    """A call starts: ``phase`` call | aspen | compute | wait; ``target`` what it
    works on (tools/intercept.target_of); ``info``: call (the journal's call id), via, tab."""
    with _lock:
        token = next(_ids)
        _acts[token] = _put({"call": info.pop("call", None) or f"a{token}", "actor": actor, "tool": tool,
                             "session": session, "phase": phase, "since": now(), "target": target}, info)
    poke()
    return token


def phase(token, name, **info):
    """Set a call's phase (and ``info``; False removes a field); returns the one it had."""
    if token is None:
        return None
    with _lock:
        a = _acts.get(token)
        if a is None:
            return None
        was, a["phase"] = a["phase"], name
        for k, v in info.items():
            if v is False:
                a.pop(k, None)
            elif v is not None:
                a[k] = v
    poke()
    return was


def end(token, status: str = "ok") -> None:
    """A call ended: ok | error | refused. It becomes ``last``."""
    global _last
    if token is None:
        return
    with _lock:
        a = _acts.pop(token, None)
        if a is not None:
            _last = {"actor": a["actor"], "tool": a["tool"], "session": a["session"], "target": a["target"],
                     "end": now(), "status": status}
    poke()


def snapshot() -> dict:
    """What the heartbeat carries: ``act`` the calls in flight, oldest first;
    ``last`` the latest one to end; ``holders`` {session: {actor, since, tab, title, via,
    tool}}."""
    with _lock:
        act = [dict(a) for a in _acts.values()]
        last = dict(_last) if _last else None
        held = {}
        for h in _holds.values():
            held.setdefault(h["session"], {k: v for k, v in h.items() if k != "session"})
    return {"act": act, "last": last, "holders": held}


# ---------------------------------------------------------------------------- the heartbeat
BEAT_S = 1.0                  # the beacon writes at least this often...
GAP_S = 0.2                   # ... and after a change, no sooner than this after its last write
ACT_MAX = 20                  # calls in flight the heartbeat lists at most (the oldest)

_loop: float | None = None    # when the event loop last came round (tick)
_wake = threading.Event()     # set by poke: something the heartbeat shows changed
_pause = threading.Event()    # never set: short waits that an overridden clock does not touch
_write_lock = threading.Lock()
_beacon_lock = threading.Lock()
_beacon = None                # the running _Beacon


def tick() -> None:
    """The event loop came round (the workbench's sync loop, every pass)."""
    global _loop
    _loop = time.time()


def poke() -> None:
    """Something the heartbeat shows changed: the beacon writes it within GAP_S."""
    _wake.set()


def heartbeat() -> dict:
    """The heartbeat file's content (v1): ``t`` when written, ``pid`` this
    server's, ``loop`` its event loop's last tick (None before the first), then
    ``snapshot()``: ``act``, ``last``, ``holders``."""
    snap = snapshot()
    del snap["act"][ACT_MAX:]
    return {"v": 1, "t": round(time.time(), 3), "pid": os.getpid(),
            "loop": None if _loop is None else round(_loop, 3), **snap}


def write_heartbeat(path) -> bool:
    """Write ``heartbeat()`` to ``path`` through a temporary file and os.replace, so a
    reader never sees half of it. Never creates the folder; False when it could not write."""
    path = Path(path)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        text = json.dumps(heartbeat(), separators=(",", ":"), default=str)
    except Exception as exc:
        logger.warning("activity: heartbeat not written (%r)", exc)
        return False
    with _write_lock:
        try:
            tmp.write_text(text, encoding="utf-8")
        except OSError:                   # the folder is gone: nothing to beat into
            return False
        for _ in range(10):
            try:
                os.replace(tmp, path)
                return True
            except PermissionError:       # the window is reading it just now
                _pause.wait(0.02)
            except OSError:
                break
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


class _Beacon(threading.Thread):
    """Writes the heartbeat every BEAT_S, and GAP_S after a poke; never touches COM."""

    def __init__(self, path: Path):
        super().__init__(name="aspen-mcp heartbeat", daemon=True)
        self.path, self.halt = path, threading.Event()

    def run(self) -> None:
        last = 0.0
        while not self.halt.is_set():
            _wake.wait(max(0.0, last + BEAT_S - time.monotonic()))
            if self.halt.wait(max(0.0, last + GAP_S - time.monotonic())):
                return
            _wake.clear()
            last = time.monotonic()
            try:
                write_heartbeat(self.path)
            except Exception as exc:      # keep beating: the window reads a stalled one as "gone"
                logger.warning("activity: heartbeat beacon (%r)", exc)


def beacon(path) -> None:
    """Start the beacon writing the heartbeat at ``path`` (moved there if it beats elsewhere;
    nothing if it already beats there)."""
    global _beacon
    path = Path(path)
    with _beacon_lock:
        b = _beacon
        if b is not None and b.is_alive() and not b.halt.is_set():
            if b.path == path:
                return
            b.halt.set()
        _beacon = _Beacon(path)
        _beacon.start()


def stop_beacon(path=None, wait: float = 1.0) -> None:
    """Stop the beacon (only if it beats at ``path``, when given); waits up to ``wait`` s."""
    global _beacon
    with _beacon_lock:
        b = _beacon
        if b is None or (path is not None and b.path != Path(path)):
            return
        _beacon = None
        b.halt.set()
    _wake.set()
    if b is not threading.current_thread():
        b.join(wait)


def beating(path=None) -> bool:
    """Whether the beacon runs (and writes ``path``, when given)."""
    b = _beacon
    return b is not None and b.is_alive() and not b.halt.is_set() and (path is None or b.path == Path(path))
