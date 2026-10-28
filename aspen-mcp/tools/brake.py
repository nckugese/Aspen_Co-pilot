"""The workbench's brakes on the AI (AI mode, pause, confirmation cards):
their state and rules. Nothing here waits, touches COM or imports the server.

    b = Brake(store=state.get("brake"), save=ws.save, live=ws.brake_live, client="claude-code")
    n = b.need(spec, name, kw, group)          # Need: what = pass | observe | pause | card
    card, how = b.card(name, kw, session=..., hold=...)       # how: new | waiting | timeout
    b.on_event({"type": "brake_card", "card": 12, "decision": "apply"})
    state["brake"] = b.view()                  # fixed size (VIEW_MAX), what the window draws

Modes (one for the whole workbench): ``observe`` refuses every changing call, ``risk`` (the
default) asks before the risky ones, ``auto`` lets all through. Pausing holds changing calls;
a card is a risky call waiting for the user. The brakes act only while this server owns the
live window (``live``); otherwise a call passes as in auto and ``Need.fallback`` says so.
A card the user has seen is only ever applied by the user: no timeout,
mode switch or closed window applies it (``decide`` is the one way to "applying").

The waiting itself (a Future on the event loop, the budget shared with the session-writer wait) is the caller's:
it registers ``wait_on(card id | "pause", fn)`` and ``fn(result)`` is called on the loop
thread when the user decides -- "apply", "decline", "late" (approved, to run after the
answer), "resume", "expired", "window_closed".

Stdlib only; importing it does no I/O.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

MODES = ("observe", "risk", "auto")
DEFAULT_MODE = "risk"
CARD_TTL_S = 1800.0                     # a card expires, and a decided one leaves the list, after this
CARDS_MAX = 20
HELD_MAX = 5                            # held calls shown per pause (the rest counted)
VIEW_MAX = 24 * 1024                    # bytes of view() as state.json holds it
ARGS_MAX = 600                          # bytes of a card's args in the view (the target says the rest)
TEXT_MAX = 300
STUCK = {"runs": 3, "field": 4, "revert": 2}
STUCK_RANGE = {"runs": (2, 10), "field": (3, 20), "revert": (1, 10)}
PENDING = ("waiting", "timeout", "cancelled")           # the user can still decide
OPEN = PENDING + ("applying",)
_NEXT = {"waiting": {"timeout", "cancelled", "applying", "declined", "expired"},
         "timeout": {"applying", "declined", "expired"}, "cancelled": {"applying", "declined", "expired"},
         "applying": {"applied", "failed", "expired", "timeout"}}      # timeout: not run after all (busy)
CLASS = {"remove_block": "remove", "remove_stream": "remove", "remove_component": "remove",
         "remove_side_duty": "remove", "remove_reaction_set": "remove", "remove_reaction": "remove",
         "remove_element": "remove", "remove_row": "remove", "reinit_simulation": "reinit",
         "close_aspen_plus": "close", "create_new_simulation": "file", "save_simulation": "file",
         "workbench_run": "program"}
_CHANGE_KINDS = ("value", "structure", "run", "batch")

# ---------------------------------------------------------------------------- how long to hold
# Measured defaults: seconds each client waits for one tool call with its default settings, by
# clientInfo.name; None = no limit found. Measured on Claude Code 2.1.282 (answered a 200 s
# call) and Codex 0.146.0 (answered a 200 s call, gave up on a 320 s one at 300 s).
CLIENT_TIMEOUT = {"claude-code": None, "codex-mcp-client": 300.0}
HOLD_MIN, HOLD_MAX, HOLD_UNKNOWN, HOLD_MARGIN = 10.0, 40.0, 25.0, 20.0


def clock() -> float:
    """The brakes' time: the wall clock to the millisecond, as the journal rounds its records'
    ``t`` (journal.entry). A pause's ``since`` is sorted among journal times (the brief puts a
    pause's line at its start): unrounded, a pause begun in the millisecond of the record before
    it could sort ahead of that record, e.g. of the mode switch just before it."""
    return round(time.time(), 3)


def enabled() -> bool:
    """ASPEN_MCP_BRAKE=0: every call passes (the switch)."""
    return os.environ.get("ASPEN_MCP_BRAKE", "1").strip() != "0"


def hold_s(client: str | None = None) -> float:
    """The most a call is held (card, pause and the session-writer wait together): clamp(timeout - 20,
    10, 40); 40 for a client with no limit, 25 for one not measured. ASPEN_MCP_HOLD_S wins."""
    try:
        env = float(os.environ.get("ASPEN_MCP_HOLD_S") or 0)
    except ValueError:
        env = 0
    if env > 0:
        return env
    if client not in CLIENT_TIMEOUT:
        return HOLD_UNKNOWN
    t = CLIENT_TIMEOUT[client]
    return HOLD_MAX if t is None else max(HOLD_MIN, min(HOLD_MAX, t - HOLD_MARGIN))


def safe_s(client: str | None = None) -> float:
    """Past this many seconds since the call came in, nothing is applied inside it any more
    (a late apply instead): min(timeout - 10, hold + 15), a timeout taken as hold + 20 when
    unknown or overridden."""
    h = hold_s(client)
    t = CLIENT_TIMEOUT.get(client) if client in CLIENT_TIMEOUT and not os.environ.get("ASPEN_MCP_HOLD_S") else h + 20
    return h + 15 if t is None else min(t - 10, h + 15)


def changes(spec) -> bool:
    """The call may change a model (Spec.changes): observe and pause govern it."""
    risk = getattr(spec, "risk", None)
    return spec.kind in _CHANGE_KINDS or bool(spec.writer) or risk not in (None, False)


def reading(spec, kw) -> bool:
    return spec.kind == "read" or (spec.dry is not None and bool((kw or {}).get(spec.dry)))


@dataclass(frozen=True)
class Need:
    """``need``'s verdict. what: pass | observe (refuse) | pause (hold) | card (ask); cls: the
    card class of a risky call; allowed "group": the user let this class through for the
    group; fallback "no_window": not live, ``would`` is what it would have been; cond: the
    conditional risk's detail (save_other, program)."""
    what: str
    mode: str
    cls: str | None = None
    allowed: str | None = None
    fallback: str | None = None
    would: str | None = None
    cond: object = None


class Brake:
    """Mode, pause, cards. ``store``: state.json's "brake" as last saved (a restart: cards still
    open expire, their calls are gone); ``save()``: after every change (the workspace writes
    view()); ``live()``: this server owns the open window; ``cond(risk, name, kw)``: the
    conditional risks' predicate (brake_effects), falsy = not risky; ``client``: clientInfo.name."""

    def __init__(self, store=None, save=None, live=None, now=None, cond=None, client=None):
        self._save, self._live, self.now, self.cond, self.client = save, live, now or clock, cond, client
        self.mode, self.seq, self.paused, self.cards, self.held = DEFAULT_MODE, 0, None, [], []
        self.stuck = {**STUCK, "on": {k: True for k in STUCK}}
        self.refused, self.last, self.allow, self._waiters = {"n": 0, "since": None}, None, {}, {}
        if isinstance(store, dict):
            self._load(store)

    def _load(self, s) -> None:
        self.mode = s.get("mode") if s.get("mode") in MODES else DEFAULT_MODE
        self.seq = int(s.get("seq") or 0)
        p = s.get("paused")
        if isinstance(p, dict) and p.get("since"):
            self.paused = {k: p.get(k) for k in ("since", "by", "rule", "detail", "group")} | {"deadline": None}
        self._configure(s.get("stuck") or {})
        if isinstance(s.get("refused"), dict):
            self.refused = {"n": int(s["refused"].get("n") or 0), "since": s["refused"].get("since")}
        self.last = s.get("last") if isinstance(s.get("last"), dict) else None
        for c in s.get("cards") or []:
            if isinstance(c, dict) and isinstance(c.get("id"), int):
                c = {k: v for k, v in c.items() if k != "live"}
                if c.get("status") in OPEN:                       # its call and its Pending are gone
                    c.update(status="expired", why="restart")
                self.cards.append(c)
                self.seq = max(self.seq, c["id"])
        self.cards = self.cards[-CARDS_MAX:]

    def live(self) -> bool:
        try:
            return bool(self._live and self._live())
        except Exception:
            return False

    def _changed(self) -> None:
        if self._save is not None:
            try:
                self._save()
            except Exception:
                pass

    # ------------------------------------------------------------------------ the rule
    def need(self, spec, name, kw, group=None) -> Need:
        """What this call needs before it may run. Reads, dry runs and calls that
        change nothing pass; then observe, then pause, then a card (risk mode, risky call)."""
        if not enabled() or reading(spec, kw) or not changes(spec):
            return Need("pass", self.mode)
        cls, cond = self._risky(spec, name, kw)
        would = ("observe" if self.mode == "observe" else "pause" if self.paused
                 else "card" if self.mode == "risk" and cls else "pass")
        if would == "pass":
            return Need("pass", self.mode, cls=cls, cond=cond)
        if not self.live():
            return Need("pass", self.mode, cls=cls, fallback="no_window", would=would, cond=cond)
        if would == "card" and cls in self.allow.get(_gid(group), ()):
            return Need("pass", self.mode, cls=cls, allowed="group", cond=cond)
        return Need(would, self.mode, cls=cls, cond=cond)

    def _risky(self, spec, name, kw):
        risk = getattr(spec, "risk", None)
        if risk in (None, False):
            return None, None
        if risk is True:
            return CLASS.get(name, "other"), None
        try:
            detail = self.cond(risk, name, kw) if self.cond is not None else None
        except Exception:
            detail = None
        return (CLASS.get(name, "other"), detail) if detail else (None, None)

    # ------------------------------------------------------------------------ mode, pause
    def set_mode(self, mode) -> dict:
        if mode not in MODES:
            return {"ok": False, "what": "mode", "error": f"unknown mode {mode!r}"}
        if mode == self.mode:
            return {"ok": True, "what": "mode", "records": []}
        self.mode, self.refused = mode, {"n": 0, "since": self.now() if mode == "observe" else None}
        self._changed()                      # cards keep waiting: only the user decides them
        return {"ok": True, "what": "mode", "records": [{"op": "brake", "what": "mode", "mode": mode, "by": "user"}]}

    def note_refused(self) -> None:
        """An observe refusal (the window's "n changes refused")."""
        self.refused["n"] += 1
        self.refused["since"] = self.refused["since"] or self.now()
        self._changed()

    def pause(self, by="user", rule=None, detail=None, group=None) -> dict | None:
        """Pause the AI (``by`` user | stuck); its record, or None when already paused."""
        if self.paused:
            return None
        self.paused = {"since": self.now(), "by": by, "rule": rule, "detail": _small(detail),
                       "group": _gid(group), "deadline": None}
        self._changed()
        return {"op": "brake", "what": "pause" if by == "user" else "stuck", "by": by, "rule": rule,
                "detail": self.paused["detail"]}

    def resume(self, by="user", mute=None, note=None, wake="resume") -> dict | None:
        """End the pause: every held call wakes (``wake``: "resume" -- its caller judges it
        again -- or "window_closed": not applied)."""
        p = self.paused
        if not p:
            return None
        self.paused = None
        self.last = {"what": "resume", "t": self.now(), "since": p["since"], "by": by, "changes": None}
        self._wake("pause", wake)
        self._changed()
        return {"op": "brake", "what": "resume", "by": by, "since": p["since"], "rule": p.get("rule"),
                "mute": mute, "group": p.get("group"), "note": note}

    def pause_deadline(self, hold: float) -> float | None:
        """One hold per pause: the first held call starts the clock, and every call arriving
        before now + ``hold`` waits until then; past it, callers refuse at once (text
        "paused_past"). None when not paused."""
        if not self.paused:
            return None
        if self.paused.get("deadline") is None:
            self.paused["deadline"] = self.now() + float(hold)
            self._changed()
        return self.paused["deadline"]

    def hold(self, call=None, tool=None, session=None, target=None) -> dict:
        """A call now held (the window's "the AI waits"); ``unhold`` it when its wait ends."""
        e = {"call": call, "tool": tool, "session": session, "target": target, "since": self.now()}
        self.held.append(e)
        self._changed()
        return e

    def unhold(self, e) -> None:
        if e in self.held:
            self.held.remove(e)
            self._changed()

    # ------------------------------------------------------------------------ waiters
    def wait_on(self, key, fn):
        """Call ``fn(result)`` when ``key`` (a card id, or "pause") is decided; a token for unwait."""
        self._waiters.setdefault(key, []).append(fn)
        return key, fn

    def unwait(self, token) -> None:
        key, fn = token
        fns = self._waiters.get(key) or []
        if fn in fns:
            fns.remove(fn)
        if not fns:
            self._waiters.pop(key, None)

    def waiting(self, key) -> bool:
        return bool(self._waiters.get(key))

    def _wake(self, key, result) -> None:
        """Every waiter of ``key`` gets ``result`` -- but an approval runs once: the first call
        waiting on a card gets "apply" / "late", the same action's later calls "joined"."""
        for i, fn in enumerate(self._waiters.pop(key, [])):
            try:
                fn("joined" if i and result in ("apply", "late") else result)
            except Exception:
                pass

    # ------------------------------------------------------------------------ cards
    def card(self, name, kw=None, *, session=None, model=None, group=None, call=None, target=None, args=None,
             cls=None, risky=None, more=0, effects=None, cp=None, reason=None, hold=None) -> tuple[dict, str]:
        """(card, how) for a risky call. how "new"; "waiting": the same action (session, tool,
        args) already waits -- wait on that card too; "timeout": its wait is over (text
        "card_dup", no new card)."""
        self.tick()
        args = args if args is not None else _compact(kw)
        key = _key(name, session, args)
        for c in reversed(self.cards):
            if c["status"] in PENDING and _key(c["tool"], c.get("session"), c.get("args")) == key:
                return c, "waiting" if c["status"] == "waiting" else "timeout"
        before = next((c for c in reversed(self.cards) if c["status"] == "declined"
                       and _key(c["tool"], c.get("session"), c.get("args")) == key), None)
        now = self.now()
        self.seq += 1
        c = {"id": self.seq, "t": now, "call": call, "tool": name, "session": session, "model": model,
             "group": _gid(group), "group_title": _cut(group.get("title"), 80) if isinstance(group, dict) else None,
             "reason": _cut(reason, TEXT_MAX), "target": _said(name, target, args, risky), "args": args,
             "risky": list(risky or [])[:8],
             "more": int(more or 0), "effects": list(effects or [])[:8], "cp": cp,
             "class": cls or CLASS.get(name, "other"), "status": "waiting",
             "until": now + hold if hold else None, "decided": None, "result": None, "since_changes": 0,
             "declined_before": before and {"id": before["id"], "t": (before.get("decided") or {}).get("t"),
                                            "comment": (before.get("decided") or {}).get("comment")}}
        self.cards.append(c)
        self._prune()
        self._changed()
        return c, "new"

    def get(self, cid) -> dict | None:
        return next((c for c in self.cards if c["id"] == cid), None)

    def settle(self, cid, status, **fields) -> dict | None:
        """Move a card on (timeout, cancelled, applying, applied, failed, expired) if that is a
        step its status allows -- timeout / cancelled only once no call waits on it (unwait
        first); an expired card's waiting calls wake ("expired")."""
        c = self.get(cid)
        if c is None or status not in _NEXT.get(c["status"], ()):
            return None
        if status in ("timeout", "cancelled") and self.waiting(cid):
            return c                          # another call of the same action still waits on it
        c["status"] = status
        c.update({k: v for k, v in fields.items() if v is not None})
        if status == "expired":
            self._wake(cid, "expired")
        self._changed()
        return c

    def done(self, cid, ok: bool, text=None) -> dict | None:
        """The applied call ended: applied / failed, the first TEXT_MAX characters of its answer."""
        return self.settle(cid, "applied" if ok else "failed", result={"ok": bool(ok), "text": _cut(text, TEXT_MAX)})

    def late(self, cid) -> None:
        """Approved, but applied after the AI's answer (not enough time left in its call)."""
        c = self.get(cid)
        if c is not None and c.get("decided"):
            c["decided"]["how"] = "late"
            self._changed()

    def decide(self, cid, decision, comment=None, allow_group=False, slow_cp=False, req=None) -> dict:
        """The user's apply / decline. A card whose call still waits is decided live (its call
        wakes "apply" -- "late" with slow_cp -- or "decline"); otherwise late: an apply is for
        the caller to queue, a decline comes with its ``proposal`` record."""
        c = self.get(cid)
        if c is None or decision not in ("apply", "decline"):
            return {"ok": False, "what": "card", "card": c, "error": "unknown card" if c is None else "bad decision"}
        if c["status"] not in PENDING:
            return {"ok": False, "what": "card", "card": c, "error": c["status"]}
        live = c["status"] == "waiting" and self.waiting(cid)
        how = "live" if live and not (decision == "apply" and slow_cp) else "late"
        c["decided"] = {"by": "user", "how": how, "t": self.now(), "comment": _cut(comment, TEXT_MAX), "req": req}
        recs = []
        if decision == "decline":
            c["status"] = "declined"
            self._wake(cid, "decline")
            if not live:
                recs.append({"op": "proposal", "status": "declined", "card": cid, "tool": c["tool"],
                             "target": c.get("target"), "comment": c["decided"]["comment"], "proposed": _proposed(c)})
        else:
            if allow_group and c.get("group"):
                self.allow.setdefault(c["group"], set()).add(c["class"])
                while len(self.allow) > 16:
                    self.allow.pop(next(iter(self.allow)))
            c["status"] = "applying"
            self._wake(cid, "apply" if how == "live" else "late")
        self._changed()
        return {"ok": True, "what": "card", "card": c, "decision": decision, "late": how == "late",
                "slow_cp": bool(slow_cp), "records": recs}

    def dismiss(self, cid) -> dict:
        c = self.get(cid)
        if c is None or c["status"] in OPEN:
            return {"ok": False, "what": "dismiss", "error": "unknown card" if c is None else c["status"]}
        self.cards.remove(c)
        self._changed()
        return {"ok": True, "what": "dismiss", "records": []}

    def expire(self, pred, why) -> list:
        """Expire the open cards ``pred(card)`` picks (a session closed, another model under its
        name): their waiting calls wake "expired"."""
        out = [c for c in self.cards if c["status"] in OPEN and pred(c)]
        for c in out:
            self.settle(c["id"], "expired", why=why)
        return out

    def tick(self) -> None:
        """Cards past CARD_TTL_S: an open one expires, a decided one leaves the list."""
        now, gone = self.now(), False
        for c in list(self.cards):
            t = max(c["t"], (c.get("decided") or {}).get("t") or 0)
            if now - t <= CARD_TTL_S:
                continue
            if c["status"] in OPEN:
                self.settle(c["id"], "expired", why="ttl")
            else:
                self.cards.remove(c)
                gone = True
        if gone:
            self._changed()

    def _prune(self) -> None:
        while len(self.cards) > CARDS_MAX:
            old = next((c for c in self.cards if c["status"] not in OPEN), None)
            if old is None:
                old = self.cards[0]
                old.update(status="expired", why="crowded")
                self._wake(old["id"], "expired")
            self.cards.remove(old)

    def closed(self) -> list:
        """The window closed: calls held for a card wake "window_closed" (the card stays, timed
        out: it may be applied from a window opened later), the pause ends. Records."""
        for c in self.cards:
            if c["status"] == "waiting":
                c.update(status="timeout", closed=True)
                self._wake(c["id"], "window_closed")
        rec = self.resume(by="window_closed", wake="window_closed")
        self._changed()
        return [rec] if rec else []

    # ------------------------------------------------------------------------ the window
    def on_event(self, ev) -> dict | None:
        """A brake_* event of the window; None for any other. The result: ok, what, records
        (journal fields, ``op`` first, for every open model -- a proposal's for its card's),
        and for a card: card, decision, late (the caller queues a late apply)."""
        t = (ev or {}).get("type")
        if t == "brake_mode":
            return self.set_mode(ev.get("mode"))
        if t == "brake_pause":
            rec = self.pause("user")
            return {"ok": rec is not None, "what": "pause", "records": [rec] if rec else []}
        if t == "brake_resume":
            rec = self.resume("user", mute=ev.get("mute"), note=_cut(ev.get("note"), TEXT_MAX))
            return {"ok": rec is not None, "what": "resume", "records": [rec] if rec else [],
                    "mute": ev.get("mute"), "note": rec and rec["note"]}
        if t == "brake_card":
            return self.decide(ev.get("card"), ev.get("decision"), ev.get("comment"), bool(ev.get("allow_group")),
                               bool(ev.get("slow_cp")), ev.get("req"))
        if t == "brake_dismiss":
            return self.dismiss(ev.get("card"))
        if t == "brake_stuck":
            self._configure(ev)
            self._changed()
            return {"ok": True, "what": "stuck", "stuck": dict(self.stuck), "records": []}
        return None

    def _configure(self, ev) -> None:
        for k, (lo, hi) in STUCK_RANGE.items():
            try:
                self.stuck[k] = max(lo, min(hi, int(ev[k])))
            except (KeyError, TypeError, ValueError):
                pass
        on = ev.get("on")
        if isinstance(on, dict):
            self.stuck["on"] = {k: bool(on.get(k, self.stuck["on"][k])) for k in STUCK}

    def view(self) -> dict:
        """state.json's "brake": at most CARDS_MAX cards, HELD_MAX held, VIEW_MAX bytes."""
        p = None
        if self.paused:
            p = {k: self.paused.get(k) for k in ("since", "by", "rule", "detail", "group", "deadline")}
            p.update(held=[dict(e, target=_small(e.get("target"))) for e in self.held[:HELD_MAX]],
                     more=max(0, len(self.held) - HELD_MAX))
        v = {"v": 1, "mode": self.mode, "seq": self.seq, "live": self.live(), "hold_s": hold_s(self.client),
             "client": self.client, "paused": p, "cards": [self._card_view(c) for c in self.cards[-CARDS_MAX:]],
             "stuck": {**{k: self.stuck[k] for k in STUCK}, "on": dict(self.stuck["on"])},
             "refused": dict(self.refused), "last": self.last}
        while _size(v) > VIEW_MAX:
            old = next((c for c in v["cards"] if c["status"] not in OPEN), None)
            if old is not None:
                v["cards"].remove(old)
            elif any(c.get("args") for c in v["cards"]):
                for c in v["cards"]:
                    c["args"] = None
            elif v["cards"]:
                v["cards"] = v["cards"][1:]
            else:
                break
        return v

    def _card_view(self, c) -> dict:
        out = dict(c, live=self.waiting(c["id"]), args=_small(c.get("args"), ARGS_MAX),
                   target=_small(c.get("target")), risky=[_small(x) for x in c.get("risky") or []],
                   effects=[_small(x) for x in c.get("effects") or []], cp=_small(c.get("cp")))
        return out


# ---------------------------------------------------------------------------- helpers
def _gid(group):
    return group.get("id") if isinstance(group, dict) else group


def _cut(s, n):
    if s is None:
        return None
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _size(v) -> int:
    return len(json.dumps(v, ensure_ascii=False, default=str).encode("utf-8"))


def _small(x, limit=512):
    """x if its JSON is at most ``limit`` bytes, else a marker with its start."""
    if x is None:
        return None
    try:
        text = json.dumps(x, ensure_ascii=False, default=str)
    except Exception:
        return {"trunc": True}
    return x if len(text.encode("utf-8")) <= limit else {"trunc": True, "text": text[:limit // 4]}


def _compact(kw):
    """A call's arguments for a card when the caller gave none: JSON scalars and lists, no ctx."""
    out = {}
    for k, v in (kw or {}).items():
        if v is None or type(v).__module__.startswith("mcp."):
            continue
        try:
            json.dumps(v)
            out[k] = v
        except (TypeError, ValueError):
            out[k] = str(v)
    return _small(out, 1024)


def _key(tool, session, args) -> str:
    return json.dumps([tool, session, args], sort_keys=True, ensure_ascii=False, default=str)


def _proposed(c) -> dict:
    return {"by": "ai", "card": c["id"], "call": c.get("call"), "group": c.get("group"), "t": c["t"]}


_OBJ = ("block", "stream", "component", "rxnset", "name", "file", "tab")


def _said(tool, target, args, risky):
    """A card's target, with ``say`` -- the words ``what`` names it by -- when it names no object:
    remove_element / remove_row give only their folder or table path ("\\Data\\Streams"). The
    words are the card's first risky item's (tools/brake_effects: "stream HOT", "Components ›
    Specifications › Type, row 0 (WATER)"), else the element's name / the row's number from the
    call's arguments. Anything else: the target as given."""
    t = target if isinstance(target, dict) else {}
    if tool not in ("remove_element", "remove_row") or t.get("say") or any(t.get(k) for k in _OBJ):
        return target
    r = risky[0] if isinstance(risky, (list, tuple)) and risky and isinstance(risky[0], dict) else {}
    a = args if isinstance(args, dict) else {}
    say = r.get("say")
    if not say and tool == "remove_element" and a.get("name"):
        say = str(a["name"]).split("!", 1)[0]
    elif not say and tool == "remove_row" and a.get("index") is not None:
        say = f"{t.get('field') or 'table'}, row {a['index']}"
    return dict(t, say=_cut(say, 160)) if say else target


# ---------------------------------------------------------------------------- what the AI reads
# Each text says on its own what to do next: the server instructions only say "Not applied"
# means nothing changed and must not be retried.
TEXTS = {
    "observe": ("Not applied: the workbench is in read-only (Observe) mode, so you may read but not change the "
                "model. Propose the change instead: workbench_edit(session_name, proposal={{\"title\": ..., \"reason\": ...}}, "
                "program=[...]) with a \"why\" on each statement opens it as a proposal in the model's tab. The user "
                "reviews it and runs it if they agree; you may only check it (workbench_run dry_run=True)."),
    "paused": ("Not applied: the user paused the AI in the workbench at {at}. Nothing was changed. Stop making "
               "changes: end your turn and tell the user you are waiting for them to resume. Reads still work."),
    "paused_past": ("Not applied: still paused by the user (since {at}). End your turn; the user resumes you from "
                    "the workbench."),
    "stuck": ("Not applied: the workbench paused you automatically because {rule}. Diagnose before changing more "
              "(aspen-error-troubleshooting); the user resumes you from the workbench."),
    "stuck_past": ("Not applied: still paused automatically (since {at}) because {rule}. End your turn; the user "
                   "resumes you from the workbench."),
    "resumed_changed": ("Not applied: while you were paused the model was changed (below). Re-check it and call "
                        "again if the change still makes sense."),
    "resumed": "(Held {s} s while the user had paused you; resumed.)",
    "resumed_late": ("Not applied: the user resumed you, but too late to apply this call inside it (held {s} s). "
                     "Nothing was changed; call it again if it still makes sense."),
    "confirmed": "(Confirmed by the user in the workbench, card #{id}.)",
    "approved_later": ("Not applied yet #{id}: the user approved {what}; the server applies it right after this "
                       "answer{cp}. A later result will confirm it."),
    "declined": ("Not applied #{id}: the user declined {what}. Their note: \"{comment}\". Do not retry it; take the "
                 "note into account."),
    "declined_bare": "Not applied #{id}: the user declined {what}. Do not retry it.",
    "card_timeout": ("Not applied #{id}: {what} is waiting for the user's confirmation in the workbench. The card "
                     "stays open; the user may still apply it, and a later result will say so. Do not call it "
                     "again: continue with other work, or end your turn and say what you are waiting for."),
    "card_dup": ("Not applied #{id}: still waiting for the user's confirmation (card open since {at}). Do not call "
                 "it again."),
    "card_closed": ("Not applied #{id}: the workbench window closed before the user decided. Nothing was changed; "
                    "ask the user."),
    "card_expired": ("Not applied #{id}: the confirmation card expired before the user decided. Nothing was "
                     "changed; propose it again if it is still needed."),
    "card_joined": ("Not applied #{id}: this repeated the call that waited on the same card; that one is the one "
                    "applied on the user's confirmation. Do not call it again."),
    "stuck_note": "(The workbench has paused you: {rule}. Your next change will wait for the user.)",
    "stuck_nowindow": "(Note: {rule}. Diagnose before changing more.)",
}


def text(key, **kw) -> str:
    return TEXTS[key].format(**kw)


def at(t) -> str:
    """A clock time for the AI: 14:02."""
    return time.strftime("%H:%M", time.localtime(t)) if t else "?"


def what(tool, target=None, session=None) -> str:
    """remove_block B4 / remove_element stream HOT / close_aspen_plus 'demo' / close_aspen_plus
    (every open model). ``say``: the target in words (``_said``), before any path."""
    t = target or {}
    for k in ("say",) + _OBJ + ("path",):
        if t.get(k):
            return f"{tool} {t[k]}"
    if session:
        return f"{tool} '{session}'"
    return f"{tool} (every open model)" if tool == "close_aspen_plus" else tool


def rule_text(rule, detail=None) -> str:
    """Why the stuck detector paused the AI: "3 simulation runs in a row failed (last: ESTCOL, COLUMN DRIES UP)"."""
    d = detail if isinstance(detail, dict) else {}
    n = d.get("n", STUCK.get(rule, "several"))
    if rule == "runs":
        last = d.get("last") if isinstance(d.get("last"), dict) else {}
        bits = [str(x) for x in (last.get("block"), last.get("msg")) if x]
        return f"{n} simulation runs in a row failed" + (f" (last: {', '.join(bits)})" if bits else "")
    if rule == "field":
        return f"{d.get('field') or d.get('path') or 'one field'} was changed {n} times in this request with no converged run between"
    if rule == "revert":
        return f"you undid your own changes {n} times in this request"
    return str(rule or "the workbench saw you repeat failing changes")


def paused_text(paused, past=False) -> str:
    """The answer to a call the pause kept out (its wait over, or ``past`` the pause's deadline)."""
    p = paused or {}
    if p.get("by") == "stuck":
        return text("stuck_past" if past else "stuck", at=at(p.get("since")), rule=rule_text(p.get("rule"), p.get("detail")))
    return text("paused_past" if past else "paused", at=at(p.get("since")))


def card_text(result, card, *, cp_s=None) -> str:
    """The answer to a call whose card ended its wait with ``result`` (decline, late, timeout,
    window_closed, expired, dup, joined); an applied one gets text("confirmed") appended instead."""
    c = card or {}
    w = what(c.get("tool"), c.get("target"), c.get("session"))
    if result == "decline":
        comment = (c.get("decided") or {}).get("comment")
        return text("declined", id=c.get("id"), what=w, comment=comment) if comment else \
            text("declined_bare", id=c.get("id"), what=w)
    if result == "late":
        cp = f" (a restore point first, about {max(1, round(cp_s))} s)" if cp_s else ""
        return text("approved_later", id=c.get("id"), what=w, cp=cp)
    if result == "window_closed":
        return text("card_closed", id=c.get("id"))
    if result == "expired":
        return text("card_expired", id=c.get("id"))
    if result == "dup":
        return text("card_dup", id=c.get("id"), at=at(c.get("t")))
    if result == "joined":
        return text("card_joined", id=c.get("id"))
    return text("card_timeout", id=c.get("id"), what=w)
