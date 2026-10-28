"""Restore points: a copy of a model kept before a change its journal cannot undo value by
value -- a change group's first structural change, an optimization, a proposal's run, a
restore -- and the named ones a person saves.

    rp = restore_points.ensure(manager, "demo", "before-structure", group=g, tool="place_block")
    rp["status"]   dedup | reused | copied | exported | skipped | failed
    rp["note"]     "" -- or, when none was made, the line a tool result adds for the AI

``ensure`` takes the first tier that holds:

1 reuse   Nothing changed since this model's last restore point (one this process made, still
          on disk): the journal's ``marks`` -- its latest input record and latest record from
          Aspen's window -- are what they were then, and nothing is pending in the current
          scope. Journals {"op": "checkpoint", "reuse": id, "cp_reason"} ("reason" is the AI's).
2 copy    The model is what its file holds: the file's size and mtime are those the server last
          loaded or wrote (the manager's stamp, or the registry's ``written``) and the journal
          has no input record since that stamp (same ``marks``) -- or no net change since its
          last sync point (``unsaved`` n == 0) and nothing from Aspen's window after it.
          ``checkpoints.backup_file``: a file copy, seconds even for a big model. state "saved".
3 export  ``Export(1)`` of the live model when ``estimate`` is at most ``max_s()``
          (ASPEN_MCP_CHECKPOINT_MAX_S, default 15 s), or when the caller allows a slow one (a
          named point; a restore the user asked to keep). state "live". It runs as an activity
          -- tool "checkpoint", phase "aspen", target {"reason", "est_s"} -- so the workbench
          header counts "saving a restore point 42 s / about 2 min" while COM holds the event
          loop: the beacon thread keeps writing the heartbeat (pywin32 lets go of the GIL).
5 skip    Journals {"op": "checkpoint", "status": "skipped", "why": "slow", "est_s", "cp_reason"}
          and hands back ``note`` for the AI. Also why "failed" (a BackupError) and "no_session".
(4, an input-only export, is not done: Export(4) takes 0.01 s even on the heavy model, but the
.inp opened again lost unit sets, a prop-set's inputs, block icons and table settings.)

One restore point per (model, change group): a group's later structural changes reuse its
first one (``dedup``, nothing journaled). Before a close (``NOT_IF_SAVED``) a model that is
what its file holds needs none: skipped, why "saved", nothing journaled. ``plan`` answers
which tier ``ensure`` would take now, doing nothing (a confirmation card's line).
Without the journal (ASPEN_MCP_JOURNAL=0) nothing tells "unchanged": tiers 3 and 5 only.
Edits made in Aspen's own window that the external-change check did not find are not in a tier-2 copy -- V15 has no
"modified" flag to ask, neither on the document nor in the window title.

``estimate``: the model's last Export(1) time when there is one, else BASE_S + size / RATE_BPS
+ K_ROWS x (its sensitivities' cases, squared; from the .bkp text and the journal) -- see the
constants. A sensitivity made and run in Aspen's window and never saved is not seen until then.
The cases count only while the model holds results (``held``): V15 drops a run's results at the
first input edit after it, and an Export of the 20000-case model then takes 0.02 s, not 128 s
-- so after an edit, a reinit, the estimate is the size's alone, and an
export's time measured with results is not one measured without (the event's ``results``).

Stdlib only; COM only through the app the manager hands out (Export, in tools/checkpoints) --
the estimate reads none (see K_ROWS). Never raises: a failure is a result, and the tool it
protects runs anyway.
"""
from __future__ import annotations

import contextlib
import logging
import os
import re
import threading
import time

from tools import activity, checkpoints, journal, model_registry, recorder

logger = logging.getLogger(__name__)

MAX_S = 15.0                  # the longest an automatic restore point may take (s), unless...
ENV_MAX = "ASPEN_MCP_CHECKPOINT_MAX_S"
# What Export(1) costs, live V15. Not the file's size alone: models of 1.2 MB, 1.0 MB and
# 0.16 MB took 0.86 s, 0.57 s and 0.60 s (a session's first
# export; 0.05-0.25 s the next), but a Flash2 with a sensitivity of 5000 cases 0.58 MB 7.3 s,
# 10000 cases 1.1 MB 29.7 s, 20000 cases 2.1 MB 128 s: the time grows with the square of a
# sensitivity's cases (3.0-3.2e-7 s per case squared). So an estimate is BASE_S + size /
# RATE_BPS + K_ROWS x the sum over the model's sensitivities of their cases squared -- each
# term rounded long. The cases are NOT read through COM: the first touch of a sensitivity
# object after a run (FindNode, Elements.Item, anything) makes Aspen load its results, as
# long as the export itself (5000 cases 7.0 s) -- so they come from the model file's input
# text and the journal's newer NPOINT values.
BASE_S = 1.0
RATE_BPS = 500_000.0          # a third of the slowest rate measured
# Restoring one in place closes Aspen (~2.5 s until its process is gone), starts a new one
# and loads the file -- as long as an Export (127 s for the 20000-case model): live
# V15, 7.3-8.6 s in all for two models whose Exports take under 1 s.
RESTORE_BASE_S = 7.0
K_ROWS = 4.0e-7               # s per case squared (3.0-3.2e-7 measured)
GROUPS_MAX = 256              # (model, group) pairs remembered for dedup
SCAN = 500                    # journal records looked through for sensitivity inputs, for results
PAGE = 64                     # ... read that many at a time for results (the first that says ends it)
COPY_BPS = 50_000_000.0       # a file copy (tier 2), for plan(): seconds even for a big model
NOT_IF_SAVED = frozenset({"before-close"})    # none needed while the model is what its file holds

_lock = threading.Lock()
_last: dict = {}              # model -> {"id", "marks"}: the latest restore point made here
_groups: dict = {}            # (model, group id) -> restore point id
_PARA = re.compile(r"\?\s*SENSITIVITY\s+(\S+)\s*\?(.*?)(?=\?\s*[A-Z]|\Z)", re.S)
_NPOINT = re.compile(r'\bNPOINT\s*=\s*"?\s*(\d+)')
_RANGE = re.compile(r'\bLOWER\s*=\s*"?\s*([-+.\dEeDd]+)"?\s+UPPER\s*=\s*"?\s*([-+.\dEeDd]+)"?(?:\s+NPOINT\s*=\s*"?\s*'
                    r'(\d+)"?)?(?:\s+INCR\s*=\s*"?\s*([-+.\dEeDd]+))?')
_JPATH = re.compile(r"\\Model Analysis Tools\\Sensitivity\\([^\\]+)\\Input\\(NPOINT|LOWER|UPPER|INCR)\\#(\d+)$", re.I)
_SAME = frozenset({"unchanged", "failed", "refused", "error"})   # a record that changed nothing (journal's)
_EDITS = frozenset({"value", "attr", "add", "remove", "connect"})
_ON = object()                # a record that says nothing of the results: look further back


def max_s() -> float:
    """ASPEN_MCP_CHECKPOINT_MAX_S (seconds; read at every call), else MAX_S."""
    try:
        v = float(os.environ.get(ENV_MAX, ""))
        return v if v >= 0 else MAX_S
    except ValueError:
        return MAX_S


def say_secs(s) -> str:
    """A duration as a tool result says it: "3 s", "2 min"."""
    if not isinstance(s, (int, float)):
        return "an unknown time"
    return f"{max(1, round(s))} s" if s < 90 else f"{round(s / 60)} min"


def _f(x):
    try:
        v = float(str(x).replace("D", "E").replace("d", "e"))
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _points(v: dict) -> int:
    """One varied variable's cases: NPOINT + 1, else (UPPER - LOWER) / INCR + 1, else 1."""
    n = _f(v.get("NPOINT"))
    if n is None:
        lo, up, inc = (_f(v.get(k)) for k in ("LOWER", "UPPER", "INCR"))
        n = abs(up - lo) / inc if None not in (lo, up, inc) and inc else 0
    return int(n) + 1


def _file_sensitivities(path) -> dict:
    """{name: {k: {"NPOINT", "LOWER", "UPPER", "INCR"}}} of the sensitivities a .bkp defines
    (its input text: "? SENSITIVITY S1 ? ... VARY ... LOWER = "60" UPPER = "95" NPOINT = "400""
    -- one VARY a row). Another kind of file (.apw), or none: {}."""
    if not path or os.path.splitext(str(path))[1].lower() != ".bkp":
        return {}
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("latin-1")
    except OSError:
        return {}
    out = {}
    for m in _PARA.finditer(text):
        rows = {}
        for k, r in enumerate(_RANGE.finditer(m.group(2))):
            rows[k] = {"LOWER": r.group(1), "UPPER": r.group(2), "NPOINT": r.group(3), "INCR": r.group(4)}
        if not rows:
            rows = {k: {"NPOINT": n} for k, n in enumerate(_NPOINT.findall(m.group(2)))}
        out[m.group(1).upper()] = rows
    return out


def _journal_sensitivities(model_id, into: dict) -> None:
    """Values from the journal: each sensitivity input (NPOINT, LOWER, UPPER, INCR of row #k)
    as last written, over the latest SCAN records -- also sensitivities the file does not have
    yet; an NPOINT smaller than the file's is not taken (the file may have been saved since)."""
    seen = set()
    for r in journal.read(model_id, limit=SCAN, kinds=("change",)) or ():
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        paths = [(tg.get("path"), r.get("after"), r.get("status"))] if r.get("op") == "value" else [
            (p, w.get("after"), w.get("status")) for p, w in (r.get("writes") or {}).items() if isinstance(w, dict)] \
            if isinstance(r.get("writes"), dict) else []
        for p, after, st in paths:
            m = _JPATH.search(str(p or ""))
            if not m or st != "changed" or not isinstance(after, dict):
                continue
            key = (m.group(1).upper(), int(m.group(3)), m.group(2).upper())
            if key in seen:
                continue
            seen.add(key)
            row = into.setdefault(key[0], {}).setdefault(key[1], {})
            v, was = after.get("value"), _f(row.get(key[2]))
            if key[2] == "NPOINT" and was is not None and (_f(v) is None or _f(v) < was):
                continue                          # the file may be newer: the larger count stands
            row[key[2]] = v


def result_rows(model_id, path) -> int | None:
    """The sum over the model's sensitivities of their cases squared -- what makes Export(1)
    slow -- from the model file's input text and the journal's newer values; None when the
    file cannot be read as .bkp text and the journal has none."""
    try:
        sens = _file_sensitivities(path)
        if model_id and journal.enabled():
            _journal_sensitivities(model_id, sens)
        if not sens and not (path and str(path).lower().endswith(".bkp")):
            return None
        total = 0
        for rows in sens.values():
            cases = 1
            for v in rows.values():
                cases *= _points(v)
            total += cases * cases
        return total
    except Exception as exc:
        logger.debug("restore point: sensitivity cases not counted (%r)", exc)
        return None


def _ran(runs) -> int:
    """A loop's runs that ran (journal's): all but the refused and failed ones."""
    try:
        return max(0, int(runs.get("n") or 0) - int(runs.get("refused") or 0) - int(runs.get("failed") or 0))
    except (AttributeError, TypeError, ValueError):
        return 0


def _says(r: dict, model_id=None):
    """What one record (the journal's, or one a scope holds yet) says of the results the model
    holds after it: True, a run that ran -- its results; False, cleared -- an input changed
    (value, attribute, a block added or removed, a connection, a loop's writes that no run
    followed) or a reinit; None, not known -- the model loaded from a file (an open, a file
    edit, a restore to a point whose results are not known: a file copy's) or a loop whose end
    is not; _ON: nothing (a save, a checkpoint, a refused or failed call)."""
    op, st = r.get("op"), r.get("status")
    if op == "run":                                         # ("unknown": it ran, its status unread)
        return True if st in journal.RAN or st == "unknown" else _ON
    if op == "reinit":
        return _ON if st in ("refused", "failed") else False
    tg = r.get("target") if isinstance(r.get("target"), dict) else {}
    if op == "restore" and tg.get("checkpoint"):          # the model put back to a restore point
        if st in _SAME:
            return None if r.get("reopened") else _ON
        cp = checkpoints.get(model_id, str(tg["checkpoint"])) if model_id else None
        if cp is not None:                                  # the point's own: an export's (a copy: its file's)
            return _had(cp) if cp.get("source") == "export" else None
        return True if r.get("fresh") is True else None
    if op in ("summary", "restore"):                        # a loop, an optimization, a program's restore
        if _ran(r.get("runs")):
            rep = r.get("report") if isinstance(r.get("report"), dict) else {}
            return True if not rep or rep.get("state") == "last" or rep.get("run") in journal.RAN else None
        ws = r.get("writes") if isinstance(r.get("writes"), dict) else {}
        ops = r.get("ops") if isinstance(r.get("ops"), dict) else {}
        edited = any(isinstance(w, dict) and (w.get("status") == "changed" or (
            w.get("status") is None and w.get("before") != w.get("after"))) for w in ws.values())
        return False if edited or any(o in _EDITS for o in ops) else _ON
    if op in ("open", "patch"):
        return None if st not in _SAME else _ON
    if op in _EDITS:
        return False if st not in _SAME else _ON
    return _ON


def _scope_says(model_id):
    """``_says`` over the current recording scope's records not in the journal yet, newest
    first (a batch's earlier writes, before the call's flush); a loop's (an Aggregate: writes
    and runs counted, their order not kept) that edited or ran: None."""
    cur = recorder.current()
    while cur is not None:
        cur = getattr(cur, "_join", None) or cur
        if getattr(cur, "model", None) not in (None, model_id):
            return _ON
        if isinstance(cur, recorder.Aggregate):
            if _ran(cur.runs) or any(e.get("n", 0) > e.get("failed", 0) for e in cur._p.values()) or \
                    any(_says({"op": o}) is not _ON for o in cur.ops):
                return None
            cur = cur._parent
            continue
        for p in reversed(getattr(cur, "_pend", ())):
            r = p if isinstance(p, dict) else {"op": getattr(p, "op", None), "status": getattr(p, "status", None)}
            if r.get("model") not in (None, model_id):
                continue
            v = _says(r, model_id)
            if v is not _ON:
                return v
        return _ON
    return _ON


def held(model_id) -> bool | None:
    """Whether the live model holds results -- what makes Export(1) slow: the first record
    that says (``_says``) among the current scope's pending ones, then the journal's newest
    first (up to SCAN; beyond, its ``stale`` table: an input changed since the last run ->
    False). None: not known -- no journal, or nothing says (the model as loaded from its file,
    whose results are the file's). No COM."""
    if not model_id or not journal.enabled():
        return None
    try:
        v = _scope_says(model_id)
        if v is not _ON:
            return v
        before, n = None, 0
        while n < SCAN:
            page = journal.read(model_id, limit=PAGE, before=before, kinds=("change",)) or []
            for r in page:
                v = _says(r, model_id)
                if v is not _ON:
                    return v
            if len(page) < PAGE:
                break
            n, before = n + len(page), page[-1]
        st = (journal.summary(model_id) or {}).get("stale")
        return False if isinstance(st, dict) and (st.get("n") or st.get("more")) else None
    except Exception as exc:
        logger.debug("restore point: results not judged (%r)", exc)
        return None


def _had(ev) -> bool | None:
    """Whether an export's model held results then: its ``results``; an older event without that,
    its ``fresh`` (results in step with the inputs)."""
    if not isinstance(ev, dict):
        return None
    for k in ("results", "fresh"):
        if isinstance(ev.get(k), bool):
            return ev[k]
    return None


def estimate(model_id: str, path=None) -> dict:
    """How long Export(1) of this model is expected to take: {"s", "how", "size", "rows2",
    "results" (``held``; left out when not known)}. ``how`` "last": the model's last export took
    that long -- a measurement of this very model, in the same state (with results or without)
    -- scaled up by the file's growth, plus (with results) K_ROWS x the growth of ``rows2``
    (``result_rows``) since; "size": no such export, BASE_S + size / RATE_BPS, + K_ROWS x rows2
    unless the results were cleared (then never more than the last export with them); None:
    nothing is known. No COM (see K_ROWS)."""
    return _estimate(model_id, path, held(model_id))


def _estimate(model_id, path, results) -> dict:
    size = None
    try:
        if path:
            size = os.path.getsize(path)
    except OSError:
        size = None
    rows2 = result_rows(model_id, path)
    last = checkpoints.last_export(model_id) if model_id else None
    out = {"size": size, "rows2": rows2}
    if results is not None:
        out["results"] = results
    full = None
    if last:
        had = _had(last)
        s = float(last["secs"])
        was = last.get("size")
        if size and isinstance(was, (int, float)) and was > 0 and size > was:
            s *= size / was
        if results is False and had is False:                 # measured without results too
            return {"s": round(s, 2), "how": "last", **out}
        if had is not False:                                  # measured with results (or not known)
            if rows2:
                then = last.get("rows2")
                s = s + K_ROWS * max(0, rows2 - then) if isinstance(then, (int, float)) else max(s, K_ROWS * rows2)
            if results is not False:
                return {"s": round(s, 2), "how": "last", **out}
            full = s
    if size or rows2:
        s = BASE_S + (size or 0) / RATE_BPS + (0.0 if results is False else K_ROWS * (rows2 or 0))
        if full is not None and full < s:                     # cleared: no longer than with results
            return {"s": round(full, 2), "how": "last", **out}
        return {"s": round(s, 2), "how": "size", **out}
    if full is not None:
        return {"s": round(full, 2), "how": "last", **out}
    return {"s": None, "how": None, **out}


def _point_held(model_id, path) -> bool | None:
    """Whether the restore point at ``path`` holds results: an export's ``_had``; a file copy's
    (or a point not found): not known."""
    try:
        k = os.path.normcase(os.path.abspath(str(path)))
        cp = next((c for c in checkpoints.list_checkpoints(model_id)
                   if c.get("path") and os.path.normcase(os.path.abspath(c["path"])) == k), None)
    except Exception:
        return None
    return _had(cp) if cp and cp.get("source") == "export" else None


def restore_estimate(model_id: str, path=None) -> float | None:
    """How long restoring the restore point at ``path`` in place is expected to take (s):
    RESTORE_BASE_S + the estimate of an Export of it (the load takes about as long) -- with the
    point's results, not the live model's (``_point_held``). No COM."""
    s = _estimate(model_id, path, _point_held(model_id, path) if model_id and path else None).get("s")
    return round(RESTORE_BASE_S + (s or 0.0), 1) if s is not None or path else None


# ---------------------------------------------------------------------------- is it the file?
def _gid(group):
    return group.get("id") if isinstance(group, dict) else group


def _dirty_scope() -> bool:
    """Whether the current recording scope holds a change not yet in the journal (a program
    statement's writes before its flush; a loop's)."""
    cur = recorder.current()
    while cur is not None:
        cur = getattr(cur, "_join", None) or cur
        if isinstance(cur, recorder.Aggregate):
            if any(e.get("n", 0) > e.get("failed", 0) for e in cur._p.values()) or cur.ops:
                return True
            cur = cur._parent
            continue
        for p in getattr(cur, "_pend", ()):
            op = p.get("op") if isinstance(p, dict) else getattr(p, "op", None)
            st = p.get("status") if isinstance(p, dict) else getattr(p, "status", None)
            if op in journal.INPUT_OPS and st not in ("unchanged", "failed", "refused", "error"):
                return True
        return False
    return False


def marks(s: dict | None) -> list | None:
    """What "nothing changed since" compares: the journal's latest input record time and its
    latest record of an edit found made in Aspen's window -- the same two numbers until a new
    such record comes (records only, no clock to compare). None without a summary."""
    return None if not isinstance(s, dict) else [s.get("last_input_t"), (s.get("ext") or {}).get("t")]


def _unchanged(s: dict, then) -> bool:
    """The live model is what its file holds, as far as the journal knows: no input record at
    all, none since the manager last loaded / wrote the file (``then``: its ``marks`` then), or
    no net change since the journal's last sync point and nothing from Aspen's window after it."""
    now = marks(s)
    if now == [None, None] or (then is not None and then == now):
        return True
    un, ext = s.get("unsaved") or {}, now[1]
    if un.get("since") is None or (ext is not None and ext > un["since"]):
        return False
    return un.get("n") == 0 and not un.get("more")


def _file_is_known(manager, session, model_id, path) -> tuple[bool, list | None]:
    """(the file is as the server last loaded or wrote it, the journal's ``marks`` then --
    None when only the registry's ``written`` vouches for the file)."""
    try:
        st = os.stat(path)
    except OSError:
        return False, None
    stamp = manager.opened(session) if hasattr(manager, "opened") else None
    k = model_registry.key(path)
    if stamp and model_registry.key(stamp["path"]) == k and \
            (stamp["size"], stamp["mtime_ns"]) == (st.st_size, st.st_mtime_ns):
        return True, stamp.get("marks")
    rec = model_registry.get(model_id) or {}
    w = rec.get("written") or {}
    ok = bool(rec.get("path")) and model_registry.key(rec["path"]) == k and \
        (w.get("size"), w.get("mtime_ns")) == (st.st_size, st.st_mtime_ns)
    return ok, None


def _is_file(manager, session, model, path, s: dict) -> bool:
    """The live model is what its file holds (tier 2's test): nothing a restore point would add."""
    known, then = _file_is_known(manager, session, model, path)
    return known and _unchanged(s, then)


def _fresh(s: dict | None):
    """Whether the results were in step with the inputs (None: unknown)."""
    if not s:
        return None
    if s.get("last_run_t") is None:
        return False if s.get("n") else None
    st = s.get("stale")
    if isinstance(st, dict):
        return st.get("n") == 0 and not st.get("more")
    return s.get("last_input_t") is None or s["last_run_t"] >= s["last_input_t"]


# ---------------------------------------------------------------------------- ensure / make
@contextlib.contextmanager
def _scope(manager, actor, via, session, model, group, tool):
    """The current recording scope (its call's records), or one of our own."""
    cur = recorder.current()
    if cur is not None:
        yield cur
        return
    with recorder.scope(actor=actor, via=via, session=session, model=model, group=group, tool=tool) as s:
        s.manager = manager
        yield s


def _note(why, est=None, err=None) -> str:
    if why == "slow":
        return (f"(No restore point was made before this change: saving one of this model takes about "
                f"{say_secs(est)}. The user can save one from the workbench.)")
    if why == "failed":
        return (f"(No restore point was made before this change: {err}. The user can save one from "
                "the workbench.)")
    return ""


def ensure(manager, session: str, reason: str, *, group=None, allow_slow: bool = False,
           actor: str | None = None, via: str | None = None, tool: str | None = None,
           name: str | None = None, reuse: bool = True, max_seconds: float | None = None) -> dict:
    """Make sure a restore point of ``session``'s model holds it as it is now -- the tiers in
    the module docstring. ``reason``: before-structure | before-optimize | before-proposal |
    before-restore | before-patch | manual; ``group``: the change group (dedup, event field);
    ``name``: a named (permanent) one, which is always a new copy; ``actor`` / ``via`` default
    to the current scope's. Returns {"status", "id", "tier", "state", "secs", "est_s", "why",
    "note", "warning"} (keys that apply). Never raises."""
    try:
        return _ensure(manager, session, reason, _gid(group), allow_slow, actor, via, tool, name,
                       reuse and not name, max_seconds)
    except Exception as exc:
        logger.warning("restore point before %s of %s failed: %r", reason, session, exc, exc_info=True)
        return {"status": "failed", "why": "failed", "error": str(exc), "note": _note("failed", err=exc)}


def make(manager, session: str, name: str | None = None, *, actor: str = "user", via: str = "window",
         tool: str = "checkpoint", group=None) -> dict:
    """A named restore point, kept for good (the workbench's "Save restore point..."): a file
    copy when the model is its file, else Export(1) however long it takes."""
    return ensure(manager, session, "manual", name=name or time.strftime("restore point %H:%M"),
                  allow_slow=True, actor=actor, via=via, tool=tool, group=group)


def plan(manager, session: str, reason: str, *, group=None, allow_slow: bool = False) -> dict:
    """What ``ensure`` would do for a call about to run -- nothing made, nothing journaled, no
    COM: a confirmation card's "a restore point first". {"tier": "dedup" (its
    change group's own, made earlier) | "reuse" (the latest, still the model) | "copy" (the
    model is its file) | "export" | "skip" (too slow; ``slow_s``: what one would take if the
    user asks for it) | "none" (``why`` "saved": a close of a model its file holds, or
    "no_session"), "est_s": seconds it adds to the call (a copy's or an export's, else 0; None
    when an export's is not known), "id" / "t": the restore point reused}. ensure's order, and its
    ``estimate`` -- results-aware (``held``): after an edit or a reinit, the size's alone."""
    try:
        return _plan(manager, session, reason, _gid(group), allow_slow)
    except Exception as exc:
        logger.warning("restore point plan before %s of %s failed: %r", reason, session, exc)
        return {"tier": None, "why": "failed", "est_s": 0.0}


def _plan(manager, session, reason, gid, allow_slow) -> dict:
    path = manager.session_file(session) if session else None
    model = manager.model_id(session) if path else None
    if not path or not model:
        return {"tier": "none", "why": "no_session", "est_s": 0.0}
    with _lock:
        cid, last = _groups.get((model, gid)) if gid else None, _last.get(model)
    cp = checkpoints.get(model, cid) if cid else None
    if cp is not None:
        return {"tier": "dedup", "id": cid, "t": cp.get("t"), "est_s": 0.0}
    on = journal.enabled()
    s = (journal.summary(model) or {}) if on else {}
    dirty = _dirty_scope()
    now = marks(s) if on else None
    if reason in NOT_IF_SAVED and on and not dirty and _is_file(manager, session, model, path, s):
        return {"tier": "none", "why": "saved", "est_s": 0.0}
    cp = checkpoints.get(model, last["id"]) if on and last and not dirty and now is not None \
        and last["marks"] == now else None
    if cp is not None:
        return {"tier": "reuse", "id": last["id"], "t": cp.get("t"), "est_s": 0.0}
    if on and not dirty and _is_file(manager, session, model, path, s):
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        return {"tier": "copy", "est_s": round(0.1 + size / COPY_BPS, 1)}
    est = estimate(model, path)
    if not allow_slow and est["s"] is not None and est["s"] > max_s():
        return {"tier": "skip", "why": "slow", "slow_s": est["s"], "est_s": 0.0}
    return {"tier": "export", "est_s": est["s"], "how": est["how"]}


def _ensure(manager, session, reason, gid, allow_slow, actor, via, tool, name, reuse, max_seconds):
    app = manager.get_app(session)
    path = manager.session_file(session)
    model = manager.model_id(session) if app is not None else None
    cur = recorder.current()
    actor = actor or getattr(cur, "actor", None) or "ai"
    via = via or getattr(cur, "via", None)
    tool = tool or getattr(cur, "tool", None) or "checkpoint"
    if app is None or not path or not model:
        return {"status": "skipped", "why": "no_session", "note": ""}
    with _lock:
        if gid and not name and (model, gid) in _groups and checkpoints.get(model, _groups[(model, gid)]):
            return {"status": "dedup", "id": _groups[(model, gid)], "tier": 0, "note": ""}
    on = journal.enabled()
    s = (journal.summary(model) or {}) if on else {}
    dirty = _dirty_scope()
    kind = "named" if name else "auto"
    extra = {"group": gid, "fresh": _fresh(s) if on else None, "journal_t": s.get("last_t")}
    now = marks(s) if on else None
    if reason in NOT_IF_SAVED and not name and on and not dirty and _is_file(manager, session, model, path, s):
        return {"status": "skipped", "why": "saved", "tier": 0, "note": ""}   # the file is the model: none needed
    with _scope(manager, actor, via, session, model, gid, tool) as sc:
        last = _last.get(model)
        if (on and reuse and last and not dirty and now is not None and last["marks"] == now
                and checkpoints.get(model, last["id"]) is not None):
            sc.add("checkpoint", session=session, model=model, reuse=last["id"], cp_reason=reason,
                   status="unchanged", target={"path": path})
            return _made(model, gid, now, {"status": "reused", "id": last["id"], "tier": 1, "note": ""})
        if on and not dirty and _is_file(manager, session, model, path, s):
            act = activity.begin(actor, "checkpoint", session, phase="call", target={"reason": reason, "est_s": None})
            try:
                cp = checkpoints.backup_file(model, path, reason=reason, tool=tool, session=session, klass=kind,
                                             name=name, extra={**extra, "state": "saved"})
            except checkpoints.BackupError as exc:
                activity.end(act, "error")
                logger.warning("restore point: the file copy of %s failed (%s); trying Export", path, exc)
            else:
                activity.end(act, "ok")
                return _made(model, gid, now, {"status": "copied", "id": cp["id"], "tier": 2, "state": "saved",
                                          "secs": cp.get("secs"), "note": "", "warning": cp.get("warning")})
        est = estimate(model, path)
        limit = max_s() if max_seconds is None else max_seconds
        if not allow_slow and est["s"] is not None and est["s"] > limit:
            sc.add("checkpoint", session=session, model=model, status="skipped", why="slow", est_s=est["s"],
                   cp_reason=reason, target={"path": path})
            return {"status": "skipped", "why": "slow", "est_s": est["s"], "tier": 5, "note": _note("slow", est["s"])}
        act = activity.begin(actor, "checkpoint", session, phase="aspen",
                             target={"reason": reason, "est_s": est["s"], "name": name})
        try:
            cp = checkpoints.export_checkpoint(app, model, reason=reason, tool=tool, session=session, name=name,
                                               orig=path, extra={**extra, "state": "live", "est_s": est["s"],
                                                                 "rows2": est["rows2"], "results": est.get("results")})
        except Exception as exc:
            activity.end(act, "error")
            sc.add("checkpoint", session=session, model=model, status="skipped", why="failed", cp_reason=reason,
                   target={"path": path}, result=str(exc)[:300])
            return {"status": "failed", "why": "failed", "error": str(exc), "tier": 5, "est_s": est["s"],
                    "note": _note("failed", err=exc)}
        activity.end(act, "ok")
        return _made(model, gid, now, {"status": "exported", "id": cp["id"], "tier": 3, "state": "live",
                                  "secs": cp.get("secs"), "est_s": est["s"], "note": "",
                                  "warning": cp.get("warning")})


def _made(model, gid, now, res: dict) -> dict:
    """Remember the restore point (for reuse: with the journal's marks it holds; per group)."""
    with _lock:
        _last[model] = {"id": res["id"], "marks": now}
        if gid:
            _groups[(model, gid)] = res["id"]
            while len(_groups) > GROUPS_MAX:
                _groups.pop(next(iter(_groups)))
    return {k: v for k, v in res.items() if v is not None}


def keep(model_id: str, cid: str, name: str | None = None) -> dict | None:
    """An automatic restore point kept for good ("Keep"): checkpoints.keep."""
    return checkpoints.keep(model_id, cid, name)


def forget(model_id: str) -> None:
    """Forget what this process made of one model -- its reuse mark and its groups' points: the
    model was put back to a restore point, so none of them holds it as it is now."""
    with _lock:
        _last.pop(model_id, None)
        for k in [k for k in _groups if k[0] == model_id]:
            del _groups[k]


def reset() -> None:
    """Forget what this process made (a model's file replaced under it)."""
    with _lock:
        _last.clear()
        _groups.clear()
