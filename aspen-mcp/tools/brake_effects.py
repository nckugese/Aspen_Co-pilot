"""What a confirmation card says: what a risky AI
call will do to the model, in plain words, and which restore point is taken first -- and the
conditional risks' predicates the brakes ask.

    brake_effects.configure(manager=lambda: manager, flowsheet=_wb.flowsheet_of, tab_of=...)
    Brake(..., cond=brake_effects.cond)       # "save_other" / "program": falsy = no card
    Hooks(..., effects=brake_effects.hook)    # {risky, more, effects, cp}: Brake.card's fields
    if brake_effects.refresh(brake): save()   # the open cards' since_changes, now and then

An effect is {"code", <its facts>, "text": {"zh", "en"}}: "Deletes block B4 (Heater) and all its
inputs", "Streams S5, S6, connected to it, are left unconnected", "The 7 changes since the last
save (13:40) are lost" (the window may word it from the code and facts instead; the AI's own
text is brake.py's). ``risky``: the risky items with their facts; ``more``: the call's other,
ordinary changes (a program's); ``cp``: restore_points.plan()'s answer for a tool that takes a
restore point first ({"tier", "est_s", ...} -- intercept's safe check adds its ``est_s``: a slow
one makes an approval run after the AI's answer), else {"tier": "none" | "backup", "why"}.

Reads only, nothing written: the journal's summary and pages, os.stat, the model registry,
the window's flowsheet as last read, a workbench tab's program -- and, on the thread that
owns the COM objects (the event loop's, the server's main thread), a few tree reads: a block's
connections, a stream's ends, reactors' reaction sets, at most COM_BUDGET_S a card; what they
did not reach comes from the flowsheet, or is left out. Never raises.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time

from tools import aspen_labels as AL, brake, checkpoints, dispid, intercept, journal, knowledge_tools, main_tools, \
    model_registry, probes, restore_points, wb_plan

logger = logging.getLogger(__name__)

COM_BUDGET_S = 0.03              # tree reads a card may take (then the window's flowsheet)
NAMES_MAX = 6                    # names listed in one line ("S1, S2 ... and 3 more")
SINCE_MAX = 500                  # journal records a card's since_changes looks through
_NESTED = ("then", "else", "body")         # a program's nested bodies (workbench_tools._NESTED)
_CHANGING = {"set", "run", "sweep", "seek", "optimize", "save"}
_VAR = re.compile(r"\{(\w+)\}")
_REACTORS = {"RCSTR", "RPLUG", "RBATCH"}
_CFG: dict = {"manager": None, "flowsheet": None, "tab_of": None, "thread": None}
_UNDO = ("undo_by_checkpoint", "只能用還原點收回", "Only a restore point takes it back")


def configure(manager=None, flowsheet=None, tab_of=None, thread=None) -> None:
    """``manager``: () -> the AspenPlusManager; ``flowsheet``: session -> its flowsheet as the
    window last read it (workbench_tools.flowsheet_of) or None; ``tab_of``: a workbench_run
    call's kw -> the tab it runs ({"title", "session", "program"}) or None; ``thread``: the
    ident of the thread that owns the COM objects (default: the main thread). Only those given
    change (the server gives the manager and the flowsheet, the workbench its tabs)."""
    given = {"manager": manager, "flowsheet": flowsheet, "tab_of": tab_of, "thread": thread}
    _CFG.update({k: v for k, v in given.items() if v is not None})


def _get(fn, *a):
    try:
        return fn(*a) if fn is not None else None
    except Exception as exc:
        logger.warning("brake effects: %r failed (%r)", fn, exc)
        return None


# ---------------------------------------------------------------------------- conditional risks
def cond(risk, name, kw):
    """The Brake's ``cond``: the detail of a conditional risk that holds, falsy for none."""
    m, kw = _get(_CFG["manager"]), kw or {}
    try:
        if risk == "save_other" and m is not None:
            return save_other(kw, m.session_file(kw.get("session_name")))
        if risk == "program":
            tab = _get(_CFG["tab_of"], kw)
            if isinstance(tab, dict):
                return program(tab.get("program"), m.session_file(tab.get("session")) if m else None) or None
        if risk == "own_row":
            return None if own_row(kw) else {"row": kw.get("index"), "table": kw.get("aspen_path")}
    except Exception as exc:
        logger.warning("brake effects: %s of %s not judged (%r)", risk, name, exc)
    return None


# A table row the AI inserted itself (insert_row), per session, table and dimension: taking one
# back is no risk to the user's model -- a stray row the AI made, as when a 2-D stoichiometry
# table grew an extra column -- so remove_row asks only for a row it did not insert. Counted
# (not tracked by index: rows shift) and in memory: a server restart forgets them, and the
# removal asks again.
_OWN_ROWS: dict[tuple, int] = {}


def _row_key(kw) -> tuple:
    dim = kw.get("dimension", 0)
    return (str(kw.get("session_name") or ""), str(kw.get("aspen_path") or "").rstrip("\\").lower(),
            dim if isinstance(dim, int) else 0)


def own_row(kw) -> bool:
    """Whether the table ``remove_row`` names has a row the AI inserted in that dimension."""
    return _OWN_ROWS.get(_row_key(kw or {}), 0) > 0


def note_rows(name, kw, res) -> None:
    """After the AI's own insert_row / remove_row ran: count the row it added, or one taken
    back. A result that is not a success (text that does not begin "Inserted" / "Removed")
    counts nothing."""
    key, text = _row_key(kw or {}), res if isinstance(res, str) else ""
    if name == "insert_row" and text.startswith("Inserted row"):
        _OWN_ROWS[key] = _OWN_ROWS.get(key, 0) + 1
    elif name == "remove_row" and text.startswith("Removed") and _OWN_ROWS.get(key, 0) > 0:
        _OWN_ROWS[key] -= 1


def save_other(kw, own_file) -> dict | None:
    """save_simulation's risk: ``file_path`` is not the session's own file and it -- or its
    X.apw / X.def, which Aspen's save overwrites too -- exists. The file then: {"file", "path",
    "size", "mtime", "exists": the file itself, "sidecars", "owner": its model's id or None}."""
    path = (kw or {}).get("file_path")
    if not path or not own_file:
        return None
    full = os.path.abspath(str(path))
    if model_registry.key(full) == model_registry.key(own_file) or os.path.isdir(full):
        return None                                         # its own file; a folder is refused
    side = sorted(checkpoints._sidecars(full))
    try:
        st, there = os.stat(full), True
    except OSError:
        if not side:
            return None                                     # a new file
        st, there = os.stat(os.path.splitext(full)[0] + side[0]), False
    return {"file": os.path.basename(full), "path": full, "size": st.st_size, "mtime": st.st_mtime,
            "exists": there, "sidecars": side, "owner": model_registry.find(full)}


def program(tab_program, model_file) -> list[dict]:
    """workbench_run's risk -- the steps that would run (turned-off ones left out) the AI's own
    call would be asked about: a removal (a block, a stream, a component: wb_plan.classes'
    destructive; not a disconnect) -- {"sid", "step", "do", "what": its names} -- and
    a save statement that would overwrite another file, its path resolved as the program does
    (a relative one beside the model file; one with a {variable} is known only as it runs:
    ``maybe``) -- {"sid", "step", "do": "save", "file", "path", "maybe", and save_other's
    facts}. ``step``: 1-based, nested bodies counted. [] when none."""
    out, here = [], os.path.dirname(os.path.abspath(model_file)) if model_file else None
    runs = wb_plan.active(tab_program) if isinstance(tab_program, list) else []
    live = {st.get("id") for st in _walk(runs)}
    gone = set(wb_plan.classes(runs)["destructive"])
    for i, st in enumerate(_walk(tab_program or []), 1):
        if st.get("id") not in live:
            continue                                        # turned off: it does not run
        if st.get("do") != "save" and st.get("id") in gone:
            out.append({"sid": st.get("id"), "step": i, "do": st.get("do"), "what": wb_plan.what(st)})
            continue
        text = str(st.get("path") or "").strip() if st.get("do") == "save" else ""
        if not text:
            continue                                        # none, or a save to its own file
        if _VAR.search(text):
            out.append({"sid": st.get("id"), "step": i, "do": "save", "file": re.split(r"[\\/]", text)[-1],
                        "path": text, "maybe": True})
            continue
        full = text if os.path.isabs(text) or here is None else os.path.join(here, text)
        d = save_other({"file_path": full}, model_file)
        if d:
            out.append({"sid": st.get("id"), "step": i, "do": "save", **d, "maybe": False})
    return out


def _walk(program):
    for st in program if isinstance(program, list) else ():
        if isinstance(st, dict):
            yield st
            for key in _NESTED:
                yield from _walk(st.get(key) or [])


# ---------------------------------------------------------------------------- the card
def hook(name, kw, session, detail=None) -> dict:
    """intercept's ``hooks.effects``: ``effects`` with configure()'s manager and flowsheet, the
    AI's current change group."""
    m = _get(_CFG["manager"])
    if m is None:
        return {}
    fs = _get(_CFG["flowsheet"], session) if session else None
    return effects(m, name, kw, session, detail, flowsheet=fs, group=journal.GROUPS.current())


def effects(manager, name, kw, session=None, detail=None, *, flowsheet=None, group=None) -> dict:
    """{"risky", "more", "effects", "cp"} of card ``name(kw)`` (the module docstring).
    ``detail``: the conditional risk's (``cond``); ``flowsheet``: the session's as the window
    last read it; ``group``: the AI's change group (a restore point it already has)."""
    kw = {k: v for k, v in (kw or {}).items() if v is not None}
    c = _Card(manager, session or kw.get("session_name"), flowsheet)
    try:
        fn = _BUILD.get(name)
        if fn is not None:
            fn(c, kw, detail)
        if c.cp is None:
            c.cp = _cp(manager, name, c.session, group)
    except Exception as exc:
        logger.warning("brake effects: %s's card incomplete (%r)", name, exc)
    return {"risky": c.risky[:8], "more": c.more, "effects": c.fx[:8], "cp": c.cp}


class _Card:
    """One card being written: its lines, and the tree reads it may still make."""

    def __init__(self, manager, session, flowsheet):
        self.m, self.session, self.fs = manager, session, flowsheet if isinstance(flowsheet, dict) else None
        self.risky, self.fx, self.more, self.cp = [], [], 0, None
        self.end, self._tree = time.perf_counter() + COM_BUDGET_S, False

    def add(self, code, zh, en, **facts):
        self.fx.append({"code": code, **facts, "text": {"zh": zh, "en": en}})

    @staticmethod
    def com() -> bool:
        """On the thread that owns the COM objects."""
        return threading.get_ident() == (_CFG["thread"] or threading.main_thread().ident)

    def fault(self, exc) -> None:
        """A tree read that raised Aspen's internal fault (probes._fault): the session is flagged
        (manager.note_fault: its runs would never return) and the card reads the tree no more --
        the window's flowsheet stands in, as when the budget is spent."""
        if not knowledge_tools.server_fault(exc):
            return
        self._tree, self.end = None, 0.0
        note = getattr(self.m, "note_fault", None)
        if note is not None:
            try:
                note(self.session, exc, tool="brake effects")
            except Exception as e:
                logger.warning("brake effects: fault of %s not flagged (%r)", self.session, e)

    def tree(self):
        """The session's tree, while the budget lasts and only on the COM objects' thread."""
        if self._tree is False:
            self._tree = None
            if self.session and self.com():
                self._tree = probes._tree(_get(self.m.get_app, self.session))
        return self._tree if self._tree is not None and time.perf_counter() < self.end else None

    def sessions(self) -> list:
        """The open sessions (alive, when that may be asked here)."""
        if self.com():
            return list(_get(self.m.session_names) or ())
        return list(getattr(self.m, "_session_files", None) or ())


def _cp(manager, name, session, group) -> dict:
    """The restore point taken before the call: restore_points.plan() for a tool whose row has
    ``cp`` -- or none: the group's was too slow to make (intercept tries no other)."""
    spec = intercept.TOOLS.get(name)
    if spec is None or spec.cp is None or not session:
        return {"tier": "none", "why": "every_model" if name == "close_aspen_plus" else None, "est_s": 0.0}
    gid = group.get("id") if isinstance(group, dict) else group
    slow = intercept._CP_SLOW.get((manager.model_id(session), gid)) if spec.cp == "group" and gid else None
    if slow is not None:
        return {"tier": "skip", "why": "slow", "slow_s": slow, "est_s": 0.0}
    return restore_points.plan(manager, session, intercept._CP_REASON.get(name) or intercept._CP_REASON[spec.cp],
                               group=group if spec.cp == "group" else None)


# -- removals
def _block(c, block):
    """{"block", "type", "ports": {stream: port} | None, "streams", "found"}: the block's own
    connections read, else the flowsheet's streams from / to it."""
    d = {"block": block, "type": None, "ports": None, "streams": [], "found": None}
    t = c.tree()
    if t is not None:
        node = probes._find(t, rf"\Data\Blocks\{block}")
        d["found"] = node is not None
        if node is not None:
            info = probes._details(t, r"\Data\Blocks", block, node, fault=c.fault)
            d["type"], d["ports"] = info.get("type"), info.get("connections")
    fb = next((b for b in (c.fs or {}).get("blocks") or [] if b.get("name") == block), None)
    if d["found"] is None and fb is not None:
        d["found"] = True
    d["type"] = AL.loc(rf"\Data\Blocks\{block}", d["type"] or (fb or {}).get("type")).get("type")
    d["streams"] = list(d["ports"]) if d["ports"] is not None else \
        [s["name"] for s in (c.fs or {}).get("streams") or [] if block in (s.get("from"), s.get("to"))]
    return d


def _block_fx(c, kw, detail, block=None):
    b = _block(c, block or str(kw.get("block_name") or ""))
    c.risky.append({"code": "remove_block", **b})
    if b["found"] is False:
        return c.add("not_found", f"模型中沒有單元 {b['block']}：此呼叫會失敗，不會刪除任何項目",
                     f"The model has no block {b['block']}: the call fails and removes nothing", block=b["block"])
    zh, en = (f"（{b['type']}）", f" ({b['type']})") if b["type"] else ("", "")
    c.add("block_removed", f"刪除單元 {b['block']}{zh}及其所有輸入", f"Deletes block {b['block']}{en} and all its inputs",
          block=b["block"], type=b["type"])
    if b["streams"]:
        c.add("streams_loose", f"與其連接的物流 {_names(b['streams'], 'zh')} 將斷開",
              f"Streams {_names(b['streams'], 'en')}, connected to it, are left unconnected", streams=b["streams"],
              ports=b["ports"])
    c.add(*_UNDO)


def _stream_fx(c, kw, detail, stream=None):
    s = str(stream or kw.get("stream_name") or "")
    d, t = {"stream": s, "from": None, "to": None, "found": None}, c.tree()
    if t is not None:
        _, ends = probes._ends(t, s)
        if ends is not None:
            d["found"] = True
            for blk, port in ends:
                d["from" if "(OUT)" in str(port).upper() else "to"] = blk
    fs = next((x for x in (c.fs or {}).get("streams") or [] if x.get("name") == s), None)
    if d["found"] is None and fs is not None:
        d.update(found=True, **{k: fs.get(k) for k in ("from", "to")})
    c.risky.append({"code": "remove_stream", **d})
    a, b = d["from"], d["to"]
    zh, en = ((f"原本從 {a} 接到 {b}", f"from {a} to {b}") if a and b else (f"原本是 {b} 的進料", f"a feed of {b}") if b
              else (f"原本是 {a} 的產品", f"a product of {a}") if a else ("未連接任何單元", "connected to no block"))
    c.add("stream_removed", f"刪除物流 {s}（{zh}）", f"Deletes stream {s} ({en})", stream=s, **{"from": a, "to": b})
    ends = [x for x in (a, b) if x]
    if ends:
        c.add("ports_empty", f"{'、'.join(ends)} 上與其連接的埠將空出",
              f"The port it was on at {', '.join(ends)} becomes empty", blocks=ends)
    c.add(*_UNDO)


def _component_fx(c, kw, detail):
    comp = str(kw.get("component_id") or "")
    c.risky.append({"code": "remove_component", "component": comp})
    c.add("component_removed", f"從成分清單刪除 {comp}；所有物流與單元中與其相關的輸入一併刪除",
          f"Removes {comp} from the components; every stream and block input about it goes too", component=comp)
    c.add(*_UNDO)


def _rxnset_fx(c, kw, detail):
    rs, no = str(kw.get("reaction_set_name") or ""), kw.get("reaction_no")
    users = _users(c, rs)
    c.risky.append({"code": "remove_reaction" if no is not None else "remove_reaction_set", "rxnset": rs,
                    "reaction": no, "users": users})
    if no is not None:
        c.add("reaction_removed", f"刪除反應集 {rs} 的第 {no} 個反應", f"Deletes reaction {no} of reaction set {rs}",
              rxnset=rs, reaction=no)
    else:
        c.add("rxnset_removed", f"刪除反應集 {rs} 及其所有反應", f"Deletes reaction set {rs} and all its reactions",
              rxnset=rs)
        c.add("reactors_unset", f"使用此反應集的反應器{' ' + _names(users, 'zh') if users else ''}將缺少反應設定",
              f"The reactors using it{' (' + _names(users, 'en') + ')' if users else ''} are left without reactions",
              users=users)
    c.add(*_UNDO)


def _row_label(c, path, row, dimension=0):
    """Row ``row``'s label in table ``path`` (its element's name: a component's ID in a
    per-component table), read while the budget lasts; None when not read or out of range."""
    t = c.tree()
    node = probes._find(t, path) if t is not None and dimension in (None, 0) else None
    if node is None:
        return None
    try:
        i, kids = int(row), knowledge_tools._children(node.Elements)    # not Item(i): it can fault Aspen
        name = str(dispid.get(kids[i], "Name") or "").strip() if 0 <= i < len(kids) and kids[i] is not None else ""
        return name or None
    except Exception as exc:
        c.fault(exc)
        return None


def _users(c, rs) -> list:
    """The flowsheet's reactors whose reaction sets (Input\\RXN_ID) name ``rs``, as far as the
    budget reads; [] when none was read."""
    out = []
    for b in (c.fs or {}).get("blocks") or []:
        t = c.tree()
        if t is None:
            break
        if str(b.get("type") or "").upper() in _REACTORS:
            vals = probes._values(probes._find(t, rf"\Data\Blocks\{b['name']}\Input\RXN_ID"), fault=c.fault) or []
            if any(str(v or "").upper() == rs.upper() for v in vals):
                out.append(b["name"])
    return out


def _item_fx(c, kw, detail):
    """remove_side_duty / remove_element / remove_row: where it is, in words (aspen_labels);
    remove_element under Blocks or Streams is a block's or a stream's removal. The risky item's
    ``say`` names the element or row for the AI's texts (brake.what): "stream HOT", "Reactions ›
    R1", "Components › Specifications › Type, row 0 (WATER)" -- a row's label read from the tree
    while the budget lasts (``label``)."""
    if "stage" in kw:
        path = rf"\Data\Blocks\{kw.get('block_name')}\Input\HEATER_DUTY\{kw.get('stage')}"
        typ = next((b.get("type") for b in (c.fs or {}).get("blocks") or [] if b.get("name") == kw.get("block_name")),
                   "RadFrac")
    else:
        folder = str(kw.get("aspen_path") or "").rstrip("\\")
        name = str(kw.get("name") or "").split("!", 1)[0]
        if name and folder.casefold() in (r"\data\blocks", r"\data\streams"):
            blk = folder.casefold() == r"\data\blocks"
            (_block_fx if blk else _stream_fx)(c, kw, detail, name)
            c.risky[-1]["say"] = f"{'block' if blk else 'stream'} {name}"
            return None
        path, typ = (folder + "\\" + name) if name else folder, None
    lc = AL.loc(path, typ)
    zh, en = AL.text(lc, "full", "zh"), AL.text(lc, "full", "en")
    row = kw.get("index")
    item = {"code": "remove_item", "path": path, "row": row}
    if row is not None:
        item["label"] = _row_label(c, path, row, kw.get("dimension"))
        item["say"] = f"{en}, row {row}" + (f" ({item['label']})" if item["label"] else "")
    elif "stage" not in kw:
        item["say"] = en
    c.risky.append(item)
    if row is not None:
        c.add("row_removed", f"刪除 {zh} 的第 {row} 列（index {row}）及其下的輸入",
              f"Deletes row {row} of {en} and the inputs under it", path=path, row=row)
    else:
        c.add("item_removed", f"刪除 {zh} 及其下的輸入", f"Deletes {en} and the inputs under it", path=path)
    c.add(*_UNDO)


# -- runs, sessions, files
def _reinit_fx(c, kw, detail):
    run = (_summary(c.m, c.session) or {}).get("run") or {}
    st = {"ok": ("收斂", "converged"), "warn": ("有警告", "with warnings"), "error": ("有錯誤", "with errors")}.get(
        run.get("status"), ("", ""))
    when = _hm(run.get("t"))
    c.risky.append({"code": "reinit_simulation", "session": c.session, "last_run": run.get("t"),
                    "status": run.get("status")})
    c.add("results_cleared", "清除整個模型的結果" + (f"（上次執行：{when}{'，' + st[0] if st[0] else ''}）" if when else ""),
          "Clears the whole model's results" + (f" (last run {when}{', ' + st[1] if st[1] else ''})" if when else ""),
          last_run=run.get("t"), status=run.get("status"))
    c.add("inputs_kept", "輸入不變；下次執行從初始估計開始", "Inputs stay; the next run starts from the initial estimates")
    c.add("results_gone", "結果不會保留，需重新執行模擬", "The results are not kept: run the simulation again")
    c.cp = {"tier": "none", "why": "results_only", "est_s": 0.0}


def _close_fx(c, kw, detail):
    names = [c.session] if kw.get("session_name") else c.sessions()
    for s in names[:NAMES_MAX]:
        f = os.path.basename(c.m.session_file(s) or s)
        sm = _summary(c.m, s)
        un, saved = (sm or {}).get("unsaved") or {}, _hm(((sm or {}).get("save") or {}).get("t"))
        n, more = un.get("n"), bool(un.get("more"))
        c.risky.append({"code": "close_aspen_plus", "session": s, "file": f, "unsaved": n, "more": more})
        c.add("close", f"關閉 {f} 的 Aspen", f"Closes Aspen with {f}", session=s, file=f)
        if sm is None:
            c.add("unsaved_unknown", "存檔後的修改數不明（無變更紀錄）", "Unknown how much changed since the last save (no change log)",
                  session=s)
        elif n:
            at = f"（最後存檔 {saved}）" if saved else ""
            c.add("unsaved_lost", f"存檔後的{'超過 ' if more else ' '}{n} 處修改將遺失{at}",
                  f"The {'more than ' if more else ''}{n} change{'s' if n != 1 or more else ''} since the last save"
                  f"{f' ({saved})' if saved else ''} {'are' if n != 1 or more else 'is'} lost",
                  session=s, n=n, more=more, saved=((sm or {}).get("save") or {}).get("t"))
        else:
            c.add("nothing_unsaved", "存檔後沒有記錄到修改", "No change recorded since the last save", session=s)
    c.add("undetected_lost", "在 Aspen 視窗中修改但未偵測到的部分也會遺失",
          "Edits made in Aspen's own window that were not detected are lost too")
    c.add("workbench_kept", "工作台的分頁、程式與便條均保留", "The workbench's tabs, programs and notes stay")


def _new_fx(c, kw, detail):
    name = str(kw.get("project_name") or "").strip()
    name = name[:-4] if name.lower().endswith(".bkp") else name
    folder = kw.get("destination_folder")
    if folder:
        folder = os.path.abspath(str(folder))
    else:                                               # main_tools._default_destination, nothing made
        pkg, cwd = os.path.dirname(os.path.abspath(main_tools._BLANK_TEMPLATE)), os.path.abspath(os.getcwd())
        folder = cwd if cwd != pkg and os.access(cwd, os.W_OK) else os.path.join(os.path.expanduser("~"),
                                                                                 ".aspen-mcp", "simulations")
    path = os.path.join(folder, f"{name}.bkp")
    c.risky.append({"code": "create_new_simulation", "path": path, "exists": os.path.exists(path)})
    if os.path.exists(path):
        c.add("new_exists", f"{path} 已存在：此呼叫將被拒絕，不會覆寫",
              f"{path} exists already: the call is refused and does not overwrite it", path=path)
    else:
        c.add("new_file", f"在 {folder} 建立 {name}.bkp", f"Creates {name}.bkp in {folder}", path=path)
    c.add("new_aspen", "另開一個 Aspen（多占用一套授權）", "Starts another Aspen (one more license in use)")
    c.cp = {"tier": "none", "why": "new_file", "est_s": 0.0}


def _save_fx(c, kw, detail):
    d = detail if isinstance(detail, dict) else save_other(kw, c.m.session_file(c.session))
    if not d:
        c.cp = {"tier": "none", "why": None, "est_s": 0.0}
        return
    own, owner = c.m.model_id(c.session), d.get("owner")
    held = next((s for s in (c.sessions() if owner else ()) if s != c.session and c.m.model_id(s) == owner), None)
    c.risky.append({"code": "save_other", **d, "owner_session": held})
    f, when = d["file"], _hm(d["mtime"], day=True)
    if not d["exists"]:
        side = ", ".join(d["sidecars"])
        c.add("overwrite_sidecars", f"覆寫 {f} 旁邊的 {side}（{when} 修改；Aspen 存檔時一起覆寫）",
              f"Overwrites the {side} beside {f} (modified {when}; Aspen's save writes it too)", **_pick(d))
    else:
        theirs = bool(owner and owner != own)
        whose = ("，屬於另一個模型" + (f"（已開啟為模型「{held}」）" if held else "")) if theirs else ""
        other = ("; another model's file" + (f" (open as model '{held}')" if held else "")) if theirs else ""
        c.add("overwrite", f"覆寫 {f}（{when} 修改{whose}）", f"Overwrites {f} (modified {when}{other})", **_pick(d),
              owner_session=held)
    c.add("backup_first", "覆寫前先備份至其所屬模型的還原點", "It is backed up first, to its own model's restore points")
    c.add("session_follows", f"此後模型存檔至 {f}", f"The model saves to {f} from then on", file=f)
    c.cp = {"tier": "backup", "why": "overwrite", "est_s": round(0.1 + d["size"] / restore_points.COPY_BPS, 1)}


def _program_fx(c, kw, detail):
    tab = _get(_CFG["tab_of"], kw) or {}
    items = detail if isinstance(detail, list) else \
        program(tab.get("program"), c.m.session_file(tab.get("session") or c.session)) if tab else []
    saves = [s for s in items if s.get("do", "save") == "save"]
    removals = [s for s in items if s.get("do", "save") != "save"]
    title = tab.get("title")
    runs = list(_walk(wb_plan.active(tab.get("program")) if isinstance(tab.get("program"), list) else []))
    steps = [st for st in runs if st.get("do") in _CHANGING or st.get("do") in wb_plan.STRUCTURE]
    c.more = max(0, len(steps) - len(items))
    c.add("program_runs", f"分頁「{title}」的程式會執行" if title else "分頁的程式會執行",
          f"Tab '{title}''s program runs" if title else "The tab's program runs", tab=title)
    for s in removals:                                 # as the remove tools' cards say it
        c.risky.append({"code": "program_remove", "sid": s.get("sid"), "step": s.get("step"), "do": s.get("do"),
                        "what": s.get("what")})
        c.add(*_removal(s), step=s.get("step"), what=s.get("what"))
    for s in saves:
        c.risky.append({"code": "program_save", **_pick(s), "sid": s.get("sid"), "step": s.get("step"),
                        "maybe": s.get("maybe")})
        if s.get("maybe"):
            c.add("program_save_maybe", f"第 {s['step']} 步存到 {s['path']}：路徑含變數，執行時才能確定是否覆寫其他檔案",
                  f"Step {s['step']} saves to {s['path']}: the path has a variable, so whether it overwrites another "
                  "file is known only as it runs", step=s["step"], path=s["path"])
        else:
            c.add("program_save", f"第 {s['step']} 步會覆寫 {s['file']}（{_hm(s.get('mtime'), day=True)} 修改）",
                  f"Step {s['step']} overwrites {s['file']} (modified {_hm(s.get('mtime'), day=True)})", step=s["step"],
                  file=s["file"], path=s.get("path"))
    if saves:
        c.add("backup_first", "程式裡的存檔步驟會先備份目標檔", "Each of its saves backs the target file up first")
    if removals:
        c.add(*_UNDO)
    session = tab.get("session") or c.session
    if session and any(st.get("do") in wb_plan.STRUCTURE for st in runs):     # before its first flowsheet change
        c.cp = restore_points.plan(c.m, session, intercept._CP_REASON["group"])
    else:
        c.cp = {"tier": "backup" if saves else "none", "why": "program_saves" if saves else None, "est_s": 0.0}


def _removal(s) -> tuple:
    """(code, zh, en) of a program's removal step (``program``'s item)."""
    w, n, do = s.get("what") or {}, s.get("step"), s.get("do")
    if do == "component":
        comp = w.get("remove")
        return ("program_component", f"第 {n} 步從成分清單刪除 {comp}；所有物流與單元中與其相關的輸入一併刪除",
                f"Step {n} removes {comp} from the components; every stream and block input about it goes too")
    if w.get("port"):
        return ("program_disconnect", f"第 {n} 步將物流 {w.get('stream')} 從 {w.get('block')} 的 {w['port']} 斷開（物流保留）",
                f"Step {n} disconnects stream {w.get('stream')} from {w.get('block')} {w['port']} (the stream stays)")
    if w.get("block"):
        return ("program_block", f"第 {n} 步刪除單元 {w['block']} 及其所有輸入；與其連接的物流將斷開",
                f"Step {n} deletes block {w['block']} and all its inputs; the streams on it are left unconnected")
    return ("program_stream", f"第 {n} 步刪除物流 {w.get('stream')}", f"Step {n} deletes stream {w.get('stream')}")


_BUILD = {"remove_block": _block_fx, "remove_stream": _stream_fx, "remove_component": _component_fx,
          "remove_reaction_set": _rxnset_fx, "remove_reaction": _rxnset_fx, "remove_side_duty": _item_fx,
          "remove_element": _item_fx, "remove_row": _item_fx, "reinit_simulation": _reinit_fx,
          "close_aspen_plus": _close_fx, "create_new_simulation": _new_fx, "save_simulation": _save_fx,
          "workbench_run": _program_fx}


# ---------------------------------------------------------------------------- since the proposal
def since_changes(model, t) -> int:
    """How many changes the model's journal has after ``t`` (a card's proposal): input records
    that changed something, anyone's -- the card's "the model changed N times since". 0 without
    the journal."""
    if not model or not t or not journal.enabled():
        return 0
    pg = journal.page(model, limit=SINCE_MAX, after=t) or {}
    return sum(1 for r in pg.get("records") or () if r.get("kind") == "change" and r.get("op") in journal.INPUT_OPS
               and r.get("status") not in ("unchanged", "failed", "refused", "error"))


def refresh(brk) -> bool:
    """The Brake's open cards' ``since_changes`` brought up to date; True when one moved (the
    caller saves its view)."""
    moved = False
    for c in list(getattr(brk, "cards", None) or ()):
        if c.get("status") in brake.PENDING:
            n = since_changes(c.get("model"), c.get("t"))
            if n != c.get("since_changes"):
                c["since_changes"], moved = n, True
    return moved


# ---------------------------------------------------------------------------- helpers
def _summary(manager, session):
    try:
        model = manager.model_id(session) if session and journal.enabled() else None
        return journal.summary(model) if model else None
    except Exception:
        return None


def _pick(d) -> dict:
    return {k: d.get(k) for k in ("file", "path", "size", "mtime", "owner") if d.get(k) is not None}


def _names(names, lang) -> str:
    names = [str(n) for n in names]
    head, rest = names[:NAMES_MAX], len(names) - NAMES_MAX
    if lang == "zh":
        return "、".join(head) + (f" 等 {len(names)} 個" if rest > 0 else "")
    return ", ".join(head) + (f" and {rest} more" if rest > 0 else "")


def _hm(t, day=False) -> str:
    """14:02 today (``day``: always with the date, 2026-09-20 14:02); "" for none."""
    if not isinstance(t, (int, float)) or t <= 0:
        return ""
    lt = time.localtime(t)
    same = time.strftime("%Y-%m-%d", lt) == time.strftime("%Y-%m-%d")
    return time.strftime("%H:%M" if same and not day else "%Y-%m-%d %H:%M", lt)
