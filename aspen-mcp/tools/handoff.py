"""Handing the workbench and its Aspen sessions from one server process to another.

The standalone workbench (``aspen-mcp --workbench``, tools/standalone.py) lets the user work
without an AI client: that process holds the Aspen sessions and serves the window. When an AI
client's server gets its first tool call while a standalone one serves the window, it asks for
them (``take_over``); the standalone answers (``serve``), lets go of its sessions without closing
Aspen (aspen_manager.release) and exits; the asker takes the same running documents
(aspen_manager.attach) and the window, which stays open. Nothing is saved, closed or reopened.

One file, ``<workbench>/handoff.json``, written whole by whoever's turn it is:

  {"id", "to": the asker's pid, "from": the owner's pid, "t", "state": "asked"}
  ... "state": "released", "sessions": [{"session", "path", "model", "visible", "pid"}]
  ... "state": "refused", "why": "a program is running"
  ... "state": "taken"            (the asker has them: the old owner may exit)

Only a standalone owner is ever asked (owner.json ``standalone``): two AI clients' servers
never take each other's sessions.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

FILE = "handoff.json"
ASK_S = 12.0          # how long the asker waits for an answer
TAKEN_S = 20.0        # how long the old owner keeps its sessions alive for the asker to take
FRESH_S = 30.0        # a request older than this is nobody's
RETRY_S = 10.0        # after a refusal, not asked again this soon
BUSY = "a program or a run is in progress there"

_LAST = {"refused": 0.0, "why": None}
_LOCK = asyncio.Lock()   # a client sends calls side by side: the first asks, the others wait for its answer


def _read(root: Path) -> dict | None:
    try:
        d = json.loads((root / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _write(root: Path, d: dict) -> None:
    tmp = root / f"{FILE}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, root / FILE)


def refused() -> str | None:
    """Why the standalone workbench last refused to hand over, while that still holds."""
    return _LAST["why"] if time.time() - _LAST["refused"] < RETRY_S else None


# ---------------------------------------------------------------------------
# The asker (an AI client's server)
# ---------------------------------------------------------------------------

async def take_over(wb, manager) -> list[str] | None:
    """Before a tool call: when a standalone workbench serves the window, take its sessions and
    the window. Returns the session names taken ([]: it had none), or None when there was
    nothing to take or it refused (``refused`` says why). Costs one small file read when this
    server serves no window; nothing when it does."""
    ws = wb._WS
    if ws is not None and ws.task is not None and not ws.task.done():
        return None
    owner = wb._owner_other()
    if owner is None or not owner.get("standalone"):
        return None
    async with _LOCK:
        owner = wb._owner_other()                         # (another call of this server took them meanwhile)
        if owner is None or not owner.get("standalone"):
            return None
        return await _take(wb, manager, owner)


def _busy(root: Path) -> bool:
    """The owner's heartbeat says a call is in flight or a session is held (a program, a run): its
    beacon thread writes that also while the work holds its loop, when it could not answer."""
    try:
        hb = json.loads((root / "heartbeat").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(hb, dict) and bool(hb.get("act") or hb.get("holders"))


async def _take(wb, manager, owner: dict) -> list[str] | None:
    if time.time() - _LAST["refused"] < RETRY_S:
        return None
    if _busy(wb._ROOT):                                   # not asked: it would not answer in time
        _LAST.update(refused=time.time(), why=BUSY)
        return None
    root, rid = wb._ROOT, uuid.uuid4().hex[:12]
    _write(root, {"id": rid, "to": os.getpid(), "from": owner["pid"], "t": time.time(), "state": "asked"})
    end, ans = time.time() + ASK_S, None
    while time.time() < end:
        await asyncio.sleep(0.1)
        d = _read(root)
        if d is not None and d.get("id") == rid and d.get("state") in ("released", "refused"):
            ans = d
            break
        if not wb._pid_alive(owner["pid"]):
            break
    if ans is None or ans["state"] == "refused":
        why = (ans or {}).get("why") or "it did not answer"
        _LAST.update(refused=time.time(), why=why)
        logger.warning("workbench: the standalone workbench (pid %s) kept its sessions: %s", owner["pid"], why)
        try:
            (root / FILE).unlink()
        except OSError:
            pass
        return None
    taken = []
    for s in ans.get("sessions") or []:
        try:
            res = manager.attach(s.get("path"), session_name=s.get("session"), model_id=s.get("model"),
                                 pid=s.get("pid"))
        except Exception:
            logger.warning("workbench: session %r not taken over", s.get("session"), exc_info=True)
            res = None
        if res is not None and s.get("session") in manager.session_names():
            taken.append(s["session"])
        else:
            logger.warning("workbench: session %r of the standalone workbench was not found running", s.get("session"))
    _write(root, dict(ans, state="taken", t=time.time()))
    end = time.time() + 5.0                               # the window is this server's once the old one is gone
    while time.time() < end and wb._pid_alive(owner["pid"]):
        await asyncio.sleep(0.1)
    try:
        live = wb.ensure_live(manager, fresh=True)
        if live is not None:
            live.state["open_sessions"] = manager.session_names()
            live.save()
    except Exception:
        logger.warning("workbench: the window was not taken over", exc_info=True)
    logger.info("workbench: took over %d session(s) from the standalone workbench: %s", len(taken), taken)
    return taken


def _waiting(wb, live, taken: list[str]) -> list[dict]:
    """The Ask AI requests the user sent while no AI client was there (open, unanswered), queued
    again for this server's push (the old process's queue went with it)."""
    out = []
    for name in taken:
        for note in (live.state["sessions"].get(name) or {}).get("notes") or []:
            if note.get("status") != "open" or note.get("reply") or note.get("event"):
                continue
            for k in ("delivered", "undelivered", "pushed", "handed", "read"):
                note.pop(k, None)
            live.asks.append({"session": name, "tab": live.tab(note.get("tab")), "note": note})
            out.append({"session": name, "id": note.get("id"), "text": str(note.get("text") or "")})
    return out


async def before(wb, manager) -> str | None:
    """intercept's ``before`` hook: ``take_over``, and what the AI is told of it at the end of the
    call's answer -- the sessions it now has, and the Ask AI requests that waited in the window."""
    taken = await take_over(wb, manager)
    if taken is None:
        why = refused()
        owner = wb._owner_other() if why else None
        if owner is None or not owner.get("standalone"):
            return None
        return ("[workbench] The user is working in the standalone workbench (no AI client), which kept its "
                f"Aspen sessions and window for now: {why}. This server has none of them until it lets go -- "
                "call again when that has ended; do not open the same files a second time.")
    text = ("[workbench] The user was working in the standalone workbench (no AI client). Its Aspen "
            f"session(s) and window are now this server's, as they were -- nothing was saved, closed or "
            f"reopened: {', '.join(taken) or 'none open'}.")
    live = wb._WS
    waiting = _waiting(wb, live, taken) if live is not None else []
    if waiting:
        live.save()
        text += (f" {len(waiting)} Ask AI request(s) wait in the window; answer each there with "
                 "workbench_edit(note_replies=[{\"id\": <note id>, \"reply\": ...}]): "
                 + "; ".join(f"{w['id']} (session {w['session']}): {w['text'][:300]}" for w in waiting))
    return text


# ---------------------------------------------------------------------------
# The owner (the standalone workbench)
# ---------------------------------------------------------------------------

async def serve(wb, manager, ws) -> bool:
    """One look at handoff.json by the standalone workbench's loop. True: its sessions and the
    window went to the asker, and this process should exit (without closing Aspen)."""
    root = wb._ROOT
    d = _read(root)
    if d is None or d.get("state") != "asked" or d.get("from") != os.getpid():
        return False
    if time.time() - float(d.get("t") or 0) > FRESH_S or not wb._pid_alive(int(d.get("to") or 0)):
        return False
    busy = [n for n in manager.session_names() if ws.busy(n) is not None]
    if ws.runs or busy:
        _write(root, dict(d, state="refused", why=BUSY, t=time.time()))
        return False
    ws.drain()
    ws.save()
    task, ws.task = ws.task, None                         # the sync loop ends: owner.json is released
    if task is not None:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    apps, sessions = [], []
    for name in manager.session_names():
        apps.append(manager.get_app(name))                # kept alive until the asker has it
        info = manager.release(name)
        if info is not None:
            sessions.append(info)
    _write(root, dict(d, state="released", sessions=sessions, t=time.time()))
    end = time.time() + TAKEN_S
    while time.time() < end:
        await asyncio.sleep(0.1)
        now = _read(root)
        if now is not None and now.get("id") == d.get("id") and now.get("state") == "taken":
            break
        if not wb._pid_alive(int(d["to"])):
            break
    del apps
    return True
