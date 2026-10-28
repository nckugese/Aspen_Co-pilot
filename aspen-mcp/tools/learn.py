"""Learning mode: on by default; while it is on, every change
the AI makes needs a ``reason`` that explains the process principle behind it.

    v = learn.check(reason, "set_value", key)      # tools/intercept.py, before the brakes and COM
    v.refuse / v.text / v.fields / v.note          # None: nothing to say (off, or a good reason)
    learn.switch(True, by="user")                  # the window's learn_mode event
    state["learn"] = learn.view()                  # what the window draws

The flag lives in its own file, ``~/.aspen-mcp/workbench/learn.json`` --
``{"v": 1, "on": true, "since": <t>, "by": "user", "weak"?: "refuse" | "remind"}`` -- not in
state.json: both registrations of this server enforce it and only the one serving the
window has a workspace; it holds with the window closed too. No file, or a file without
``on``, means on: only the user's own switch (``on: false``, written by ``switch``) turns it off,
and that choice is kept across windows, server restarts and sessions. ``state()`` costs at most one
``os.stat`` each STAT_S and re-reads the file only when it changed.

The check has no judge: a missing reason is always refused; a weak one -- too
short (fewer than 8 words, or 12 CJK characters, counted together), no cause-and-effect word,
or only "as the user asked" -- is refused once per (tool, target) within GRACE_S, and a weak
one after that is applied, its records marked ``reason_weak``. So the AI is never caught in a
refusal loop. ``weak`` "remind" (the file's key, or env ASPEN_MCP_LEARN_WEAK, which wins)
relaxes that to a reminder at the end of the answer: the switch for when the refusals cost
more retries than they teach. ASPEN_MCP_LEARN=0: nothing is enforced
(the flag is still kept; ``view()["enforced"]`` false).

The AI hears of a switch in the next result's brief (``news`` / ``told``, tools/brief.py); the
server instructions' ``reason`` rule says that learning mode wants the process principle.

Stdlib only; importing it does no I/O; nothing here raises into a tool.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path.home() / ".aspen-mcp" / "workbench"
FILE = "learn.json"
GRACE_S = 120.0                  # a weak reason is refused once per (tool, target) in this long
GRACE_MAX = 256                  # (tool, target) keys remembered
WORDS_MIN = 8                    # words (numbers count) ...
CJK_MIN = 12                     # ... or CJK characters: a reason shorter than both is weak
WEAK_MODES = ("refuse", "remind")
NEWS_ON = ("[workbench] Learning mode is on: changes need a `reason` that explains the process principle; "
           "plain descriptions are refused.")
NEWS_REMIND = ("[workbench] Learning mode is on: changes need a `reason` that explains the process principle; "
               "plain descriptions get a reminder.")
NEWS_OFF = "[workbench] Learning mode is off: `reason` is optional again."
MISSING = ("Not applied: the workbench is in learning mode, where every change needs a `reason` that explains "
           "the process principle behind it -- what physically happens and why it moves the model toward the "
           "goal (e.g. \"A higher reflux ratio returns more liquid to the top stages, washing the heavy component "
           "down, so the distillate purity rises; the reboiler duty rises with it\"), written in the user's "
           "language (e.g. \"提高回流比使更多液體回到塔頂，把重成分洗下，因此塔頂純度提高、再沸器熱負荷也增加\"). "
           "Call {tool} again with that reason.")
WEAK = ("Not applied (learning mode): {what}. The reason should give the cause and its effect in the process, "
        "not only what is set. Add the physical mechanism and resend; a second attempt is accepted as written.")
REMIND = ("Learning mode: {what} -- next time give the cause and its effect in the process, not only what is "
          "set (the user reads the reason beside this change).")
WHAT = {"boiler": "the reason only says it was asked for",
        "short": "the reason is too short ({n}) to explain the process",
        "causal": "the reason names no cause and effect (because, so, which, raises, lowers, leads to ...; "
                  "in Chinese 因為、所以、導致、使、提高、降低 ... -- keep writing in the user's language)"}

now = time.monotonic             # the grace clock; kept as a module attribute so it can be overridden
_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]")
_WORD = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:[.,]\d+)?")
_CAUSAL = re.compile(
    r"\b(?:because|since|so|therefore|thus|hence|which|whereby|due to|in order to|so as to|as a result|"
    r"leads? to|leading to|causes|caused by|results? in|raises|lowers|increases|reduces|decreases|drives|"
    r"shifts|means)\b|→|->|=>|因為|因为|所以|使(?!用)|讓|让|導致|导致|造成|為了|为了|以便|提高|降低|增加|"
    r"減少|减少|因此|從而|从而|進而|进而|以免|避免", re.I)
_BOILER = re.compile(
    r"\b(?:as (?:the )?user (?:asked|requested|wanted)|as (?:requested|asked|instructed|agreed)|"
    r"(?:the )?user (?:asked|requested|wants|wanted)(?: (?:for|me to))?(?: it| this| that)?|"
    r"per (?:the )?(?:user'?s? )?(?:request|instructions?)|at the user'?s request|requested by (?:the )?user)\b|"
    r"(?:(?:依照|依|照|按照|按|根據|根据|應|应)(?:使用者|用戶|用户)?|使用者|用戶|用户)的?要求", re.I)

DEFAULT_ON = True                # no file, or no ``on`` in it: on
STAT_S = 0.25                    # the file is looked at (one os.stat) at most this often
_mono = time.monotonic
_lock = threading.Lock()
_cache: dict = {"key": None, "data": None, "at": None}   # the file as last read: (mtime_ns, size), when
_grace: dict = {}                            # (tool, target) -> when its weak reason was refused
_told = {"on": DEFAULT_ON}                   # what this process's AI was told last (a start: the default, as RULE says)


# ---------------------------------------------------------------------------- the flag
def path() -> Path:
    return Path(ROOT) / FILE


def enforced() -> bool:
    """ASPEN_MCP_LEARN=0: the flag is kept but nothing is enforced (the switch)."""
    return os.environ.get("ASPEN_MCP_LEARN", "1").strip().lower() not in ("0", "off", "false", "no")


def state() -> dict:
    """The flag file as {"on", "since", "by", "weak"?} ({"on": DEFAULT_ON} when there is none): at
    most one os.stat each STAT_S (another process's switch is seen that late at most; this
    one's at once), the file read again only when it changed."""
    t = _mono()
    with _lock:
        at = _cache.get("at")
        if _cache["data"] is not None and at is not None and 0 <= t - at < STAT_S:
            return _cache["data"]
    p = path()
    try:
        st = os.stat(p)
    except OSError:
        with _lock:
            _cache.update(key=None, data={"on": DEFAULT_ON}, at=t)
        return {"on": DEFAULT_ON}
    key = (st.st_mtime_ns, st.st_size)
    with _lock:
        if _cache["key"] == key and _cache["data"] is not None:
            _cache["at"] = t
            return _cache["data"]
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        data = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        data = {}
    # the user's own switch holds; a missing or unreadable ``on`` is the default (on)
    flag = data["on"] if isinstance(data.get("on"), bool) else DEFAULT_ON
    data = {"on": flag, "since": data.get("since"), "by": data.get("by"),
            **({"weak": data["weak"]} if data.get("weak") in WEAK_MODES else {})}
    with _lock:
        _cache.update(key=key, data=data, at=t)
    return data


def on() -> bool:
    """Learning mode is on and enforced."""
    return enforced() and state()["on"]


def weak_mode(st: dict | None = None) -> str:
    """"refuse" (the default) or "remind": env ASPEN_MCP_LEARN_WEAK, else the file's ``weak``."""
    env = os.environ.get("ASPEN_MCP_LEARN_WEAK", "").strip().lower()
    if env in WEAK_MODES:
        return env
    w = (state() if st is None else st).get("weak")
    return w if w in WEAK_MODES else "refuse"


def switch(on: bool, by: str = "user", weak: str | None = None) -> dict:
    """Write the flag (``weak``: keep the file's when None). Returns ``view()``; a file that
    cannot be written is logged and the view says what holds."""
    cur = state()
    data = {"v": 1, "on": bool(on), "since": round(time.time(), 3) if bool(on) != cur["on"] else cur.get("since"),
            "by": str(by or "user")[:40]}
    w = weak if weak in WEAK_MODES else cur.get("weak")
    if w in WEAK_MODES:
        data["weak"] = w
    p = path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f"{p.stem}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        for _ in range(20):                          # the other server may be reading it
            try:
                os.replace(tmp, p)
                break
            except PermissionError:
                time.sleep(0.05)
        else:
            tmp.unlink(missing_ok=True)
            logger.warning("learn: could not replace %s", p)
    except OSError:
        logger.warning("learn: could not write %s", p, exc_info=True)
    with _lock:
        _cache["at"] = None                          # looked at again now
    return view()


def view() -> dict:
    """state.json's ``learn``: {"on", "since", "by", "enforced", "weak"}."""
    st = state()
    return {"on": st["on"], "since": st.get("since"), "by": st.get("by"), "enforced": enforced(),
            "weak": weak_mode(st)}


# ---------------------------------------------------------------------------- the brief
def news() -> tuple[str, bool] | None:
    """(the line for the AI, the state it tells) when learning mode was switched since this
    process's AI was last told -- a server starts believing it on (RULE says so) -- else None."""
    try:
        st = state()
        cur = enforced() and st["on"]
        if cur == _told["on"]:
            return None
        if not cur:
            return NEWS_OFF, False
        return (NEWS_REMIND if weak_mode(st) == "remind" else NEWS_ON), True
    except Exception as exc:
        logger.warning("learn: no news (%r)", exc)
        return None


def told(state_on: bool) -> None:
    """The line ``news`` gave reached the AI."""
    _told["on"] = bool(state_on)


# ---------------------------------------------------------------------------- the check
@dataclass(frozen=True)
class Verdict:
    """``refuse``: not applied, ``text`` the answer and ``fields`` its refused record's (learn,
    learn_why); applied: ``fields`` go on the call's records (reason_weak), ``note`` a line at
    the end of its answer (remind mode)."""
    refuse: bool
    text: str | None = None
    fields: dict | None = None
    note: str | None = None


def weakness(reason) -> tuple[str, str] | None:
    """(code, what) of a weak reason -- "boiler", "short", "causal" -- or None: a reason that
    gives enough words and a cause-and-effect word, once "as the user asked" is taken out."""
    text = " ".join(str(reason or "").split())
    rest = _BOILER.sub(" ", text)
    boiler = rest != text
    words, cjk = len(_WORD.findall(rest)), len(_CJK.findall(rest))
    short = words + cjk * WORDS_MIN / CJK_MIN < WORDS_MIN
    causal = _CAUSAL.search(rest) is not None
    if boiler and (short or not causal):
        return "boiler", WHAT["boiler"]
    if short:
        n = f"{cjk} characters" if cjk > words else f"{words} word{'s' * (words != 1)}"
        return "short", WHAT["short"].format(n=n)
    if not causal:
        return "causal", WHAT["causal"]
    return None


def check(reason, tool: str, key=None) -> Verdict | None:
    """Learning mode's verdict on one changing AI call (``key``: its target, the grace's key
    with ``tool``). None: learning mode off (or not enforced), or a good reason."""
    try:
        if not enforced():
            return None
        st = state()
        if not st["on"]:
            return None
        if reason is None or not str(reason).strip():
            return Verdict(True, MISSING.format(tool=tool), {"learn": "missing"})
        weak = weakness(reason)
        if weak is None:
            return None
        code, what = weak
        if weak_mode(st) == "remind":
            return Verdict(False, fields={"reason_weak": True}, note=REMIND.format(what=what))
        k, t = (str(tool), str(key)), now()
        with _lock:
            t0 = _grace.get(k)
            if t0 is not None and t - t0 <= GRACE_S:
                return Verdict(False, fields={"reason_weak": True})
            _grace.pop(k, None)
            _grace[k] = t
            while len(_grace) > GRACE_MAX:
                _grace.pop(next(iter(_grace)))
        return Verdict(True, WEAK.format(what=what), {"learn": "weak", "learn_why": code})
    except Exception as exc:
        logger.warning("learn: %s not checked (%r)", tool, exc)
        return None


def reset() -> None:
    """Forget the grace, the cache and what was told, as a fresh server process would."""
    with _lock:
        _grace.clear()
        _cache.update(key=None, data=None, at=None)
    _told["on"] = DEFAULT_ON
