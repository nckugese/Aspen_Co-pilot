"""What others changed in a model since the AI's last call, told at the top of its next
result.

    tools/intercept.py _call:  pending = brief.Pending(...); ... the tool ...; brief.deliver(pending, res)
    workbench_read:            its "brief" key is brief.take(): the same lines, not prefixed again

Others are everyone but this server's AI: the user (a value typed in the inspector, the
window's Run, an applied point, a restore, an undo or redo -- one line each: "user (window)
undid 2 changes: <field> 40 → 25; ...", "redid ..."), a program the user started (one line:
what it did, what it left changed), another AI session (AI records another server process wrote since this one
started) and edits made in Aspen's own window (actor ``external``, found by
comparing before the AI's call -- tools/external.py -- so this very call's brief has them: "user
(Aspen window, detected) set ...", "user (Aspen window) ran the simulation: ..."; only told,
never paused). The AI's own records are never told back: actor ``ai`` or
via ``mcp`` from this process, and a program it started with workbench_run (its group's
``ai_group``). A long call another process began and never ended (a server killed during an
optimize, the AI's own predecessor's included) is told as "started, no end recorded".

Per model a cursor: the newest record already told and ``journal.others()`` then. A call
checks that count -- one stat while the journal's summary is cached -- and reads the journal
only when it moved. The cursor starts at the model's last AI record, so what the user did
before a server restart is told once, or at this process's start when there is none. It
moves only once the lines are attached: a tool that raised gets none, and the next call
tells them. At most LINES lines, the first a header marked [workbench], each at most WIDTH
characters, English, a field as its label plus its path (the AI writes back by path); a
JSON-object result gets them under "workbench_brief" instead. The journal off: nothing.

The brakes (tools/brake.py): what the user did to this AI in the workbench is told too
-- the records this process wrote (another server's are about its own AI): "14:02–14:05 user
paused you; meanwhile:" (the changes follow), a pause still on, an automatic one no answer
told of (``told_in``: the call whose answer did), a mode switch, "user declined your proposal
#13 (remove_stream S5): "keep it"" (a late decline), "user applied your proposal #12: removed
block B4 (Heater)" (a card applied after the AI's call ended: its records carry ``proposed``).
The AI's proposals as block programs: the user's run of one is their approval --
one line from its change group, whose header carries ``proposal`` and, once it ended, ``outcome``:
"user approved and ran your proposal 'Warmer feed': applied 3 steps (2 sets, 1 run); left ..." (a
step that failed, a stop, the user's edits before it) -- and sending one back is a milestone (op
proposal, status rejected): "user rejected your proposal 'Warmer feed' (tab t1): "make it 90 C"".
``collect(since=)`` is what others changed after a time, whatever was told already -- model
changes only: tools/intercept.py asks it whether a call held by a pause may still apply.

Diagnosis: the newest failed or refused run of someone else's gets a second line, its
diagnosis in short (tools/diagnose.say: where it failed, the failure kind in our words, what
changed since the last good run) -- "why: run #9 failed at COL1 (RadFrac): The column's
material balance cannot close [not_in_mass_balance]; changed since the last good run: ...".

Learning mode: switched on or off since this process's AI was last told is the
brief's first line, "[workbench] Learning mode is on: ..." (tools/learn.news) -- also with the
journal off.

Pure stdlib, no COM; nothing here raises into a tool.
"""
from __future__ import annotations

import contextvars
import json
import logging
import threading
import time

from tools import aspen_labels, brake, diagnose, journal, learn

logger = logging.getLogger(__name__)

LINES = 8                  # the whole brief, header included
WIDTH = 200                # characters of a line
READ = 200                 # records read when others have written
KEY = "workbench_brief"    # where a JSON-object result carries it
START = time.time()        # this process's start: the cursor of a model with no AI record
OTHER_AI = "another AI session"
EXTERNAL = "user (Aspen window, detected)"      # an edit made in Aspen's own window
EXTERNAL_RUN = "user (Aspen window)"             # a run made there
BRAKE_OPS = ("brake", "proposal")                # the brakes' milestones, late declines: never a change
NOT_DONE = frozenset({"failed", "error", "refused", "unchanged"})
MODES = {"observe": "Observe: your changes are refused; propose them with workbench_edit(proposal=...)",
         "risk": "Confirm risky: deletions, reinitialize, closing and overwriting files wait for the user's "
                 "confirmation",
         "auto": "Auto: your changes apply directly"}
RULES = {"runs": "simulation runs kept failing", "field": "one field kept changing with no converged run",
         "revert": "you kept undoing your own changes"}

_marks: dict = {}          # model -> {"key": (t, id), "others": int | None}
_said: dict = {}           # the brake milestones told (their keys: one per event, the same in every model)
SAID_MAX = 64
_lock = threading.Lock()
CURRENT: contextvars.ContextVar = contextvars.ContextVar("aspen_mcp_brief", default=None)


class Pending:
    """One AI call's brief, collected when first asked for (take, or deliver at the end).
    ``session``: the call's session, None for all open ones; ``types(session)``: {block: type}.
    ``learn``: the learning-mode state its first line tells (tools/learn.news), None: none."""
    __slots__ = ("get_manager", "session", "types", "lines", "marks", "taken", "learn")

    def __init__(self, get_manager, session=None, types=None):
        self.get_manager, self.session, self.types = get_manager, session, types
        self.lines, self.marks, self.taken, self.learn = None, {}, False, None

    def make(self) -> list:
        if self.lines is None:
            self.lines, self.marks = collect(self.get_manager(), self.session, self.types)
            said = learn.news()
            if said is not None:
                self.lines, self.learn = [said[0]] + self.lines, said[1]
        return self.lines


def take() -> list:
    """The current call's lines for a tool that shows them itself (workbench_read); deliver
    then attaches nothing more. [] outside a call or with nothing new."""
    p = CURRENT.get()
    if p is None:
        return []
    try:
        lines = p.make()
        p.taken = True
        return lines
    except Exception as exc:
        logger.warning("brief: not collected (%r)", exc)
        return []


def deliver(p: Pending | None, res):
    """The call ended well: its result with the lines attached (unless taken), and the
    cursors moved past what they tell. A result they cannot go on keeps the cursors."""
    if p is None:
        return res
    try:
        lines = p.make()
        done = True
        if lines and not p.taken:
            res, done = attach(res, lines)
        if done:
            _commit(p.marks)
            if p.learn is not None:
                learn.told(p.learn)
    except Exception as exc:
        logger.warning("brief: not delivered (%r)", exc)
    return res


def attach(res, lines):
    """(result, attached): a JSON object gets KEY first, text the lines and a blank line before it."""
    if not isinstance(res, str):
        return res, False
    i = res.find("{")
    if i >= 0 and not res[:i].strip():
        try:
            obj = json.loads(res)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            sep = "" if not obj else ","
            return res[:i + 1] + f"\n {json.dumps(KEY)}: {json.dumps(lines, ensure_ascii=False)}{sep}" \
                + res[i + 1:], True
    return "\n".join(lines) + "\n\n" + res, True


def reset() -> None:
    """Forget every cursor, as a fresh server process would."""
    with _lock:
        _marks.clear()
        _said.clear()
    learn.told(False)


def _commit(marks: dict) -> None:
    with _lock:
        for model, mk in marks.items():
            if model is None:                  # the milestones told: not again from another model
                _said.update(dict.fromkeys(mk, True))
                while len(_said) > SAID_MAX:
                    _said.pop(next(iter(_said)))
                continue
            cur = _marks.get(model)
            if cur is None or tuple(mk["key"]) >= tuple(cur["key"]):
                _marks[model] = mk


# ---------------------------------------------------------------------------- collect
def collect(manager, session=None, types=None, since=None) -> tuple[list, dict]:
    """(lines, new cursors) for the model of ``session`` (None: every open session's).
    ``since`` (a time): what others changed after it instead, told before or not -- model
    changes only, no brake milestones; the cursors neither read nor moved ({})."""
    if not journal.enabled():
        return [], {}
    names = [session] if session else list(getattr(manager, "_session_files", None) or ())
    found, marks, where, done, seen = [], {}, [], set(), set()
    with _lock:
        said = set(_said)
    for s in names:
        model = manager.model_id(s)
        if not model or model in done:
            continue
        done.add(model)
        if since is None:
            items, mk = _news(model, s, types)
            if mk is not None:
                marks[model] = mk
        else:
            items = _after(model, s, types, since)
        for t, text, key in items:
            if key is None:
                found.append((t, s, text))
                if s not in where:
                    where.append(s)
            elif key not in seen and key not in said:     # (written to every open model: told once)
                seen.add(key)
                found.append((t, None, text))
    if seen:
        marks[None] = sorted(seen, key=repr)
    return _render(found, where, since), marks


def _news(model, session, types):
    """([(t, text, key)], the cursor past them | None when nothing moved) of one model; ``key``
    None for a change, else the brake milestone's (``_brakes``)."""
    others = journal.others(model)
    if others is None:
        return [], None
    with _lock:
        mk = _marks.get(model)
    if mk is None:
        mk = _start(model)
    if mk["others"] == others:
        return [], None
    p = journal.page(model, limit=READ, after=list(mk["key"]))
    if p.get("error"):
        return [], None
    recs = p.get("records") or []
    key = max([mk["key"]] + [(float(r.get("t") or 0), str(r.get("id") or "")) for r in recs])
    items = _rows(list(reversed(recs)), p.get("groups") or {}, _tmap(types, session), milestones=True)
    if p.get("more"):
        items.insert(0, (0.0, "(more changes than shown: workbench_read lists the latest under \"changes\")", None))
    return items, {"key": key, "others": others}


def _after(model, session, types, since) -> list:
    """collect(since=)'s rows of one model: others' changes after ``since``."""
    p = journal.page(model, limit=READ, after=since)
    if p.get("error"):
        return []
    items = _rows(list(reversed(p.get("records") or [])), p.get("groups") or {}, _tmap(types, session))
    if p.get("more"):
        items.insert(0, (0.0, "(more changes than shown: workbench_read lists the latest under \"changes\")", None))
    return items


def _tmap(types, session) -> dict:
    try:
        return (types(session) if types is not None else {}) or {}
    except Exception:
        return {}


def _start(model) -> dict:
    """A model's first cursor: its last AI record, else this process's start."""
    p = journal.page(model, limit=1, actors=["ai"])
    r = (p.get("records") or [None])[0]
    key = (float(r.get("t") or 0), str(r.get("id") or "")) if r else (START, "")
    with _lock:
        return _marks.setdefault(model, {"key": key, "others": None})


def _who(r, heads) -> str | None:
    """Who made a record, as the brief says it; None for this AI's own."""
    if r.get("actor") == "external":                   # found by comparing: after the fact
        return EXTERNAL_RUN if r.get("op") in journal.RUN_OPS else EXTERNAL
    g = heads.get(r.get("group")) or {}
    if r.get("actor") == "ai" or r.get("via") == "mcp" or g.get("ai_group"):
        mine = r.get("srv") == journal.srv() or float(r.get("t") or 0) < START   # (a predecessor's)
        return None if mine else OTHER_AI
    return str(r.get("actor") or "someone") + (f" ({r['via']})" if r.get("via") else "")


def _told(r) -> bool:
    op, st = r.get("op"), r.get("status")
    if op in journal.RUN_OPS:
        return st not in ("refused", "unchanged")
    return op in journal.INPUT_OPS and st == "changed"


def _began(r, heads) -> str | None:
    """An open begin record (journal.page marks it: nothing ended it) as a brief line, or None:
    this process's own calls are still running and not news; the AI's own of an earlier
    server process (killed during it) are told too -- this AI has no memory of them, and the
    model may hold whatever that call last wrote."""
    if not r.get("open") or r.get("srv") == journal.srv():
        return None
    who = _who(r, heads)
    owner = ("an earlier server session's" if who is None else f"{OTHER_AI}'s" if who == OTHER_AI
             else "the user's" if r.get("actor") in ("program", "user") else f"{who}'s")
    tool = r.get("tool") if r.get("tool") != "workbench_run" else None
    noun = tool or ("program" if r.get("actor") == "program" and not r.get("do") else None)
    return " ".join(x for x in (owner, noun, journal.what(r)) if x)


def _items(recs, heads, types) -> list:
    """[(t, text)], oldest first, of the model changes others made (``_rows``, no milestones)."""
    return [(t, text) for t, text, _ in _rows(recs, heads, types)]


def _rows(recs, heads, types, milestones=False) -> list:
    """[(t, text, key)], oldest first: a field typed by hand (repeats folded: first value ->
    last), a run, anything else as the journal says it, one line per program run, one per
    undo or redo made in the window (``_undone``), one per card of the AI applied after its
    call (``_applied``), and a long call that started with no end recorded (``_began``) --
    ``key`` None; ``milestones``: also what the user did to this AI in the workbench
    (``_brakes``, each with its event's key)."""
    rows, fields, progs, undos, props, marks, failed = [], {}, {}, {}, {}, [], None
    for r in recs:
        if r.get("kind") == "begin":
            text = _began(r, heads)
            if text:
                rows.append([float(r.get("t") or 0), "text", text])
            continue
        if r.get("kind") != "change":
            continue
        if r.get("op") in BRAKE_OPS:
            if milestones and r.get("srv") == journal.srv():    # (another server's: about its own AI)
                marks.append(r)
            continue
        g = heads.get(r.get("group")) or {}
        if g.get("actor") == "program" and g.get("proposal"):   # the user ran the AI's proposal
            who = _who(r, heads)                           # (one line, also when nothing in it changed)
            if who is None:
                continue
            if r["group"] not in progs:
                progs[r["group"]] = (who, [])
                rows.append([float(r.get("t") or 0), "prog", r["group"]])
            if _told(r):
                progs[r["group"]][1].append(r)
            continue
        prop = _proposal(r, heads)
        if prop is not None:                               # "AI proposed, you executed": one line a card
            if prop not in props:
                props[prop] = []
                rows.append([float(r.get("t") or 0), "prop", prop])
            props[prop].append(r)
            continue
        if not _told(r):
            continue
        who = _who(r, heads)
        if who is None:
            continue
        t, gid, op = float(r.get("t") or 0), r.get("group"), r.get("op")
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        if r.get("tool") == "revert" or r.get("revert_of"):     # an undo (tools/undo_apply.py): one line each
            k = (who, r.get("call") or gid)
            if k not in undos:
                undos[k] = (who, [])
                rows.append([t, "undo", k])
            undos[k][1].append(r)
        elif (heads.get(gid) or {}).get("actor") == "program":
            if gid not in progs:
                progs[gid] = (who, [])
                rows.append([t, "prog", gid])
            progs[gid][1].append(r)
        elif op in ("value", "attr") and tg.get("path") and tg.get("attr") is None:
            k = (who, tg["path"].lower())
            if k not in fields:
                fields[k] = {"who": who, "path": tg["path"], "before": r.get("before"), "n": 0}
                rows.append([t, "field", k])
            f = fields[k]
            f.update(after=r.get("after"), n=f["n"] + 1)
        elif op in journal.RUN_OPS:
            rows.append([t, "text", f"{who} ran the simulation: {r.get('status')}" + _counts(r)])
            if milestones and op == "run" and r.get("status") in ("error", "refused"):
                failed = (len(rows), r)
        else:
            rows.append([t, "text", f"{who} {journal.what(r, lambda p: aspen_labels.named(p, types))}"])
    if failed is not None:                                 # the newest failed run's diagnosis
        text = _diagnosis(failed[1], types)
        if text:
            rows.insert(failed[0], [float(failed[1].get("t") or 0), "text", text])
    out = []
    for t, kind, x in rows:
        if kind == "field":
            f = fields[x]
            text = f"{f['who']} set {aspen_labels.named(f['path'], types, 'path')} {_v(f['before'])} → " \
                   f"{_v(f['after'])}" + (f" ({f['n']} edits)" if f["n"] > 1 else "")
        elif kind == "prog":
            text = _program(heads.get(x) or {}, *progs[x], types)
        elif kind == "undo":
            text = _undone(*undos[x], heads, types)
        elif kind == "prop":
            text = _applied(*x, props[x], types)
        else:
            text = x
        out.append((t, text, None))
    if marks:
        out = sorted(out + _brakes(marks, [t for t, _, _ in out]), key=lambda x: x[0])
    return out


def _diagnosis(r, types) -> str | None:
    """A failed or refused run's diagnosis in one line (tools/diagnose.say): the
    workbench's card of it when it built one, else the record's own (its blocks, its Run-Status
    lines, what changed since the last good run)."""
    try:
        model = r.get("model")
        c = diagnose.recall(model, r.get("id")) or diagnose.session_card({}, r, "en", model, latest=False)
        text = diagnose.say(c, lambda p: aspen_labels.named(p, types), short=True)
    except Exception as exc:
        logger.warning("brief: no diagnosis of run %s (%r)", r.get("id"), exc)
        return None
    return f"why: {text}; workbench_read has its diagnosis" if text else None


# ---------------------------------------------------------------------------- the brakes
def _proposal(r, heads):
    """(card, whose) of a record a card of the AI's made after its call ended ("AI proposed,
    you executed": ``proposed``), else None -- also for a program run's (``_program`` says it)."""
    p = r.get("proposed")
    if not isinstance(p, dict) or p.get("by") != "ai" or p.get("card") is None \
            or (heads.get(r.get("group")) or {}).get("actor") == "program" or r.get("op") == "checkpoint":
        return None
    return p["card"], _whose(r)


def _whose(r) -> str:
    mine = r.get("srv") == journal.srv() or float(r.get("t") or 0) < START
    return "your" if mine else f"{OTHER_AI}'s"


def _applied(card, whose, recs, types) -> str:
    """One card applied after the AI's call: "user applied your proposal #12: removed block B4
    (Heater)" -- or tried, and it failed."""
    name = lambda p: aspen_labels.named(p, types)        # noqa: E731
    done = [r for r in recs if r.get("status") not in NOT_DONE]
    if not done:
        return f"user tried to apply {whose} proposal #{card}: {journal.what(recs[-1], name)}"
    texts = []
    for r in done:
        op, tg = r.get("op"), r.get("target") if isinstance(r.get("target"), dict) else {}
        if op in ("value", "attr") and tg.get("path") and tg.get("attr") is None:
            texts.append(f"set {aspen_labels.named(tg['path'], types, 'path')} {_v(r.get('before'))} → "
                         f"{_v(r.get('after'))}")
        elif op in journal.RUN_OPS:
            texts.append("reinitialized the simulation" if op == "reinit" else
                         f"ran the simulation: {r.get('status')}" + _counts(r))
        else:
            texts.append(journal.what(r, name))
    return _fit(f"user applied {whose} proposal #{card}: ", texts)


def _fit(text, items) -> str:
    """``text`` then ``items`` joined by "; " as far as a line holds them (+N more)."""
    text += items[0]
    for i, x in enumerate(items[1:], 1):
        rest = len(items) - i - 1
        if len(text) + 2 + len(x) + (len(f" (+{rest} more)") if rest else 0) > WIDTH - 9:   # "- HH:MM "
            return text + f" (+{len(items) - i} more)"
        text += "; " + x
    return text


def _brakes(recs, changes) -> list:
    """[(t, text, key)] of what the user did to this AI in the workbench (records this process
    wrote, oldest first; ``changes``: the times of the other lines, for "meanwhile"; ``key``:
    the event's, the same in every model's copy -- collect tells it once). A pause that ended
    is one line at its start, "–14:05 ..." (``_render`` puts its start before it), with the
    pause's own record folded in; a pause still on, an automatic one no answer told
    (``told_in``: the call whose answer ended saying so), a mode switch (the latest), a card
    the user declined after the AI's call ended (a ``proposal`` record)."""
    out, ends = [], [r for r in recs if r.get("op") == "brake" and r.get("what") == "resume"]
    spans = [(float(r.get("since") or 0) - 1.0, float(r.get("t") or 0)) for r in ends]
    folded = {}                                            # a resume's since -> the stuck record it ends
    last_mode = next((r for r in reversed(recs) if r.get("what") == "mode"), None)
    for r in recs:
        t, what = float(r.get("t") or 0), r.get("what")
        if r.get("op") == "proposal":
            if r.get("proposal") and r.get("status") == "rejected":     # a proposal sent back
                c, tab = " ".join(str(r.get("comment") or "").split()), r.get("tab")
                out.append((t, f"user rejected your proposal '{r.get('title')}' (tab {tab})"
                               + (f": \"{_cut(c, 100)}\"" if c else " without a comment")
                               + f"; revise it: workbench_edit(tab='{tab}', proposal={{...}})",
                            ("proposal", r.get("proposal"), r.get("note_id") or t)))
            elif r.get("status") == "declined":
                c = r.get("comment")
                out.append((t, f"user declined your proposal #{r.get('card')} ({brake.what(r.get('tool'), r.get('target'))})"
                               + (f": \"{c}\"" if c else "") + "; do not retry it", ("proposal", r.get("card"))))
            continue
        if what in ("pause", "stuck") and not r.get("fallback"):
            span = next((s for s in spans if s[0] <= t <= s[1]), None)
            if span is not None:                           # told with its end
                folded[span] = r
                continue
        if what == "pause":
            out.append((t, "user paused you: your changes wait for them and are not applied; reads still work",
                        ("pause", t)))
        elif what == "stuck" and not r.get("told_in"):
            why = brake.rule_text(r.get("rule"), r.get("detail"))
            out.append((t, f"the workbench noticed {why}; no window is open, so you were not paused: diagnose "
                           "before changing more" if r.get("fallback") else
                           f"the workbench paused you automatically: {why}; your changes wait for the user", ("stuck", t)))
        elif what == "mode" and r is last_mode and r.get("mode") in MODES:
            out.append((t, f"user switched you to {MODES[r['mode']]}", ("mode", t)))
    for r, span in zip(ends, spans):
        since, t = float(r.get("since") or 0), float(r.get("t") or 0)
        stuck = folded.get(span)
        if r.get("rule") or (stuck or {}).get("what") == "stuck":
            why = brake.rule_text(stuck.get("rule"), stuck.get("detail")) if stuck and stuck.get("detail") \
                else RULES.get(r.get("rule"), str(r.get("rule") or "it looked stuck"))
            text = f"the workbench paused you automatically because {why}"
        else:
            text = "user paused you"
        if r.get("by") == "window_closed":
            text += "; the pause ended when the workbench window closed"
        elif r.get("rule"):
            text += "; the user resumed you"
        if r.get("note"):
            text += f"; their note: \"{r['note']}\""
        n = sum(since <= x <= t for x in changes)
        text += "; meanwhile:" if n else "; nothing changed meanwhile" if r.get("changes") == 0 else ""
        out.append((since or t, f"–{_clock(t).strip()} {text}" if since else text, ("resume", since or t)))
    return out


def _undone(who, recs, heads, types) -> str:
    """One undo the user made in the workbench window (or a redo: an undo of an undo): "user
    (window) undid 2 changes: <field> 40 → 25; ..." -- a field as its label plus path, first
    value -> last; a port's streams taken off / put back; an object removed; a restore undone
    (the model back to the point kept before it)."""
    name = lambda p: aspen_labels.named(p, types)        # noqa: E731
    fields, items = {}, []
    for r in recs:
        op = r.get("op")
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        if op in ("value", "attr") and tg.get("path") and tg.get("attr") is None:
            k = tg["path"].lower()
            if k in fields:
                fields[k][2] = r.get("after")
            else:
                fields[k] = [tg["path"], r.get("before"), r.get("after")]
                items.append(("field", k))
        elif op == "connect" and isinstance(r.get("before"), list) and isinstance(r.get("after"), list):
            off, on = [x for x in r["before"] if x not in r["after"]], [x for x in r["after"] if x not in r["before"]]
            where = " ".join(str(tg[k]) for k in ("block", "port") if tg.get(k))
            did = ([f"took {', '.join(map(str, off))} off {where}"] if off else []) + \
                  ([f"put {', '.join(map(str, on))} on {where}"] if on else [])
            items.append(("text", "; ".join(did) or journal.what(r, name)))
        else:
            items.append(("text", journal.what(r, name)))
    texts = [f"{aspen_labels.named(fields[x][0], types, 'path')} {_v(fields[x][1])} → {_v(fields[x][2])}"
             if kind == "field" else x for kind, x in items]
    if all(r.get("op") == "restore" for r in recs):
        return f"{who} undid a restore: " + "; ".join(texts)
    n = len(texts)
    approx = sum(r.get("exact") is False for r in recs)
    head = heads.get(recs[0].get("group")) or {}
    of = heads.get(head.get("of")) if isinstance(head.get("of"), str) else None
    name = (of or {}).get("title") or head.get("label")      # (label: that title as the undo found it)
    title = f" of \"{name}\"" if name else ""
    text = f"{who} {'redid' if any(r.get('redo') for r in recs) else 'undid'} {n} change{'s' * (n != 1)}{title}" \
           + (f" ({approx} only approximately)" if approx else "") + ": " + texts[0]
    for i, x in enumerate(texts[1:], 1):
        rest = len(texts) - i - 1
        if len(text) + 2 + len(x) + (len(f" (+{rest} more)") if rest else 0) > WIDTH - 9:   # "- HH:MM "
            return text + f" (+{len(texts) - i} more)"
        text += "; " + x
    return text


def _counts(r) -> str:
    c = [f"{r[k]} {k}" for k in ("errors", "warnings") if r.get(k)]
    return f" ({', '.join(c)})" if c else ""


def _v(x) -> str:
    return journal._val(x)


def _same(a, b) -> bool:
    va, vb = (x.get("value") if isinstance(x, dict) else x for x in (a, b))
    try:
        return float(va) == float(vb)
    except (TypeError, ValueError):
        return str(va) == str(vb)


def _did(recs, types) -> tuple[list, list]:
    """What a program run's records did -- ["2 sets", "sweep of <field> 1..3", "1 run", ...] --
    and the fields it left changed, first value -> last, as text."""
    sets = runs = ok = back = links = 0
    loops, net, objs = [], {}, {"add": [], "remove": []}
    for r in recs:
        op = r.get("op")
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        writes = r.get("writes") if isinstance(r.get("writes"), dict) else {}
        if op in journal.RUN_OPS:
            runs, ok = runs + 1, ok + (r.get("status") == "ok")
        elif op in ("value", "attr") and tg.get("path"):
            sets += 1
            writes = {tg["path"]: {"before": r.get("before"), "after": r.get("after")}}
        elif op == "restore":
            back += r.get("n") or len(writes)
        elif op in objs:                                  # a flowsheet statement: what it placed / removed
            objs[op].append(str(tg.get("name") or tg.get("block") or tg.get("stream") or "?"))
        elif op == "connect":
            links += 1
        else:
            rg = r.get("range") if isinstance(r.get("range"), list) and len(r["range"]) == 2 else None
            of = f" of {aspen_labels.named(tg['path'], types, 'label')}" if tg.get("path") else ""
            span = f" {_v({'value': rg[0]})}..{_v({'value': rg[1]})}" if rg else ""
            loops.append(str(r.get("do") or op) + of + span + (f" ({r['n']} writes)" if r.get("n") else ""))
        if op not in journal.RUN_OPS and isinstance(r.get("runs"), dict):     # a loop's, the restore's
            runs, ok = runs + (r["runs"].get("n") or 0), ok + (r["runs"].get("ok") or 0)
        for path, w in writes.items():
            if journal.split_key(path)[1] is not None or not isinstance(w, dict) or w.get("status", "changed") != "changed":
                continue
            k = path.lower()
            net[k] = [path, net[k][1] if k in net else w.get("before"), w.get("after")]
    did = [f"{sets} set{'s' * (sets != 1)}"] if sets else []
    for op, verb in (("add", "added"), ("remove", "removed")):
        if objs[op]:
            did.append(f"{verb} {', '.join(objs[op][:4])}" + (f" +{len(objs[op]) - 4}" if len(objs[op]) > 4 else ""))
    if links:
        did.append(f"{links} connection{'s' * (links != 1)}")
    did += loops[:2] + ([f"{len(loops) - 2} more loop(s)"] if len(loops) > 2 else [])
    if runs:
        did.append(f"{runs} run{'s' * (runs != 1)}" + ("" if ok == runs else f" ({runs - ok} not ok)"))
    if back:
        did.append(f"put {back} value(s) back")
    left = [f"{aspen_labels.named(p, types)} {_v(b)} → {_v(a)}" for p, b, a in net.values() if not _same(b, a)]
    return did, left


def _left(text, left) -> str:
    """``text`` then "left <field> a → b; ..." as far as a line holds them (+N more)."""
    text += "left " + left[0]
    for i, x in enumerate(left[1:], 1):
        rest = len(left) - i - 1
        if len(text) + 2 + len(x) + (len(f" (+{rest} more)") if rest else 0) > WIDTH - 9:   # "- HH:MM "
            return text + f" (+{len(left) - i} more)"
        text += "; " + x
    return text


def _program(head, who, recs, types) -> str:
    """One program run: what it did, then the fields it left changed (first value -> last). A
    program card of the AI's the user approved after its call ended (``proposed``): "user
    applied your proposal #12 (program "...")"; the AI's proposal the user ran (the header's
    ``proposal``): _approved."""
    if head.get("proposal"):
        return _approved(head, recs, types)
    prop = next((r["proposed"] for r in recs if isinstance(r.get("proposed"), dict)
                 and r["proposed"].get("by") == "ai" and r["proposed"].get("card") is not None), None)
    did, left = _did(recs, types)
    title = f" \"{head['title']}\"" if head.get("title") else ""
    owner = OTHER_AI if who == OTHER_AI else "the user"
    lead = f"user applied {_whose(recs[0])} proposal #{prop['card']} (program{title})" if prop else \
        f"{owner}'s program{title}"
    text = f"{lead}: {', '.join(did) or 'no changes'}; "
    if not left:
        return text + "inputs it wrote are back as they were"
    return _left(text, left)


def _approved(head, recs, types) -> str:
    """The user's run of the AI's proposal -- their approval --, from its change group's
    header (``outcome``, written when it ended) and its records: "user approved and ran your
    proposal 'Warmer feed': applied 3 steps (2 sets, 1 run); left <field> 25 → 30"; "...: step 3
    failed (<why>); the 2 steps before it applied (...)"; "...: they stopped it before step 3;
    nothing applied"; the user's edits of it first ("after they turned off c"); before it ended,
    "it is running now"."""
    o = head.get("outcome") if isinstance(head.get("outcome"), dict) else {}
    lead = f"user approved and ran your proposal '{head.get('title') or head.get('proposal')}'"
    if o.get("edits"):
        lead += f" (after they {_cut(o['edits'], 60)})"
    elif o.get("off"):
        lead += f" ({o['off']} step{'s' * (o['off'] != 1)} turned off)"
    st, done, n = o.get("status"), int(o.get("done") or 0), o.get("n") or "?"
    steps = f"{done} step{'s' * (done != 1)}"
    err = f" ({_cut(' '.join(str(o['error']).split()), 80)})" if o.get("error") else ""
    what = ("it is running now" if st is None else f"applied {steps}" if st == "applied"
            else f"step {n} failed{err}; the {steps} before it applied" if st == "partial" and o.get("error")
            else f"they stopped it before step {n}; the {steps} before it applied" if st == "partial"
            else f"step {n} failed{err}; nothing applied" if st == "failed"
            else f"they stopped it before step {n}; nothing applied")
    did, left = _did(recs, types)
    text = f"{lead}: {what}" + (f" ({', '.join(did)})" if did else "")
    return _left(text + "; ", left) if left else text


def _cut(text, n) -> str:
    text = str(text)
    return text if len(text) <= n else text[:n - 1] + "…"


def _render(found, where, since=None) -> list:
    """The lines: a header, then ``found`` [(t, session | None for a milestone, text)] by time
    -- a text starting "–" is a span from its time ("14:02–14:05 user paused you")."""
    if not found:
        return []
    many = len(where) > 1
    names = ", ".join(f"'{s}'" for s in where)
    when = "your last call" if since is None else _clock(since).strip() or "then"
    head = f"[workbench] Since {when}, others changed {'sessions ' if many else ''}{names} " \
           f"(measured by the server; not by you):" if where else f"[workbench] Since {when}, in the workbench:"
    found.sort(key=lambda x: x[0])
    rows = [f"- {_clock(t).strip() if text.startswith('–') else _clock(t)}{s + ': ' if many and s else ''}{text}"
            for t, s, text in found]
    if len(rows) > LINES - 1:
        cut = len(rows) - (LINES - 2)
        rows = rows[cut:] + [f"- ({cut} earlier change(s) not shown: workbench_read lists them under \"changes\")"]
    return [head] + [r if len(r) <= WIDTH else r[:WIDTH - 1] + "…" for r in rows]


def _clock(t) -> str:
    return time.strftime("%H:%M ", time.localtime(t)) if t else ""
