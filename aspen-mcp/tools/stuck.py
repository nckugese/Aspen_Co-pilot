"""Is the AI stuck? Three rules over the journal records of this server's own AI.
This module only decides; tools/brake.py pauses.

    trigs = stuck.check(model, recs)           # a journal.listen fn: after every append
    stuck.config()                             # {"runs": 3, "field": 4, "revert": 2, "on": {...}}
    stuck.configure({"runs": 5, "on": {"field": False}})    # clamped; returns the new config
    stuck.resume(mute="runs")                  # the user resumed: counts start again, and this
                                               # rule is off for the last trigger's group
    stuck.mute(group, rule) / stuck.muted(group) / stuck.reset(model)

A record counts only when it is a ``change`` with ``actor == "ai"`` and ``srv`` this
process's (``journal.srv()``): the user's edits, programs, optimizers, Aspen's own window and
another server's AI never do. Runs are the exception on one side: a converged run (``run``
ok / warn, or a loop's ``summary`` / ``restore`` whose ``runs`` counts an ok or warn) resets,
whoever made it.

  runs    N (3, 2-10) AI ``run`` / ``reinit`` records of one model in a row whose status is
          error (ran, ended in errors), failed (did not complete) or refused (inputs
          incomplete, or Aspen's internal fault flagged the session: ``why`` says which).
          Unknown / ok reinit neither count nor break the row.
  field   N (4, 3-20) AI ``value`` / ``attr`` records (status changed) of one field in one
          group with no converged run of the model after them: a converged run sets every
          such count of the model to 0, so a hand sweep (set_value + run, converging) never
          counts. The key is the path in lower case, ``#n`` for attribute n.
  revert  N (2, 1-10) times in one group the AI took back its own change: a value / attr
          whose new state is the ``before`` of its own earlier change of that field in the
          group (A -> B -> A), the removal of an object it added in the group, or a record
          with ``revert_of`` naming its own records. A take-back counts only when no
          converged run came between the change and it: going back after results were seen
          is a sweep, not a swing.

A change the user approved is theirs to judge, never a sign the AI is stuck: a record whose
``gate`` says ``confirmed`` (its card applied) or ``allowed`` (the user let the class through
for the group), or that carries ``proposed`` (a late apply, "AI proposed, you executed"),
counts for neither ``field`` nor ``revert`` (a removal of the AI's own addition included).

A rule that fires starts its count again (so it does not fire on every later record) and is
remembered as ``last()``; one switched off or muted keeps counting and only does not fire.
``check`` (alias ``feed``) returns [] or trigger dicts:
    {"rule", "model", "group", "n", "limit", "ids": [record ids, the evidence],
     "why": {"en", "zh"}: plain words, "detail": {...}}
detail: runs {"n", "last": {"block", "msg", "mech", "status"}} -- the last failed run's own
first error (``_last_run``, the record's ``first_error``): the block and Aspen's words for it,
the failure kind tools/diagnose names (``why`` says it in plain words: "MEOHCOL · column not in mass balance"); field
{"path", "field", "values"} (``field``: the path in words, "FEED › Temperature"); revert
{"path", "values"} or, for a removal, {"name"}. A field in ``why`` / ``field`` is named by
tools/aspen_labels (zh with its gloss), and so is a tree path in a run's message: never a
backslash; a message is cut at a word. The functions above are ``WATCH``'s, one ``Watch`` per
process (``Watch(srv=)`` for another server's records). Stdlib only (and journal for
``srv``, aspen_labels, diagnose and probes for the words), never raises; a record costs a few dict
operations -- only a rule firing names its field (aspen_labels' cached read, the one I/O).
"""
from __future__ import annotations

import logging
import math
import re
import threading

from tools import aspen_labels, diagnose, journal, probes

logger = logging.getLogger(__name__)

RULES = ("runs", "field", "revert")
DEFAULTS = {"runs": 3, "field": 4, "revert": 2}
RANGES = {"runs": (2, 10), "field": (3, 20), "revert": (1, 10)}
FAILED = frozenset({"error", "failed", "refused"})     # a run / reinit that did not converge
CONVERGED = frozenset({"ok", "warn"})
KEYS_MAX, HIST_MAX, MUTE_MAX, MSG_MAX, WHY_MAX = 256, 20, 64, 100, 60


def _num(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _same(a, b) -> bool:
    if a == b:
        return True
    x, y = _num(a), _num(b)
    return x is not None and y is not None and math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12)


def _eq(a, b) -> bool:
    """Two measured states ({"value", "unit", "basis", ...}) hold the same: value read on both
    sides, and whatever of value / unit / basis both read agrees."""
    if not isinstance(a, dict) or not isinstance(b, dict) or "value" not in a or "value" not in b:
        return False
    return all(_same(a[k], b[k]) for k in ("value", "unit", "basis") if k in a and k in b)


def _val(s):
    return s.get("value") if isinstance(s, dict) else None


def _cap(d: dict, n: int = KEYS_MAX) -> None:
    while len(d) > n:
        d.pop(next(iter(d)))


def _tg(r) -> dict:
    return r.get("target") if isinstance(r.get("target"), dict) else {}


def _key(r) -> str | None:
    tg = _tg(r)
    p = tg.get("path")
    if not p:
        return None
    n = tg.get("attr", r.get("attr")) if r.get("op") == "attr" else None
    return str(p).lower() if n is None else f"{str(p).lower()}#{n}"


def _where(r, lang="en") -> str:
    """FEED › Temperature (in zh, the field name with its Chinese gloss): the object and field of a record in
    words (aspen_labels.say; the block type when the target has one), else object › field code,
    else its path's tail; `` › #n`` for attribute n. Never a backslash."""
    tg = _tg(r)
    p = tg.get("path")
    s = aspen_labels.say(str(p), tg.get("type"), lang) if p else ""
    if not s:
        name = next((tg[k] for k in ("block", "stream", "rxnset", "chemistry", "name") if tg.get(k)), None)
        s = " › ".join(str(x) for x in (name, tg.get("field")) if x) or str(p or "?").rsplit("\\", 1)[-1]
    if r.get("op") == "attr" and tg.get("attr") is not None:
        s += f" › #{tg['attr']}"
    return s.replace("\\", "/")


def _approved(r) -> bool:
    """The user approved this change: its card applied (gate ``confirmed``), its class let
    through for the group (gate ``allowed``), or applied late as theirs (``proposed``)."""
    g = r.get("gate") if isinstance(r.get("gate"), dict) else {}
    return bool(g.get("confirmed") or g.get("allowed") or r.get("proposed"))


def _converged(r) -> bool:
    op, st = r.get("op"), r.get("status")
    if op == "run":
        return st in CONVERGED
    runs = r.get("runs") if isinstance(r.get("runs"), dict) else {}
    if op in ("summary", "restore") and runs:
        return any((_num(runs.get(k)) or 0) > 0 for k in CONVERGED)
    return False


# ---------------------------------------------------------------------------- a failed run's words
_PATH = re.compile(r"\\Data(?:\\[^\\\s,;'\"]+)+")
_RUN_HEAD = re.compile(r"^\s*(?:Cannot run|Failed to run) simulation '[^']*'\s*[:.]?\s*", re.I)
_MSG_HEAD = re.compile(r"^\s*\*")                                         # "*  WARNING", " * ERROR IN BLOCK"
_REFUSED = {"en": "inputs incomplete", "zh": "輸入不完整"}
_FAULT = {"en": "Aspen reported an internal fault", "zh": "Aspen 回報內部錯誤"}    # (diagnose._FAULT_SAID)
_FAILED = {"en": "did not finish", "zh": "未完成"}


def _cut(text, n: int = MSG_MAX) -> str:
    """``text`` on one line, at most ``n`` characters -- cut at a word, "…" at the end."""
    s = " ".join(str(text or "").split())
    if len(s) <= n:
        return s
    head = s[:n - 1]
    sp = head.rfind(" ")
    return (head[:sp] if sp >= n // 2 else head).rstrip(" ,;:-(") + "…"


def _labelled(text) -> str:
    """Every tree path in ``text`` in words (aspen_labels.say): "...under: \\Data\\Blocks." ->
    "...under: Blocks."; never a backslash."""
    def say(m):
        p = m.group(0)
        tail = p[len(p.rstrip(".:")):]
        p = p[:len(p) - len(tail)]
        return (aspen_labels.say(p) or p.rsplit("\\", 1)[-1]) + tail
    return _PATH.sub(say, str(text or "")).replace("\\", "/")


def _sentence(result) -> str:
    """A run the tool did not start or finish (refused, failed): the first sentence of its
    answer after "Cannot run simulation 'x':" / "Failed to run simulation 'x'."."""
    s = " ".join(_RUN_HEAD.sub("", str(result or ""), count=1).split())
    return re.split(r"(?<=\.)\s+(?=[A-Z])", s, maxsplit=1)[0].rstrip(" .")


def _last_run(r) -> dict:
    """{"block", "msg", "mech", "status"} of a failed run record, from its own first error: the
    record's ``first_error`` (tools/probes.first_error, taken from the whole run answer), else --
    a record from before it -- the same read of what the record kept (its cut ``result``, its
    Run-Status ``msgs``): the block, the failure kind tools/diagnose names, and the line that
    says it ("COLUMN NOT IN MASS BALANCE"). A run that did not run (refused, failed): the first
    sentence of the tool's answer. Tree paths in words, cut at a word."""
    st = r.get("status")
    blocks = r.get("blocks") if isinstance(r.get("blocks"), dict) else {}
    msgs = r.get("msgs") if isinstance(r.get("msgs"), list) else []
    block = msg = mech = None
    if st == "error":
        fe = r.get("first_error")
        fe = fe if isinstance(fe, dict) else probes.first_error(r.get("result"), msgs, blocks) or {}
        block, mech = (x if isinstance(x, str) and x else None for x in (fe.get("block"), fe.get("kind")))
        lines = [x for x in fe.get("lines") if isinstance(x, str) and x] if isinstance(fe.get("lines"), list) else []
        if lines:
            msg = next((x for x in lines if mech and mech in diagnose.mechanisms(x, limit=len(diagnose.EXPLAIN))),
                       None) or next((x for x in lines if not _MSG_HEAD.match(x)), lines[0])
            msg = msg.rstrip(" .;")
    elif r.get("result"):
        msg = _sentence(r.get("result"))
    msg = _cut(_labelled(msg), MSG_MAX) if msg else None
    return {k: v for k, v in (("block", block), ("msg", msg), ("mech", mech), ("status", st)) if v}


def _run_words(last: dict, result=None, lang="en") -> list:
    """The last failed run in plain words for ``why``: [block, what went wrong] -- the failure
    kind's title (tools/diagnose), a refused run's real reason (Aspen's internal fault, else
    "inputs incomplete (where)"), else Aspen's own words, cut."""
    out = [last["block"]] if last.get("block") else []
    if last.get("mech"):
        t = diagnose.explain(last["mech"], lang)["title"]
        word = t.split(" ", 1)[0]
        out.append(t[:1].lower() + t[1:] if lang == "en" and not (len(word) > 1 and word.isupper()) else t)
    elif last.get("status") == "refused" and diagnose._FAULT_SAID in " ".join(str(result or "").split()):
        out.append(_FAULT[lang])
    elif last.get("status") == "refused":
        where = [w for w in (aspen_labels.say(p.rstrip(".:")) for p in _PATH.findall(_sentence(result))) if w][:3]
        if not where:
            out.append(_REFUSED[lang])
        else:
            out.append(f"{_REFUSED['en']} under {', '.join(where)}" if lang == "en" else
                       f"{'、'.join(where)} 的{_REFUSED['zh']}")
    elif last.get("msg"):
        if last.get("status") == "failed":
            out.append(_FAILED[lang])
        out.append(_cut(last["msg"], WHY_MAX))
    elif last.get("status") == "failed":
        out.append(_FAILED[lang])
    return out


class _Model:
    """What one model's records left: ``fails`` the AI's failed runs in a row (id, record),
    ``epoch`` converged runs seen, ``pend`` (group, key) -> ids of changes no converged run
    followed, ``hist`` (group, key) -> [(before, after, epoch, id)], ``adds`` (group, object
    path) -> (epoch, id), ``reverts`` group -> [(id, how: value | remove | undo, field key)],
    ``mine`` the AI's record ids (for revert_of)."""
    __slots__ = ("fails", "epoch", "pend", "hist", "adds", "reverts", "mine")

    def __init__(self):
        self.fails, self.epoch, self.pend, self.hist = [], 0, {}, {}
        self.adds, self.reverts, self.mine = {}, {}, {}


class Watch:
    def __init__(self, srv=None):
        self._srv = srv                    # None: journal.srv() at every check
        self._lock = threading.RLock()
        self._models: dict = {}
        self._mutes: dict = {}             # group -> set of rules off for it
        self._last = None
        self._cfg = {**DEFAULTS, "on": dict.fromkeys(RULES, True)}

    # -- settings
    def config(self) -> dict:
        with self._lock:
            return {**{k: self._cfg[k] for k in RULES}, "on": dict(self._cfg["on"])}

    def configure(self, cfg=None, **kw) -> dict:
        """Set thresholds / switches from a dict like config()'s (a brake_stuck event) or
        keywords; values out of RANGES are clamped, junk ignored. Returns config()."""
        try:
            d = {**(cfg if isinstance(cfg, dict) else {}), **kw}
            with self._lock:
                for k in RULES:
                    n = _num(d.get(k))
                    if n is not None:
                        lo, hi = RANGES[k]
                        self._cfg[k] = int(min(hi, max(lo, round(n))))
                on = d.get("on")
                for k in RULES:
                    v = on.get(k) if isinstance(on, dict) else None
                    if isinstance(v, bool):
                        self._cfg["on"][k] = v
        except Exception as exc:
            logger.warning("stuck: configure failed (%r)", exc)
        return self.config()

    def defaults(self) -> dict:
        return self.configure({**DEFAULTS, "on": dict.fromkeys(RULES, True)})

    def mute(self, group, rule=None) -> None:
        """Rule ``rule`` (None: all three) no longer fires for ``group``."""
        if rule is not None and rule not in RULES or not isinstance(group, (str, type(None))):
            return
        with self._lock:
            s = self._mutes.pop(group, set())
            self._mutes[group] = s | (set(RULES) if rule is None else {rule})
            _cap(self._mutes, MUTE_MAX)

    def muted(self, group) -> set:
        with self._lock:
            return set(self._mutes.get(group, ())) if isinstance(group, (str, type(None))) else set()

    def last(self) -> dict | None:
        with self._lock:
            return dict(self._last) if self._last else None

    def reset(self, model=None) -> None:
        """Counts start again: one model's, or every model's; ``last()`` goes with them (with
        one model's, when it was that model's)."""
        with self._lock:
            if model is None:
                self._models.clear()
                self._last = None
            else:
                self._models.pop(model, None)
                if (self._last or {}).get("model") == model:
                    self._last = None

    def resume(self, mute=None, group=None) -> None:
        """The user resumed the AI: every count starts again; ``mute`` (a rule) is off from now
        on for ``group`` (default: the last trigger's)."""
        with self._lock:
            if mute in RULES:
                g = group if group is not None else (self._last or {}).get("group")
                if g is not None:
                    self.mute(g, mute)
            self.reset()

    # -- the check
    def check(self, model, recs, srv=None) -> list:
        try:
            me = srv or self._srv or journal.srv()
            out = []
            with self._lock:
                m = self._models.get(model)
                if m is None:
                    m = self._models[model] = _Model()
                for r in [recs] if isinstance(recs, dict) else recs if isinstance(recs, (list, tuple)) else ():
                    if isinstance(r, dict) and r.get("kind") == "change":
                        out += self._one(model, m, r, r.get("actor") == "ai" and r.get("srv") == me)
                if out:
                    self._last = out[-1]
            return out
        except Exception as exc:
            logger.warning("stuck: check of %s failed (%r)", model, exc)
            return []

    feed = check

    def _fires(self, rule, group) -> bool:
        return self._cfg["on"][rule] and rule not in self._mutes.get(group, ())

    def _one(self, model, m, r, ai) -> list:
        if _converged(r):
            m.fails.clear()
            m.pend.clear()
            m.epoch += 1
            return []
        if not ai:
            return []
        op, st, g, rid = r.get("op"), r.get("status"), r.get("group"), r.get("id")
        if rid:
            m.mine[rid] = None
            _cap(m.mine, 1000)
        if op in ("run", "reinit"):
            return self._runs(model, m, r, g, rid) if st in FAILED else []
        if st != "changed":
            return []
        out, rev, ok = [], None, _approved(r)
        if op in ("value", "attr"):
            k = _key(r)
            if k is None:
                return []
            hist = m.hist.setdefault((g, k), [])
            back = next((h for h in reversed(hist) if _eq(h[0], r.get("after"))), None)
            if back is not None and back[2] == m.epoch:
                rev = (rid, "value", k)
            hist.append((r.get("before"), r.get("after"), m.epoch, rid))
            del hist[:-HIST_MAX]
            _cap(m.hist)
            if not ok:
                out += self._field(model, m, r, g, k, rid)
        elif op in ("add", "remove"):
            p = str(_tg(r).get("path") or "").lower()
            if p and op == "add":
                m.adds[(g, p)] = (m.epoch, rid)
                _cap(m.adds)
            elif p:
                a = m.adds.pop((g, p), None)
                if a is not None and a[0] == m.epoch:
                    rev = (rid, "remove", None)
        if rev is None and r.get("revert_of"):
            of = r["revert_of"]
            of = [of] if isinstance(of, str) else of if isinstance(of, list) else []
            if of and all(x in m.mine for x in of):
                rev = (rid, "undo", None)
        if rev is not None and not ok:
            out += self._revert(model, m, r, g, rev)
        return out

    def _runs(self, model, m, r, g, rid) -> list:
        m.fails = (m.fails + [(rid, r)])[-RANGES["runs"][1]:]
        n = self._cfg["runs"]
        if len(m.fails) < n or not self._fires("runs", g):
            return []
        ev, m.fails = m.fails[-n:], []
        last = _last_run(ev[-1][1])
        en, zh = (_run_words(last, ev[-1][1].get("result"), lang) for lang in ("en", "zh"))
        return [self._trig("runs", model, g, [i for i, _ in ev], n, {"n": n, "last": last},
                           f"{n} failed runs in a row" + (f" (last: {', '.join(en)})" if en else ""),
                           f"連續 {n} 次執行失敗" + (f"（最後：{' · '.join(zh)}）" if zh else ""))]

    def _field(self, model, m, r, g, k, rid) -> list:
        pend = m.pend.setdefault((g, k), [])
        pend.append(rid)
        _cap(m.pend)
        n = self._cfg["field"]
        if len(pend) < n or not self._fires("field", g):
            return []
        ids, where = pend[-n:], _where(r)
        del m.pend[(g, k)]
        vals = [_val(h[1]) for h in m.hist.get((g, k), ())][-n:]
        return [self._trig("field", model, g, ids, n, {"path": _tg(r).get("path"), "field": where, "values": vals},
                           f"{where} changed {n} times in this request with no successful run",
                           f"{_where(r, 'zh')} 在此請求中修改 {n} 次，期間無成功執行")]

    def _revert(self, model, m, r, g, rev) -> list:
        rv = m.reverts.setdefault(g, [])
        rv.append(rev)
        del rv[:-RANGES["revert"][1]]
        _cap(m.reverts, 32)
        n = self._cfg["revert"]
        if len(rv) < n or not self._fires("revert", g):
            return []
        ev = rv[-n:]
        del m.reverts[g]
        _, how, k = rev
        where, v = _where(r), _val(r.get("after"))
        if how == "remove":
            where = str(_tg(r).get("name") or where)
            en, zh, detail = f"removed {where}, which it had added", f"移除自身新增的 {where}", {"name": where}
        else:
            hist = m.hist.get((g, k), []) if k else []
            vals = ([_val(hist[0][0])] + [_val(h[1]) for h in hist])[-8:] if hist else []
            back = how == "value" or v is not None
            en = where + (f" back to {v}" if back else "")
            zh = _where(r, "zh") + (f" 改回 {v}" if back else "")
            detail = {"path": _tg(r).get("path"), "values": vals}
        return [self._trig("revert", model, g, [e[0] for e in ev], n, detail,
                           f"the AI reverted its own changes {n} times (last: {en})",
                           f"AI 撤銷自身修改 {n} 次（最後：{zh}）")]

    def _trig(self, rule, model, group, ids, n, detail, en, zh) -> dict:
        return {"rule": rule, "model": model, "group": group, "n": len(ids), "limit": n,
                "ids": [i for i in ids if i], "why": {"en": en, "zh": zh}, "detail": detail}


WATCH = Watch()
check = WATCH.check
config = WATCH.config
configure = WATCH.configure
defaults = WATCH.defaults
mute = WATCH.mute
muted = WATCH.muted
last = WATCH.last
reset = WATCH.reset
resume = WATCH.resume
