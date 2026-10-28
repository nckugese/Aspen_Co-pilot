"""Proposals: a block program the AI writes for the user to review and run.

The AI cannot approve its own change. It writes the change as a program -- ``workbench_edit(
proposal={"title", "reason"}, program=[...])``, a sub-tab of its model's tab -- and the user reads it, checks
it, edits or turns off steps, and approves it by running it in the window; the AI may only check
it (a dry run). This module is the proposal's data and its words: pure, stdlib only (plus the
program model in tools/wb_plan.py), no COM, no I/O, no clock (the caller gives ``t``).
tools/workbench_tools.py wires it: workbench_edit, the window's program / undo events, the check,
workbench_run's refusal and workbench_read.

A proposal tab is a tab with ``kind`` "proposal", ``parent`` (its model's tab:
one tab per model, its proposals as sub-tabs) and ``proposal``:

    {"id": "p...", "title", "reason", "status", "rev": the AI's revisions (1 = as first written),
     "t0", "t", "proposed_in": the AI's change group then, "note": the Ask AI note it answers,
     "base": {"model", "input_t": the journal's latest input when it was written},
     "ai": {"program_rev", "program"} -- the AI's last version, to tell what the user changed
           ({"program_rev", "big": true} past AI_MAX: then ``edited`` is {"unknown": true}),
     "edited": {"changed", "added", "removed", "off"} | null -- the user's changes to it,
     "reply": {"text", "t"} | null -- the user's comment sending it back (reject),
     "run": null | the approved run (approve / stepped / finish): {"group", "model", "mode", "cp":
            the restore point ({"id", "status", "state", "secs", "tier", "t"}, or {"skipped":
            "user"}), "done", "total", "wrote", "n" / "at": the step running (then the one it
            stopped or failed at), "failed_at", "failed_id", "error", "outcome": the last
            simulation run's, "off", "rev", "edited", "t0", "t1", "undone": {"how", "t"}, "end": the
            status it ended in, "applied": {sid: its signature} -- the top-level steps that change the
            model and finished (ran_step)},
     "ran"?: [sids] -- a revision of a partly applied or failed proposal: the steps of the new
            version that applied in that run and are unchanged, turned off for the user (mark_ran);
            the window marks them already run (the user may turn them back on). Cleared by approval.
     "unapplied"?: [ids] -- the user's edits to an applied or partly applied proposal that its run did
            not apply (unapplied; set as they edit it): the window offers to apply just those, an
            approval with ``approve`` "edits". Cleared by approval, an undo, a revision.
     "refused": null | why the user's last approval did not run: {"why": draft | running |
            withdrawn | empty | check | cp | error, "t", "errors", "text", and for check "texts" /
            "help": the short line and the explanation in both languages ({"en", "zh"})},
     "log": [{"t", "what", "by"}] -- the last LOG_MAX of proposed, revised, edited, checked,
            withdrawn, approved, applied, partial, failed, stopped, rejected, dismissed, undone; by
            ai | user | auto},
     "dismissed": null | {"t", "was": the status before} -- the user closed it (dismiss),
     "watch"?: [{"path", "label"?}] -- at most WATCH_MAX results the window tags after the run, the
            first the goal (the AI's, written with the proposal, not a revision),
     "explain"?: {"run", "items": [{"result", "via"?, "words"?, "text"?}]} -- the AI's words on a run's
            result tags (written after the run, for that run only, not a revision)

status: ``draft`` (the AI is still writing it: it cannot be approved yet), ``open`` (waiting for
the user's review), ``withdrawn`` (the AI took it back) -- and, once the user acts on it:
``running`` (approved: it runs now), then ``applied`` (every step ran), ``partial`` (it stopped
or failed after a step that changes the model had run), ``failed`` (a step failed before any
did), ``stopped`` (the user stopped it before any did); ``rejected`` (sent back with a comment,
a note to the AI), ``dismissed`` (the user closed it: it does not run; the AI may revise it,
which opens it again). The AI says "ready" (or "open") for open, the default.

Lanes (``lane``): ``active`` -- draft, open, running (paused or waiting too), stopped, partial,
failed: in the model tab's row until the user decides -- and ``history`` -- applied, rejected,
withdrawn, dismissed (FINISHED). A finished one stays loaded until the window leaves it; one no
longer loaded is kept in tools/prop_archive.py (its ``history_entry`` in the model's index), and an
AI revision brings it back (status_after reopens it).

A run the user stopped keeps ``run.resume`` {"at", "n", "rev", "mode"} (stopped_at): approving it
again with that step (resumable) continues from there -- the steps before it that change the
model are not run again, the first approval's restore point is kept (``run.resumed``).

Approval: the user runs the proposal from the window -- that is the approval,
the AI may only check it. workbench_tools refuses the run first when it cannot be one (``why_not``:
a draft, running, withdrawn, no step turned on), then pre-checks it (an error: not run, nothing
saved -- ``refused``), keeps a restore point, and runs it as the program "approved by the user"
(``approve``, ``stepped``, ``finish``).
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid

from tools import wb_plan

STATUSES = ("draft", "open", "running", "applied", "partial", "failed", "stopped", "rejected", "withdrawn",
            "dismissed")
ASKED = {"ready": "open", "open": "open", "draft": "draft", "withdrawn": "withdrawn"}   # the AI's words
TITLE_MAX = 120          # characters of a title (the tab's own: 60)
REASON_MAX = 1000        # ... of the AI's reason
LOG_MAX = 20             # entries a proposal's log keeps
AI_MAX = 32 * 1024       # bytes of the AI's version kept to tell the user's edits from
IDS_MAX = 50             # statement ids an ``edited`` list keeps
READ_MAX = 5             # proposals workbench_read lists for a session
CLOSED_READ = 3          # proposals the user closed unrun that workbench_read lists
PROBLEMS_READ = 5        # a check's problems workbench_read lists
PROBLEM_TEXT = 160       # characters of one of them
REPLY_MAX = 1000         # characters of the user's comment sending one back
ERROR_TEXT = 200         # ... of the error a failed step left in ``run``
CANNOT = ("draft", "running", "withdrawn", "dismissed")    # statuses the user's run is refused in
FINISHED = ("applied", "rejected", "withdrawn", "dismissed")   # the history lane; the rest: active
HISTORY_READ = 5         # history entries workbench_read lists
WATCH_MAX = 3            # results a proposal's watch names (the first is the goal)
WATCH_LABEL_MAX = 40     # characters of a watched result's label
EXPLAIN_ITEMS = 3        # results one explain speaks of
EXPLAIN_TEXT = (140, 280)   # characters of an explain's sentence: Chinese, else
EXPLAIN_WORDS = (12, 24)    # ... of its words by an object on the path
EXPLAIN_VIA = 24         # objects a path the AI gives names
EDITS = ("applied", "partial")   # the ends whose user edits run by themselves (kept, unapplied)
WRITES = ("set",) + wb_plan.STRUCTURE   # steps that leave what they wrote as it is (kept)


# ---------------------------------------------------------------------------- the AI's argument
def spec(p) -> dict:
    """The AI's ``proposal`` argument -- {"title", "reason", "status"?} -- checked: {"title",
    "reason" (each only when given), "status": draft | open | withdrawn | None}. ValueError."""
    if not isinstance(p, dict):
        raise ValueError('proposal must be an object: {"title", "reason", "status"?}')
    out = {}
    for key, cap in (("title", TITLE_MAX), ("reason", REASON_MAX)):
        v = p.get(key)
        if v is None:
            continue
        if not isinstance(v, str):
            raise ValueError(f"proposal {key} must be text")
        v = " ".join(v.split())[:cap] if key == "title" else v.strip()[:cap]
        if v:
            out[key] = v
    st = p.get("status")
    if st is not None and str(st).strip().lower() not in ASKED:
        raise ValueError(f"proposal status {st!r}: use \"ready\" (the default), \"draft\" or \"withdrawn\"")
    out["status"] = ASKED[str(st).strip().lower()] if st is not None else None
    if "watch" in p:
        out["watch"] = watch_spec(p["watch"])
    if "explain" in p:
        out["explain"], out["explain_dropped"] = explain_spec(p["explain"])
    return out


_DIGIT = re.compile(r"\d")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")      # a name -- HX1, CO2, H2O --: its digits are no number
_CJK = re.compile(r"[　-鿿＀-￯]")


def _number_in(text: str) -> bool:
    """Whether ``text`` gives a number: a digit (ASCII or full-width) outside a name like HX1 or CO2."""
    return bool(_DIGIT.search(_NAME.sub(" ", text)))


def _cap(text: str, caps: tuple[int, int]) -> str:
    return text[:caps[0] if _CJK.search(text) else caps[1]]


def explain_spec(x) -> tuple[dict | None, list[str]]:
    """The AI's ``explain`` of a run's result tags: {"run", "items": [{"result" (the
    result's path), "via"? (the objects from a change to it, in flow order), "words"? ({OBJECT: a few
    words}, at most one), "text"? (one sentence)}]}, at most EXPLAIN_ITEMS; None or {} clears it.
    Words and text carry no number -- the numbers are the measured ones; a digit in a name such as HX1
    or CO2 is none --: one that does is dropped
    (the second value: "item N text" / "item N words" said back). ValueError for a malformed one."""
    if x is None or x == {}:
        return None, []
    shape = '{"run", "items": [{"result", "via"?, "words"?, "text"?}]}'
    if not isinstance(x, dict) or any(k not in ("run", "items") for k in x):
        raise ValueError(f"proposal explain must be {shape}")
    run, items = x.get("run"), x.get("items")
    if not isinstance(run, str) or not run.strip():
        raise ValueError('proposal explain needs "run": the id of the run its results come from (workbench_read: '
                         "proposals[].effects.run)")
    if not isinstance(items, list) or not 1 <= len(items) <= EXPLAIN_ITEMS:
        raise ValueError(f'proposal explain "items" must be a list of 1-{EXPLAIN_ITEMS} results: {shape}')
    out, dropped = [], []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict) or any(k not in ("result", "via", "words", "text") for k in it):
            raise ValueError(f'proposal explain item {i} must be {{"result", "via"?, "words"?, "text"?}}')
        res, via, words, text = it.get("result"), it.get("via"), it.get("words"), it.get("text")
        if not isinstance(res, str) or not res.strip().startswith("\\"):
            raise ValueError(f'proposal explain item {i}: "result" must be the result\'s tree path (\\Data\\...)')
        row = {"result": res.strip()}
        if via is not None:
            if not isinstance(via, list) or not 2 <= len(via) <= EXPLAIN_VIA \
                    or not all(isinstance(v, str) and v.strip() for v in via):
                raise ValueError(f'proposal explain item {i}: "via" must be 2-{EXPLAIN_VIA} block and stream names '
                                 "in flow order")
            row["via"] = [v.strip().upper() for v in via]
        if words is not None:
            if not isinstance(words, dict) or len(words) > 1 or not all(isinstance(k, str) and k.strip() and
                                                                         isinstance(v, str) for k, v in words.items()):
                raise ValueError(f'proposal explain item {i}: "words" must be {{"OBJECT": "a few words"}}, one object')
            for k, v in words.items():
                v = " ".join(v.split())
                if _number_in(v):
                    dropped.append(f"item {i} words")
                elif v:
                    row["words"] = {k.strip().upper(): _cap(v, EXPLAIN_WORDS)}
        if text is not None:
            if not isinstance(text, str):
                raise ValueError(f'proposal explain item {i}: "text" must be text')
            v = " ".join(text.split())
            if _number_in(v):
                dropped.append(f"item {i} text")
            elif v:
                row["text"] = _cap(v, EXPLAIN_TEXT)
        out.append(row)
    return {"run": run.strip(), "items": out}, dropped


def watch_spec(w) -> list[dict]:
    """The proposal's ``watch``: at most WATCH_MAX results [{"path", "label"?}] the
    window tags after the run, ``watch[0]`` the goal; [] clears it. ValueError."""
    if w is None:
        return []
    if not isinstance(w, list) or len(w) > WATCH_MAX:
        raise ValueError(f'proposal watch must be a list of at most {WATCH_MAX} results: [{{"path", "label"?}}], '
                         "the goal first")
    out, seen = [], set()
    for i, x in enumerate(w, 1):
        x = {"path": x} if isinstance(x, str) else x
        if not isinstance(x, dict) or any(k not in ("path", "label") for k in x):
            raise ValueError(f'proposal watch item {i} must be {{"path", "label"?}}')
        path, label = x.get("path"), x.get("label")
        if not isinstance(path, str) or not path.strip().startswith("\\"):
            raise ValueError(f"proposal watch item {i}: \"path\" must be a tree path (\\Data\\...)")
        if label is not None and not isinstance(label, str):
            raise ValueError(f"proposal watch item {i}: \"label\" must be text")
        path = path.strip()
        if path in seen:
            continue
        seen.add(path)
        item = {"path": path}
        if label and label.strip():
            item["label"] = " ".join(label.split())[:WATCH_LABEL_MAX]
        out.append(item)
    return out


def new(sp: dict, program, program_rev: int, t: float, proposed_in=None, note=None, base=None) -> dict:
    """A proposal as the AI first writes it (``sp``: spec()'s, with a title). ValueError: no
    title, withdrawn (nothing to withdraw), or no step unless a draft."""
    if not sp.get("title"):
        raise ValueError('a new proposal needs a title: proposal={"title": ..., "reason": ...} (to revise or '
                         "withdraw one, give its tab)")
    status = sp.get("status") or "open"
    if status == "withdrawn":
        raise ValueError("to withdraw a proposal, give its tab")
    if status == "open" and not program:
        raise ValueError("a proposal needs its steps: program=[...]")
    prop = {"id": "p" + uuid.uuid4().hex[:7], "title": sp["title"], "reason": sp.get("reason") or "",
            "status": status, "rev": 1, "t0": t, "t": t, "proposed_in": proposed_in, "note": note,
            "base": base, "ai": None, "edited": None, "reply": None, "run": None, "refused": None, "log": []}
    if sp.get("watch"):
        prop["watch"] = sp["watch"]
    _keep_ai(prop, program, program_rev)
    log(prop, "proposed", "ai", t)
    return prop


def _renamed(prop: dict, sp: dict) -> dict:
    return {k: sp[k] for k in ("title", "reason") if sp.get(k) and sp[k] != prop.get(k)}


def status_after(prop: dict, sp: dict | None, program, changed: bool) -> str:
    """The status the AI's workbench_edit on its proposal tab leaves (``sp``: its proposal
    argument or None; ``changed``: the program changed): the one asked, else a draft stays one
    and anything else is open again once revised (the program, title or reason changed).
    ValueError -- before anything is changed: it runs now, or it would be open with no step."""
    sp, was = sp or {}, prop.get("status")
    if was == "running":
        raise ValueError("the user is running this proposal now; wait for it to end")
    changed = changed or bool(_renamed(prop, sp))
    status = sp.get("status") or ("draft" if was == "draft" else "open" if changed else was)
    if status == "open" and not program:
        raise ValueError("a proposal needs its steps: program=[...]")
    return status


def revise(prop: dict, sp: dict | None, program, program_rev: int, changed: bool, t: float) -> dict:
    """The AI's workbench_edit on its proposal tab, after status_after said yes: a change of the
    program (``changed``), title or reason is a revision -- rev + 1, the program as the AI's edit
    left it is the AI's version (the user's edits: replaced by a whole program, taken in by an
    insert; their version stays in the tab's undo history), ``edited`` cleared. Returns {"what": revised | withdrawn |
    None (nothing to say), "replaced": the user's edits the revision replaced, "was": the status
    before, "rev": whether it is a new revision}."""
    sp, was = sp or {}, prop.get("status")
    status = status_after(prop, sp, program, changed)
    if "watch" in sp:                   # (what the result tags show; not a revision)
        if sp["watch"]:
            prop["watch"] = sp["watch"]
        else:
            prop.pop("watch", None)
    if "explain" in sp:                 # (the AI's words on the result tags; not a revision)
        if sp["explain"]:
            prop["explain"] = sp["explain"]
        else:
            prop.pop("explain", None)
    ren = _renamed(prop, sp)
    changed = changed or bool(ren)
    prop.update(ren)
    replaced = None
    if changed:
        replaced = prop.get("edited")
        prop["rev"] = int(prop.get("rev") or 0) + 1
        prop["edited"] = None
        prop.pop("unapplied", None)
        _keep_ai(prop, program, program_rev)
    if not changed and status == was:
        return {"what": None, "replaced": None, "was": was, "rev": False}
    prop["status"] = status
    what = "withdrawn" if status == "withdrawn" else "revised"
    log(prop, what, "ai", t)
    return {"what": what, "replaced": replaced, "was": was, "rev": changed}


def _keep_ai(prop: dict, program, program_rev: int) -> None:
    text = json.dumps(program or [], ensure_ascii=False, separators=(",", ":"))
    prop["ai"] = {"program_rev": program_rev, "big": True} if len(text.encode("utf-8")) > AI_MAX else \
        {"program_rev": program_rev, "program": json.loads(text)}


def log(prop: dict, what: str, by: str, t: float) -> None:
    """One entry of the proposal's log (the last LOG_MAX kept); the user's edits, one after
    another, stay one entry (its time moves)."""
    entries = prop.setdefault("log", [])
    if what == "edited" and entries and entries[-1].get("what") == "edited" and entries[-1].get("by") == by:
        entries[-1]["t"] = t
    else:
        entries.append({"t": t, "what": what, "by": by})
    del entries[:-LOG_MAX]
    prop["t"] = _tick(t)


_LAST = [0.0]


def _tick(t: float) -> float:
    """``t``, or just after the last proposal's change when the clock has not moved since (Windows'
    time.time() ticks every ~16 ms): "the latest changed first" stays the order they changed in."""
    _LAST[0] = t = max(float(t), _LAST[0] + 1e-6)
    return t


# ---------------------------------------------------------------------------- the user's edits
def _ids(program) -> list[str]:
    out = []

    def walk(sts):
        for st in sts or []:
            out.append(st.get("id"))
            for key in wb_plan.NESTED:
                walk(st.get(key))
    walk(program)
    return out


def _bare(program) -> list[dict]:
    """The program without its ``off`` flags (a step turned off is told apart)."""
    return [{k: (_bare(v) if k in wb_plan.NESTED and isinstance(v, list) else v) for k, v in st.items() if k != "off"}
            for st in program or [] if isinstance(st, dict)]


def _offs(program) -> set:
    out = set()

    def walk(sts):
        for st in sts or []:
            if st.get("off") is True:
                out.add(st.get("id"))
            for key in wb_plan.NESTED:
                walk(st.get(key))
    walk(program)
    return out


def edited(prop: dict, program, diff) -> dict | None:
    """What the user changed of the AI's last version: {"changed", "added", "removed" (a count),
    "off": the steps they turned off} -- a step turned back on is changed -- or None (as the AI
    wrote it); {"unknown": true} when the AI's version was too big to keep. ``diff``:
    workbench_tools._program_diff."""
    ai = prop.get("ai") or {}
    if "program" not in ai:
        return {"unknown": True}
    old = ai["program"]
    added, changed, removed = diff(_bare(old), _bare(program))
    was, now, ids = _offs(old), _offs(program), _ids(program)
    off = [sid for sid in ids if sid in now and sid not in was]
    changed = changed + [sid for sid in ids if sid in was and sid not in now and sid not in changed]
    if not (added or changed or removed or off):
        return None
    return {"changed": changed[:IDS_MAX], "added": added[:IDS_MAX], "removed": removed, "off": off[:IDS_MAX]}


def touched(prop: dict, program, diff, t: float) -> bool:
    """The user changed the proposal tab's program (an edit, an undo / redo): ``edited`` again,
    a log entry when it differs from the AI's. Returns whether ``edited`` changed."""
    e = edited(prop, program, diff)
    if e == prop.get("edited"):
        _unapplied(prop, program)
        return False
    prop["edited"] = e
    _unapplied(prop, program)
    if e is not None:
        log(prop, "edited", "user", t)
    return True


def _unapplied(prop: dict, program) -> None:
    u = unapplied(prop, program)
    if u:
        prop["unapplied"] = u[:IDS_MAX]
    else:
        prop.pop("unapplied", None)


def edits_text(e: dict | None) -> str:
    """The user's edits in the AI's words: "changed s3, turned off s5"."""
    if not e:
        return ""
    if e.get("unknown"):
        return "changed it"
    parts = []
    for key, word in (("changed", "changed"), ("added", "added"), ("off", "turned off")):
        if e.get(key):
            parts.append(f"{word} {', '.join(e[key][:8])}" + (" ..." if len(e[key]) > 8 else ""))
    if e.get("removed"):
        parts.append(f"removed {e['removed']} step(s)")
    return ", ".join(parts)


# ---------------------------------------------------------------------------- the user's approval
def why_not(prop: dict, active) -> str | None:
    """Why the user's run of the proposal cannot be an approval, before anything is checked:
    draft | running | withdrawn (its status), empty (no step turned on: ``active`` is
    wb_plan.active of the program); None -- it can."""
    st = prop.get("status")
    if st in CANNOT:
        return st
    if not any(s.get("do") not in ("def", "proc") for s in active or ()):
        return "empty"
    return None


def refused(prop: dict, why: str, t: float, **kw) -> None:
    """The user's run did not start (``why``: why_not's, or check -- the pre-check found errors
    (``errors``), cp -- no restore point could be saved (``text``) --, error): nothing ran, the
    status stays."""
    prop["refused"] = {"why": why, "t": t, **{k: v for k, v in kw.items() if v is not None}}


def steps(program, active) -> dict:
    """What an approved run counts by: {"n": {sid: its number, as the check numbers the whole
    program}, "top": [the sids of the top-level steps that run, def / proc left out], "changing":
    the ones of them that change the model -- a value, a run, a save, the flowsheet, in their
    bodies or the procedure they call -- "off": [the outermost turned-off statements' sids]}."""
    n = {row["id"]: row["n"] for row in wb_plan.outline(program) if row.get("n")}
    procs = {s.get("name"): s for s in wb_plan._walk(active) if s.get("do") == "proc"}

    def changes(st, seen):
        for x in wb_plan._walk([st]):
            if x.get("do") in wb_plan.CHANGING or x.get("do") in wb_plan.STRUCTURE:
                return True
            if x.get("do") == "call" and x.get("name") in procs and x["name"] not in seen:
                if changes(procs[x["name"]], seen | {x["name"]}):
                    return True
        return False
    top = [s.get("id") for s in active or () if s.get("do") not in ("def", "proc")]
    off = []

    def walk(sts):
        for s in sts or ():
            if s.get("off") is True:
                off.append(s.get("id"))
                continue
            for key in wb_plan.NESTED:
                walk(s.get(key))
    walk(program)
    return {"n": n, "top": top, "changing": [s.get("id") for s in active or () if s.get("id") in top
                                             and changes(s, frozenset())], "off": off}


def approve(prop: dict, run: dict, t: float) -> None:
    """The approved run starts (its restore point kept, or skipped by the user): status running,
    ``run`` -- {"group", "model", "mode", "cp", "total", "off", ...} as the caller has them --
    with done 0, and the log's approved."""
    prop["run"] = {"group": None, "model": None, "mode": "run", "cp": None, "done": 0, "total": 0, "wrote": False,
                   "n": None, "failed_at": None, "failed_id": None, "error": None, "outcome": None, "off": 0,
                   "rev": prop.get("rev"), "edited": bool(prop.get("edited")), "t0": t, "t1": None, **run}
    prop["refused"] = None
    prop.pop("ran", None)
    prop.pop("unapplied", None)
    prop["status"] = "running"
    log(prop, "approved", "user", t)


def _sig(st: dict) -> str:
    """What a step does, as a short signature: its statement (and body) without ``off`` or ``why``."""
    bare = {k: v for k, v in _bare([st])[0].items() if k != "why"} if isinstance(st, dict) else st
    text = json.dumps(bare, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def ran_step(prop: dict, st: dict) -> None:
    """A top-level step of the approved run that changes the model finished: kept in ``run.applied``
    with its signature, so a revision can tell it applied and is unchanged (mark_ran)."""
    r = prop.get("run")
    if isinstance(r, dict) and isinstance(st, dict) and st.get("id"):
        r.setdefault("applied", {})[st["id"]] = _sig(st)


def kept(prop: dict, program, ends=("partial", "failed")) -> tuple[list, list]:
    """What the last approved run -- ended in ``ends``, not undone -- left applied of ``program`` (top
    level): (ran: the steps that applied then and are unchanged, not to run again; new: the ones that
    change the model and did not apply, or changed since). From the first new step on, an unchanged
    step runs again unless it only writes (a set, a structure step): a run, a sweep or a save after an
    edit works on the edited model. ([], []) when the run left none applied."""
    r = prop.get("run") if isinstance(prop.get("run"), dict) else {}
    done = r.get("applied") if r.get("end") in ends and not r.get("undone") else None
    if not isinstance(done, dict) or not done:
        return [], []
    changing = set(steps(program, wb_plan.active(program))["changing"])
    ran, new = [], []
    for st in program or ():
        if not isinstance(st, dict):
            continue
        sid = st.get("id")              # (signed as it ran: its turned-off body steps left out)
        same = sid in done and done[sid] == _sig(wb_plan.active([dict(st, off=False)])[0])
        if same and not (new and st.get("do") not in WRITES):
            ran.append(sid)
        elif not same and sid in changing:
            new.append(sid)
    return ran, new


def unapplied(prop: dict, program) -> list[str]:
    """The user's edits (``edited``) to an applied or partly applied proposal that its run did not
    apply: the changed and added statements in kept()'s new steps (those steps, when the edits are
    not known); [] otherwise."""
    e = prop.get("edited")
    if not e or prop.get("status") not in EDITS:
        return []
    new = kept(prop, program, EDITS)[1]
    if e.get("unknown"):
        return new
    mine = set(e.get("changed") or ()) | set(e.get("added") or ())
    return [x for st in program or () if isinstance(st, dict) and st.get("id") in new for x in _ids([st]) if x in mine]


def mark_ran(prop: dict, program) -> list[str]:
    """The AI revises a proposal whose last run ended partial or failed (not undone): the top-level
    steps of ``program`` (edited in place) that applied in that run and are unchanged (kept) are
    turned off -- running them again would place a block twice or write a value already written --
    and listed in ``ran`` for the window's mark. Returns their sids ([] when the last run left none)."""
    ran = kept(prop, program)[0]
    for st in program or ():
        if isinstance(st, dict) and st.get("id") in ran:
            st["off"] = True
    if ran:
        prop["ran"] = ran
    else:
        prop.pop("ran", None)
    return ran


def stepped(prop: dict, done: int, wrote: bool, at=None) -> None:
    """A top-level step of the approved run finished (``done`` so far; ``wrote``: one that
    changes the model has) -- or, ``at`` (n, sid), one is about to start."""
    r = prop.get("run")
    if isinstance(r, dict):
        r["done"], r["wrote"] = done, bool(wrote)
        if at is not None:
            r["n"], r["at"] = at


def finish(prop: dict, status: str, t: float, error: str | None = None, outcome: str | None = None) -> str:
    """The approved run ended (``status``: the program's, done | stopped | error; anything else --
    it never got to say, the server went away -- as stopped): applied, or partial when it stopped
    or failed after a step that changes the model had run, else stopped / failed; the failing
    step (``run.n``, ``run.at``) and ``error`` kept; ``outcome``: the last simulation run's (ok |
    warn | error). Returns the proposal's status."""
    r = prop.get("run") if isinstance(prop.get("run"), dict) else {}
    end = "applied" if status == "done" else "partial" if r.get("wrote") else \
        "failed" if status == "error" else "stopped"
    n, sid = r.pop("n", None), r.pop("at", None)
    r["n"] = None if end == "applied" else n          # the step it stopped or failed at
    if status == "error" and end != "applied":
        r["failed_at"], r["failed_id"] = n, sid
        r["error"] = " ".join(str(error or "").split())[:ERROR_TEXT] or None
    r.update(t1=t, outcome=outcome, end=end)
    prop["run"] = r
    prop["status"] = end
    log(prop, end, "user", t)
    return end


def stopped_at(prop: dict, sid, program_rev, mode) -> None:
    """The user stopped the approved run before (or during) top-level step ``sid`` -- or, run by
    group, it failed there --: ``run.resume``
    {"at", "n", "rev": the tab's program_rev, "mode": step | group | run} when a step before it
    finished, so the window can offer to continue from there, in the same mode (resumable)."""
    r = prop.get("run")
    if isinstance(r, dict) and sid and r.get("n") and int(r.get("done") or 0) > 0 \
            and prop.get("status") in ("partial", "stopped"):
        r["resume"] = {"at": sid, "n": r["n"], "rev": program_rev, "mode": mode if mode in ("step", "group") else "run"}


def resumable(prop: dict, program_rev, active) -> dict | None:
    """The stopped run's ``resume`` when the approval can continue from it: stopped (partial or
    stopped), not undone, the program as it was (``program_rev``), its step still a top-level
    step that runs (``active``: wb_plan.active of the program) and not the first; else None."""
    r = prop.get("run") if isinstance(prop.get("run"), dict) else {}
    res = r.get("resume")
    if prop.get("status") not in ("partial", "stopped") or not isinstance(res, dict) or r.get("undone"):
        return None
    if res.get("rev") != program_rev:
        return None
    top = [s.get("id") for s in active or () if s.get("do") not in ("def", "proc")]
    if res.get("at") not in top or top.index(res["at"]) == 0:
        return None
    return {"at": res["at"], "n": res.get("n"), "mode": res.get("mode") or "run"}


def dismiss(prop: dict, t: float) -> bool:
    """The user closes the proposal (the card's Close proposal): dismissed -- it does not run --,
    ``dismissed`` {t, was}, the log's dismissed. ValueError while it runs; False when it was
    dismissed already."""
    if prop.get("status") == "running":
        raise ValueError("running")
    if prop.get("status") == "dismissed":
        return False
    prop["dismissed"] = {"t": t, "was": prop.get("status")}
    prop["status"] = "dismissed"
    log(prop, "dismissed", "user", t)
    return True


def interrupted(prop: dict, t: float) -> None:
    """The server went away while the approved run ran: it ended there (stopped)."""
    if prop.get("status") == "running":
        finish(prop, "stopped", t)


def undone(prop: dict, how: str, t: float) -> None:
    """The user took the approved run back -- restore (the model put back to its restore point)
    or revert (its change group undone)."""
    r = prop.get("run")
    if isinstance(r, dict) and not r.get("undone"):
        r["undone"] = {"how": how, "t": t}
        prop.pop("unapplied", None)
        log(prop, "undone", "user", t)


def head(prop: dict) -> dict:
    """The approved run's change group header fields (journal.GROUPS.program): the proposal and
    the AI's group it was written in."""
    return {"proposal": prop.get("id"), "proposed_in": prop.get("proposed_in")}


def outcome(prop: dict) -> dict:
    """The approved run's end for its change group header (the AI's brief tells it): {"status",
    "done", "total", "n": the step it stopped or failed at, "error", "off", "edits": the user's
    edits in the AI's words, "rev", "outcome"}."""
    r = prop.get("run") or {}
    out = {"status": prop.get("status"), "done": r.get("done"), "total": r.get("total"), "n": r.get("n"),
           "error": r.get("error"), "off": r.get("off") or None, "rev": prop.get("rev"),
           "edits": edits_text(prop.get("edited"))[:160] or None, "outcome": r.get("outcome")}
    return {k: v for k, v in out.items() if v is not None}


# ---------------------------------------------------------------------------- the user's reply
def reject(prop: dict, text: str, t: float) -> dict:
    """The user sends the proposal back with ``text`` (may be empty): status rejected, ``reply``,
    the log's rejected. ValueError while it runs, or once the AI withdrew it."""
    if prop.get("status") == "running":
        raise ValueError("running")
    if prop.get("status") == "withdrawn":
        raise ValueError("withdrawn")
    prop["reply"] = {"text": " ".join(str(text or "").split("\n")).strip()[:REPLY_MAX], "t": t}
    prop["status"] = "rejected"
    log(prop, "rejected", "user", t)
    return prop["reply"]


def note(tab: dict, text: str, lang: str, t) -> dict:
    """The Ask AI note a rejection leaves (``target`` the proposal): the window's words, the
    user's comment kept as they wrote it (``comment``) for what the AI is told."""
    p = tab.get("proposal") or {}
    say_ = say(lang, "note_rejected" if text else "note_rejected0", title=p.get("title"), text=text)
    return {"id": "n" + uuid.uuid4().hex[:6], "target": {"kind": "proposal", "tab": tab.get("id"), "name": p.get("title")},
            "text": say_, "status": "open", "reply": "", "t": t, "tab": tab.get("id"), "proposal": p.get("id"),
            "comment": text}


def _in_root(root: dict | None) -> str:
    """", in model tab 'X' (id t...)" -- the model's tab a proposal is a sub-tab of -- or ""."""
    return f", in model tab '{root.get('title')}' (id {root.get('id')})" if isinstance(root, dict) else ""


def pushed(tab: dict, note_: dict, root: dict | None = None) -> str:
    """What the AI is told when the user sends its proposal back (the channel's text; ``root``: its
    model's tab). A proposal sent back goes to that tab's History; a revision reopens it."""
    p, tid = tab.get("proposal") or {}, tab.get("id")
    said = f": \"{note_['comment']}\"" if note_.get("comment") else " (no comment)"
    return (f"The user rejected your proposal '{p.get('title')}' (tab {tid}, rev {p.get('rev')}{_in_root(root)}){said}. "
            f"It is kept in the model tab's History. Revise it with workbench_edit(tab='{tid}', proposal={{...}}, "
            f"program=[...]) -- that reopens it --, or answer the note (note_replies, id {note_.get('id')}).")


def about(tab: dict) -> str:
    """What a note about the proposal is about, for the AI (workbench_read's target_text)."""
    p = tab.get("proposal") or {}
    reply = (p.get("reply") or {}).get("text")
    return (f"about your proposal '{p.get('title')}' (tab {tab.get('id')}, rev {p.get('rev')}, {p.get('status')})"
            + (f"; the user's comment: \"{reply}\"" if reply else ""))


# ---------------------------------------------------------------------------- checks and the AI's reads
def checked(prop: dict, check: dict | None, by: str, t: float) -> None:
    """A check (dry run) of the proposal tab left ``check`` (tab.check): logged."""
    if isinstance(check, dict):
        log(prop, "checked", by, t)


def check_summary(check: dict | None, program_rev: int) -> dict | None:
    """tab.check for the AI: {"ok", "errors", "warns", "current": it checked the program as it is
    now, "problems": [{"id", "n", "code", "level", "text"}] -- errors first, at most PROBLEMS_READ},
    or None (never checked)."""
    if not isinstance(check, dict):
        return None
    probs = []
    for row in check.get("steps") or []:
        for p in row.get("problems") or []:
            if p.get("level") in ("error", "warn"):
                probs.append({"id": row.get("id"), "n": row.get("n"), "code": p.get("code"), "level": p["level"],
                              "text": str(p.get("text") or "")[:PROBLEM_TEXT]})
    probs.sort(key=lambda p: p["level"] != "error")
    return {"ok": check.get("ok"), "errors": check.get("errors"), "warns": check.get("warns"),
            "current": check.get("rev") == program_rev, "problems": probs[:PROBLEMS_READ]}


def summary(tab: dict) -> dict:
    """A proposal tab in workbench_read's ``proposals``; ``unapplied``, ``watch`` and ``effects``,
    what the window's result tags show after its run (effects_brief), when there are any."""
    p = tab.get("proposal") or {}
    out = {"tab": tab.get("id"), "title": p.get("title"), "status": p.get("status"), "rev": p.get("rev"),
           "edited": p.get("edited"), "reply": p.get("reply"), "run": p.get("run"), "refused": p.get("refused"),
           "check": check_summary(tab.get("check"), tab.get("program_rev"))}
    if p.get("unapplied"):
        out["unapplied"] = p["unapplied"]
    if p.get("watch"):
        out["watch"] = p["watch"]
    fx = effects_brief((tab.get("run") or {}).get("effects"))
    if fx:
        out["effects"] = fx
        ex = p.get("explain")
        if isinstance(ex, dict) and ex.get("run") == fx.get("run"):     # (this run's, written)
            out["explained"] = [it.get("result") for it in ex.get("items") or []]
    return out


def effects_brief(fx) -> dict | None:
    """A run's effects for the AI: {"run", "joint_outside", "more", "items": [{path, b, a, u, goal}]}
    -- the numbers the window already tags (the AI's reply after the run should not repeat them)."""
    if not isinstance(fx, dict) or not fx.get("items"):
        return None
    return {"run": fx.get("run"), "joint_outside": fx.get("joint_outside"), "more": fx.get("more"),
            "items": [{k: it.get(k) for k in ("path", "b", "a", "u", "goal") if it.get(k) is not None}
                      for it in fx["items"]]}


def lane(prop) -> str:
    """"history" for a finished proposal (FINISHED), else "active"."""
    return "history" if isinstance(prop, dict) and prop.get("status") in FINISHED else "active"


def history_entry(tab: dict) -> dict:
    """A proposal tab's entry in its model's archive index and in state.json's ``history``: {"tab",
    "pid", "title", "status", "was"? (dismissed: the status before), "rev", "t0", "t", "group" (its
    approved run's change group), "cp" (its restore point), "undone", "steps", "session", "lane"}."""
    p = tab.get("proposal") if isinstance(tab.get("proposal"), dict) else {}
    r = p.get("run") if isinstance(p.get("run"), dict) else {}
    e = {"tab": tab.get("id"), "pid": p.get("id"), "title": p.get("title"), "status": p.get("status"),
         "rev": p.get("rev"), "t0": p.get("t0"), "t": p.get("t"), "group": r.get("group"),
         "cp": (r.get("cp") or {}).get("id") if isinstance(r.get("cp"), dict) else None,
         "undone": bool(r.get("undone")), "session": tab.get("session"), "lane": lane(p),
         "steps": sum(1 for s in tab.get("program") or () if isinstance(s, dict) and s.get("do") not in ("def", "proc"))}
    if p.get("status") == "dismissed":
        e["was"] = (p.get("dismissed") or {}).get("was")
    return e


def listing(tabs, root_id=None, session: str | None = None) -> list[dict]:
    """workbench_read's ``proposals``: the loaded proposal tabs of the model tab ``root_id`` (else,
    an older state, of ``session``) -- the active lane and the finished ones still loaded --, the
    latest changed first."""
    mine = [t for t in tabs if t.get("kind") == "proposal" and isinstance(t.get("proposal"), dict)
            and (t.get("parent") == root_id if root_id else t.get("session") == session)]
    mine.sort(key=lambda t: -(t["proposal"].get("t") or 0))
    return [summary(t) for t in mine[:READ_MAX]]


def history_listing(entries) -> list[dict]:
    """workbench_read's ``proposal_history``: the model's finished proposals (state.json
    ``history``), the latest first, at most HISTORY_READ, ``archived`` when not loaded."""
    out = []
    for e in sorted((e for e in entries or [] if isinstance(e, dict) and e.get("lane") == "history"),
                    key=lambda e: -(e.get("t") or 0))[:HISTORY_READ]:
        row = {k: e.get(k) for k in ("tab", "title", "status", "was", "rev", "t", "group", "undone") if e.get(k) is not None}
        row["archived"] = not e.get("loaded")
        out.append(row)
    return out


def closed_listing(history=()) -> list[dict]:
    """workbench_read's ``closed_proposals``: the model's dismissed proposals (its ``history``
    entries), the latest first."""
    keys = ("tab", "title", "rev", "status", "was", "t")
    return [{k: e.get(k) for k in keys} for e in sorted(
        (e for e in history or () if isinstance(e, dict) and e.get("status") == "dismissed"),
        key=lambda e: -(e.get("t") or 0))][:CLOSED_READ]


# ---------------------------------------------------------------------------- the AI's answers
def refusal(tab: dict) -> str:
    """workbench_run(dry_run=False) on a proposal tab."""
    return (f"Error: tab '{tab.get('title')}' is a proposal: only the user can run it (that is the approval). "
            f"workbench_run(tab='{tab.get('id')}', dry_run=True) checks it.")


def answer(tab: dict, what: str, replaced=None, checking: bool = False, root: dict | None = None) -> str:
    """workbench_edit's sentence about the proposal (``what``: proposed | revised | withdrawn;
    ``root``: the model's tab it is a sub-tab of, named in it)."""
    p, tid = tab.get("proposal") or {}, tab.get("id")
    if what == "withdrawn":
        return (f"Proposal '{p.get('title')}' on tab '{tab.get('title')}' (id {tid}{_in_root(root)}) is withdrawn; "
                "it goes to the model tab's History.")
    head = f"Proposal '{p.get('title')}' is on tab '{tab.get('title')}' (id {tid}, rev {p.get('rev')}{_in_root(root)})"
    if p.get("status") == "draft":
        text = (f"{head}, saved as a draft: the user cannot approve it yet. When it is done: "
                f"workbench_edit(tab='{tid}', proposal={{\"status\": \"ready\"}}).")
    else:
        text = (f"{head}, waiting for the user's review; the user approves it by running it in the window. Do not "
                f"run it yourself: workbench_run(tab='{tid}') with dry_run=True checks it.")
        if checking:
            text += " A check is starting now; workbench_read shows its result (proposals[].check)."
    if replaced:                        # (an insert went on top of their edits, a whole program replaced them)
        text += (f" The user had edited rev {int(p.get('rev') or 1) - 1} ({edits_text(replaced)}); rev {p.get('rev')} "
                 "is the program as your edit left it -- their version is one undo away in the window.")
    return text


# ---------------------------------------------------------------------------- the window's chat lines
_SAY = {
    "proposed": ("The AI proposed \"{title}\": nothing changes until it is approved.",
                 "AI 提出提案「{title}」：核准前模型不會變更。"),
    "drafted": ("Proposal \"{title}\" is a draft: it cannot be approved yet.",
                "提案「{title}」為草稿，尚不能核准。"),
    "revised": ("The AI revised the proposal (rev {rev}).", "AI 改寫了提案（第 {rev} 版）。"),
    "revised_mine": ("The AI revised the proposal (rev {rev}); earlier edits are in undo (↶).",
                     "AI 改寫了提案（第 {rev} 版）；先前的修改可用 ↶ 找回。"),
    "ready": ("Proposal complete, awaiting review.", "提案已完成，待審核。"),
    "withdrawn": ("The AI withdrew this proposal.", "AI 撤回了這份提案。"),
    # the user's approval (why_not, the pre-check, the restore point, the end)
    "not_draft": ("This proposal is still a draft: it cannot be approved yet.", "提案仍為草稿，尚不能核准。"),
    "not_running": ("This proposal is running already.", "這份提案已經在執行了。"),
    "not_withdrawn": ("The AI withdrew this proposal: it cannot be run.", "AI 已經撤回這份提案，不能執行。"),
    "not_empty": ("Nothing to run: every step is turned off.", "沒有要執行的步驟：每一步都停用了。"),
    "not_dismissed": ("This proposal was closed: it cannot be run.", "提案已關閉，不能執行。"),
    "not_resume": ("Cannot continue from where it stopped: the proposal changed since, or was taken back. "
                   "Nothing was run.", "無法從停止處繼續：提案已變更或已收回。未執行任何步驟。"),
    "not_check": ("Not run: the check found {n} problem(s) (listed in the run log). No restore point was created "
                  "and the model was not changed; fix them, then approve again.",
                  "未執行：檢查發現 {n} 個問題（見執行紀錄）。未建立還原點，模型未變更；修正後再核准。"),
    "not_cp": ("Not run: a restore point could not be created ({why}). The model was not changed. To run it anyway, "
               "choose \"Run without a restore point\".",
               "未執行：無法建立還原點（{why}），模型未變更。仍要執行請選「不存還原點，直接執行」。"),
    "approved": ("Approved: restore point created; running {n} step(s).",
                 "已核准：已建立還原點，開始執行 {n} 步。"),
    "approved_nocp": ("Approved without a restore point; running {n} step(s).",
                      "已核准（未建立還原點），開始執行 {n} 步。"),
    "approved_resume": ("Approved again: continuing from step {n}; the {done} step(s) already applied are not "
                        "run again. The restore point from the first approval is kept.",
                        "再次核准：從第 {n} 步繼續；已套用的 {done} 步不重複執行，沿用第一次核准的還原點。"),
    "resume_skipped": ("Not run again (applied before the stop): {n} step(s): {ids}",
                       "不重複執行（停止前已套用）：{n} 步：{ids}"),
    "approved_edits": ("Approved your changes: restore point created; the {done} step(s) already applied and "
                       "unchanged are not run again.", "已核准你的修改：已建立還原點；已套用且未改動的 {done} 步不重複執行。"),
    "edits_skipped": ("Not run again (applied and unchanged): {n} step(s): {ids}",
                      "不重複執行（已套用且未改動）：{n} 步：{ids}"),
    "off_skipped": ("Skipping {n} turned-off step(s): {ids}", "略過 {n} 個停用的步驟：{ids}"),
    "applied": ("Applied: all {n} step(s) ran; they can be taken back as one group, or the model restored to "
                "before the proposal.", "已套用：{n} 步全部執行；可整組收回，或還原到提案之前。"),
    "applied_nocp": ("Applied: all {n} step(s) ran; they can be taken back as one group.",
                     "已套用：{n} 步全部執行；可整組收回。"),
    "failed_at": ("Step {n} failed: {why}. The {done} step(s) before it were applied.",
                  "第 {n} 步失敗：{why}。前面 {done} 步已套用。"),
    "failed_none": ("Step {n} failed: {why}. Nothing was applied.", "第 {n} 步失敗：{why}。未套用任何變更。"),
    "failed_resume": (" Once its cause is put right, the run can continue from step {n}.", "排除原因後，可從第 {n} 步繼續。"),
    "stopped_at": ("Stopped before step {n}; the {done} step(s) before it were applied.",
                   "於第 {n} 步前停止；前 {done} 步已套用。"),
    "stopped_none": ("Stopped before step {n}; nothing was applied.", "於第 {n} 步前停止；未套用任何變更。"),
    # the user's reply
    "rejected": ("Proposal sent back; comment sent to the AI.", "已退回提案，意見已送出。"),
    "reject_running": ("The proposal is running: stop it before sending it back.", "提案正在執行：先停止再退回。"),
    "reject_withdrawn": ("The AI withdrew this proposal already.", "AI 已經撤回這份提案了。"),
    "dismissed": ("Proposal closed; it will not run. It is kept in History.", "已關閉提案，不會執行；已收進歷史提案。"),
    "dismiss_running": ("The proposal is running: stop it before closing it.", "提案正在執行：先停止再關閉。"),
    "note_rejected": ("Sent back the proposal \"{title}\": {text}", "退回提案「{title}」：{text}"),
    "note_rejected0": ("Sent back the proposal \"{title}\"", "退回提案「{title}」"),
}


def end_text(prop: dict, lang: str) -> str:
    """The chat line of the approved run's end, in the window's words."""
    r, st = prop.get("run") or {}, prop.get("status")
    if st == "applied":
        return say(lang, "applied" if (r.get("cp") or {}).get("id") else "applied_nocp", n=r.get("done") or 0)
    n, done = r.get("n") or "?", r.get("done") or 0
    if r.get("failed_at") is not None or st == "failed":
        text = say(lang, "failed_at" if st == "partial" else "failed_none", n=n, done=done, why=r.get("error") or "?")
        res = r.get("resume")                             # (a run by group that failed part way)
        return text + say(lang, "failed_resume", n=res.get("n") or n) if isinstance(res, dict) else text
    return say(lang, "stopped_at" if st == "partial" else "stopped_none", n=n, done=done)


def say(lang: str, key: str, **kw) -> str:
    en, zh = _SAY[key]
    return (zh if lang == "zh" else en).format(**kw)
