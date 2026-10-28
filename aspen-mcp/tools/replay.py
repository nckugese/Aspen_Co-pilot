"""The timeline turned into blocks -- change records (tools/journal.py, as
journal.pick hands them) made back into a block program that a tab shows and can run again.

    build(records, lang)  -> {"program", "skipped", "notes", "n"}
    program(records)      -> (program, skipped)
    title(lang, head, n) / text(lang, res, ...) / counts(skipped) / say(lang, key, **kw)
                          the new tab's name, its chat line, the answer's tally, the job's words

What becomes what, oldest record first by (t, id):
  value, changed                  set: after's value; a unit / basis only when the request gave one
                                  (after has them only then); set_property_method's (GOPSETNAME): method
  run that ran; reinit            run; a reinit just before a run: {"do": "run", "reinit": true};
                                  a reinit with no run after it: skipped
  add / remove of a block,        place / remove / component -- a component added again by the name
  stream or component             it was added by (target.aname), else by its label (noted)
  connect                         connect; one that took the stream off (journal.is_disconnect:
                                  disconnect_stream, a program's or an undo's -- the port may keep
                                  other streams --, or a refused connect's ``detached``): remove
                                  with its port
  summary / restore (a loop, an   a set of each field it left changed (after != before): its end
  optimize, a program's end)      value in the unit it had; why "the sweep's result"
  attr, save, patch, open, close, checkpoint, analysis, a restore to a restore point, reactions,
  rows, other elements, a loop with no end recorded                         skipped, listed
  failed, refused, unchanged, error (a run that ran is no error), a begin that ended, group
  headers, end records                                     left out, not listed: nothing changed
A call's reason is the why of the first statement made from it (a program's own why included).
Sets of one field with no run or flowsheet change between them fold into the last -- the first's
why, the unit and basis last given -- and one that ends where the first began goes. Statements
carry no ids: normalize() gives them. Pure: stdlib and tools.journal's record reading only, no
COM, no disk, no clock.
"""
from __future__ import annotations

import math
import numbers

from tools import journal

RAN = frozenset({"ok", "warn", "error"})                 # journal.RAN: a run record whose run ran
_NO_CHANGE = frozenset({"unchanged", "failed", "refused", "error"})
_BREAKS = frozenset({"run", "place", "connect", "remove", "component", "method"})   # end a fold
_METHOD = "\\specifications\\input\\gopsetname"
_SKIP_OPS = {"attr": "attr", "save": "save", "checkpoint": "checkpoint", "open": "open", "close": "open",
             "analysis": "analysis"}
_OBJ_KINDS = ("rxnset", "reaction", "chemistry", "row")
TITLE_MAX = 60

# (en, zh). Skip codes as a list says them; a loop's words for "the <do>'s result".
_WORDS = {
    "attr": ("attribute settings", "屬性設定"), "save": ("saves", "存檔"),
    "checkpoint": ("restore points", "還原點"), "open": ("opening or closing the model", "開關模型"),
    "analysis": ("analyses", "分析"), "patch": ("file edits", "改檔"),
    "redraw": ("redrawing Aspen's diagram", "重新排列 Aspen 流程圖"),
    "reinit": ("a Reinitialize with no run after it", "其後未執行的 Reinitialize"),
    "restore_point": ("restoring a restore point", "還原到還原點"),
    "unfinished": ("a loop or optimization with no end recorded", "沒有結束紀錄的迴圈或優化"),
    "no_type": ("a block whose type was not recorded", "沒有記下類型的單元"),
    "rxnset": ("reactions", "反應"), "reaction": ("reactions", "反應"), "chemistry": ("chemistry", "化學"),
    "row": ("table rows", "表格列"), "element": ("other elements", "其他元素"), "other": ("other changes", "其他修改"),
}
_DO = {"sweep": ("sweep", "掃描"), "seek": ("design spec", "調整到目標"), "optimize": ("optimization", "優化"),
       "repeat": ("loop", "重複"), "until": ("loop", "重複直到"), "restore": ("program's end", "程式結束時的還原")}
_MSG = {
    "tb_title": ("Redo: {title}", "重做：{title}"),
    "tb_title_n": ("Redo: {n} changes", "重做：{n} 筆修改"),
    "tb_done": ("Made {k} block step(s) from {n} change(s){skip}.", "從 {n} 筆修改做成 {k} 步積木{skip}。"),
    "tb_skip": (" (skipped {m}: {words})", "（略過 {m} 筆：{words}）"),
    "tb_why": ("Each step's note is the reason given at the time.", "每一步的說明是當時的理由。"),
    "tb_again_group": ("To get the same result, put the model back to before this group, then run it.",
                       "要重現一樣的結果，先把模型還原到這組之前再執行。"),
    "tb_again_ids": ("To get the same result, put the model back to before these changes, then run it.",
                     "要重現一樣的結果，先把模型還原到這些修改之前再執行。"),
    "tb_by_label": ("{names}: added again by its label (the name it was added by was not recorded).",
                    "{names} 當時沒有記下加入時的名稱，用代號重新加入。"),
    "tb_missing": ("{m} more could not be found among the recent records (too old).",
                   "另有 {m} 筆在最近的紀錄裡找不到（太舊了）。"),
    "tb_none": ("None of these changes has a block", "這些修改都沒有對應的積木"),
    "tb_result": ("the {do}'s result", "{do}的結果"),
    "rd_busy": ("Model {session} is running a program; redraw Aspen's diagram when it finishes",
                "模型 {session} 正在執行程式，完成後再重新排列 Aspen 流程圖"),
    "rd_done": ("Redrew Aspen's diagram: Aspen reopened the model and laid it out left to right.",
                "已重新排列 Aspen 流程圖：Aspen 重新開啟模型，由左到右排列。"),
    "rd_fail": ("Could not redraw Aspen's diagram: {res}", "無法重新排列 Aspen 流程圖：{res}"),
    "rd_placed": ("Put the workbench's arrangement into Aspen's diagram: Aspen reopened the model with {n} "
                  "block(s) where they are here, their streams moved along.",
                  "已把工作台的排列套用到 Aspen 流程圖：Aspen 重新開啟模型，{n} 個單元移到這裡的位置，流股跟著移動。"),
    "rd_place_fail": ("Could not put the arrangement into Aspen's diagram: {res}", "無法把排列套用到 Aspen 流程圖：{res}"),
}


def say(lang: str, key: str, **kw) -> str:
    en, zh = _MSG[key]
    return (zh if lang == "zh" else en).format(**kw)


def _word(lang: str, table: dict, key: str) -> str:
    en, zh = table.get(key) or (key, key)
    return zh if lang == "zh" else en


def _key(r: dict) -> tuple:
    t = r.get("t")
    return float(t) if isinstance(t, (int, float)) and not isinstance(t, bool) else 0.0, str(r.get("id") or "")


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _line(s) -> str | None:
    s = " ".join(str(s or "").split())
    return s or None


def _num(v):
    """A number written as text, a number (as the window's set block reads its field); else as it is."""
    if isinstance(v, str) and v.strip():
        try:
            f = float(v)
        except ValueError:
            return v
        if math.isfinite(f):
            return int(f) if f.is_integer() and not any(c in v for c in ".eE") else f
    return v


def _same(a, b) -> bool:
    a, b = _num(a), _num(b)
    if isinstance(a, numbers.Real) and isinstance(b, numbers.Real) and not isinstance(a, bool) \
            and not isinstance(b, bool):
        return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)), abs(float(b)))
    return a == b


class _Build:
    def __init__(self, lang: str, reasons: dict):
        self.lang, self.reasons = lang, reasons
        self.steps: list = []        # [{"st": statement, ...}] in order
        self.open: dict = {}         # lower-cased path -> its set's entry since the last run / flowsheet change
        self.said: set = set()       # calls whose reason a statement carries already
        self.reinit = None           # a reinit record waiting for its run
        self.skipped: list = []
        self.notes: list = []
        self.used: set = set()       # records a statement was made from

    def why(self, r: dict):
        """The reason of ``r``'s call, for the first statement made from that call only."""
        call = r.get("call")
        if not call:
            return _line(r.get("reason"))
        if call in self.said:
            return None
        self.said.add(call)
        return self.reasons.get(call)

    def skip(self, r: dict, code: str) -> None:
        self.skipped.append({k: v for k, v in (("id", r.get("id")), ("code", code), ("op", r.get("op")),
                                                ("tool", r.get("tool"))) if v is not None})

    def emit(self, r: dict, st: dict, why=None, before=None) -> None:
        self.used.add(r.get("id"))
        if self.reinit is not None:
            if st["do"] == "run":
                st["reinit"] = True
                why = why or self.why(self.reinit)
            else:
                self.skip(self.reinit, "reinit")
            self.reinit = None
        if st["do"] != "set":
            if st["do"] in _BREAKS:
                self.open.clear()
            if why:
                st["why"] = why
            self.steps.append({"st": st})
            return
        key = st["path"].lower()
        e = self.open.pop(key, None)
        unit, basis = st.pop("unit", None), st.pop("basis", None)
        if e is not None:                           # the same field again: one set, the last value
            self.steps = [x for x in self.steps if x is not e]
            unit, basis = unit or e["unit"], basis or e["basis"]
            why, before = e["why"] or why, e["before"]
        e = {"st": st, "unit": unit, "basis": basis, "why": why, "before": before}
        for k, v in (("unit", unit), ("basis", basis), ("why", why)):
            if v:
                st[k] = v
        if isinstance(before, dict) and "value" in before and _same(before.get("value"), st.get("value")) \
                and (not unit or unit == before.get("unit")) and (not basis or basis == before.get("basis")):
            return                                  # it ends where it began: nothing to do
        self.open[key] = e
        self.steps.append(e)

    def take(self, r: dict, ended: set) -> None:
        kind, op, status = r.get("kind"), r.get("op"), r.get("status")
        if kind == "begin":
            unended = r.get("open") if isinstance(r.get("open"), bool) else r.get("call") not in ended
            if unended:
                self.skip(r, "unfinished")
            return
        if kind != "change":
            return
        if op in ("run", "reinit"):
            if status not in RAN:
                return
            if op == "run":
                self.emit(r, {"do": "run"}, self.why(r))
            else:
                if self.reinit is not None:
                    self.skip(self.reinit, "reinit")
                self.reinit = r
            return
        if status in _NO_CHANGE:
            return
        tg = _d(r.get("target"))
        if op == "value":
            path = str(tg.get("path") or "")
            if not path:
                return
            after, req = _d(r.get("after")), _d(r.get("req"))
            value = after["value"] if "value" in after else req.get("value")
            if r.get("tool") == "set_property_method" or path.lower().endswith(_METHOD):
                name = _line(value)
                self.emit(r, {"do": "method", "method": name}, self.why(r)) if name else self.skip(r, "other")
                return
            st = {"do": "set", "path": path, "value": _num(value)}
            if req.get("unit"):
                st["unit"] = str(after.get("unit") or req["unit"])
            if req.get("basis"):
                st["basis"] = str(after.get("basis") or req["basis"])
            self.emit(r, st, self.why(r), r.get("before") if isinstance(r.get("before"), dict) else None)
        elif op in ("add", "remove"):
            self._object(r, op, tg)
        elif op == "connect":
            s, b, p = tg.get("stream"), tg.get("block"), tg.get("port")
            if not (s and b and p):
                return self.skip(r, "other")
            off = bool(r.get("detached")) or journal.is_disconnect(r)     # (a detached one: V15 took it off)
            self.emit(r, {"do": "remove" if off else "connect", "stream": str(s), "block": str(b), "port": str(p)},
                      self.why(r))
        elif op in ("summary", "restore"):
            self._loop(r, op, tg)
        elif op in _SKIP_OPS:
            self.skip(r, _SKIP_OPS[op])
        elif op == "patch":
            self.skip(r, "redraw" if r.get("tool") == "layout_flowsheet" else "patch")
        else:
            self.skip(r, "other")

    def _object(self, r: dict, op: str, tg: dict) -> None:
        kind, name = tg.get("kind"), _line(tg.get("name"))
        if not name:
            return self.skip(r, "other")
        if kind in ("block", "stream"):
            if op == "remove":
                st = {"do": "remove", kind: name}
            elif kind == "block":
                if not _line(tg.get("type")):
                    return self.skip(r, "no_type")
                st = {"do": "place", "block": name, "type": _line(tg["type"])}
            else:
                st = {"do": "place", "stream": name}
                typ = (_line(tg.get("type")) or "").upper()
                if typ and typ != "MATERIAL":
                    st["type"] = typ
        elif kind == "component":
            if op == "remove":
                st = {"do": "component", "remove": name}
            else:
                aname = _line(tg.get("aname"))
                st = {"do": "component", "add": aname or name}
                if not aname:
                    self.notes.append({"id": r.get("id"), "code": "by_label", "name": name})
        else:
            return self.skip(r, kind if kind in _OBJ_KINDS else "element")
        self.emit(r, st, self.why(r))

    def _loop(self, r: dict, op: str, tg: dict) -> None:
        """A loop's, an optimization's or a program end's summary: the end value of every field it
        left changed, in the unit it had then (a basis only where that changed too)."""
        if op == "restore" and tg.get("checkpoint"):
            return self.skip(r, "restore_point")
        writes = r.get("writes")
        if not isinstance(writes, dict):
            return
        self.why(r)                                  # the call's reason is not a later statement's
        do = _word(self.lang, _DO, str(r.get("do") or op))
        why = say(self.lang, "tb_result", do=do)
        for path, w in writes.items():
            if journal.split_key(path)[1] is not None or not isinstance(w, dict) or "after" not in w:
                continue                             # (an attribute a loop wrote: no block sets one)
            b, a = _d(w.get("before")), _d(w.get("after"))
            if _same(b.get("value"), a.get("value")) and b.get("unit") == a.get("unit"):
                continue
            st = {"do": "set", "path": str(path), "value": _num(a.get("value"))}
            if a.get("unit"):
                st["unit"] = str(a["unit"])
            if a.get("basis") and a.get("basis") != b.get("basis"):
                st["basis"] = str(a["basis"])
            self.emit(r, st, why, b if "value" in b else None)

    def done(self) -> dict:
        if self.reinit is not None:
            self.skip(self.reinit, "reinit")
            self.reinit = None
        return {"program": [e["st"] for e in self.steps], "skipped": self.skipped, "notes": self.notes,
                "n": len(self.used)}


def build(records, lang: str = "en") -> dict:
    """``records`` (change, begin, end records and group headers, in any order) as a block program:
    {"program": statements without ids, "skipped": [{"id", "code", "op", "tool"}] listed for the
    user (codes: _WORDS), "notes": [{"id", "code": "by_label", "name"}], "n": the records a
    statement was made from}. ``lang`` words a loop's why."""
    recs = sorted((r for r in records or () if isinstance(r, dict)), key=_key)
    reasons: dict = {}
    for r in recs:
        call, why = r.get("call"), _line(r.get("reason"))
        if call and why and call not in reasons:
            reasons[call] = why
    ended = {r.get("call") for r in recs if r.get("kind") in ("change", "end") and r.get("call")}
    b = _Build(lang, reasons)
    for r in recs:
        b.take(r, ended)
    return b.done()


def program(records) -> tuple[list, list]:
    """(the program, what was skipped): build() in short."""
    res = build(records)
    return res["program"], res["skipped"]


def counts(skipped) -> list[dict]:
    """[{"code", "n"}] of a skipped list, in the order first skipped."""
    out: dict = {}
    for s in skipped or ():
        out[s["code"]] = out.get(s["code"], 0) + 1
    return [{"code": c, "n": n} for c, n in out.items()]


def title(lang: str, head, n: int) -> str:
    """The new tab's name: "Redo: <the group's title>", else "Redo: <n> changes"."""
    t = _line(head)
    return (say(lang, "tb_title", title=t) if t else say(lang, "tb_title_n", n=n))[:TITLE_MAX]


def text(lang: str, res: dict, missing: int = 0, group: bool = True) -> str:
    """The new tab's chat line: what was made of how many changes, what was skipped (in words),
    that each why is the reason of the time, and how to get the same result again."""
    skipped = res.get("skipped") or []
    skip = ""
    if skipped:
        words = ("、" if lang == "zh" else ", ").join(_word(lang, _WORDS, c["code"]) for c in counts(skipped))
        skip = say(lang, "tb_skip", m=len(skipped), words=words)
    parts = [say(lang, "tb_done", n=res.get("n", 0), k=len(res.get("program") or []), skip=skip),
             say(lang, "tb_why"), say(lang, "tb_again_group" if group else "tb_again_ids")]
    names = [n["name"] for n in res.get("notes") or [] if n.get("code") == "by_label"]
    if names:
        parts.append(say(lang, "tb_by_label", names=", ".join(dict.fromkeys(names))))
    if missing:
        parts.append(say(lang, "tb_missing", m=missing))
    return ("" if lang == "zh" else " ").join(parts)
