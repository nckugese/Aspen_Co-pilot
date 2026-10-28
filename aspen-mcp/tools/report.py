"""Change report: what changed in a model -- by whom, when, why (the AI's own words, a
block's note) and what each run did -- as a file a student can hand to a classmate or a
teacher: Markdown, or one self-contained HTML page (inline CSS, no script, nothing fetched).

    tally(records, skip_actors=("user",))   the counts of change records, whole and by actor
                                            (the window's WBC.tally counts the same way)
    overrides(records)                      {id: the later record by someone else that set
                                            the same field again} (WBC.overrides)
    build(model, span, fmt, lang, types, coverage, after, group, now)
                                            {"name", "text", "n", "more", "tally"}

Fields are named where they sit in Aspen (tools/aspen_labels, with the zh-TW gloss); the body
has no backslash -- a \\Data\\ path in free text is named too, a file path cut to its name --
and the appendix maps each name shown to its code path. Reads the journal files only
(journal.page, at most SCAN_MAX records); stdlib + journal + aspen_labels, so
workbench/window.py imports it; no COM, no I/O at import.
"""
from __future__ import annotations

import html
import json
import math
import re
import time
from pathlib import Path

from tools import aspen_labels as AL
from tools import journal

SCAN_MAX = 20000                       # records one report reads
NAMES_MAX = 3                          # names tally lists per kind added / removed
DELTA_TOP, WRITES_TOP, MSGS_TOP = 5, 10, 4
ACTOR_ORDER = ("ai", "user", "program", "optimizer", "external")
_RAN = frozenset({"ok", "warn", "error"})


# ------------------------------------------------------------------------------ tally
def _key(r) -> tuple:
    t = r.get("t")
    return (float(t) if isinstance(t, (int, float)) else 0.0, str(r.get("id") or ""))


def _vpath(r) -> str:
    """A value record's field, lower-cased (Aspen paths are case-insensitive), or ""."""
    tg = r.get("target") if isinstance(r.get("target"), dict) else {}
    ok = r.get("op") == "value" and r.get("status") == "changed" and tg.get("path") and r.get("id")
    return str(tg["path"]).lower() if ok else ""


def overrides(records) -> dict:
    """{record id: the first later record that set the same field again, by someone else}: a
    value one actor set that another changed afterwards (the AI putting back your edit made in
    Aspen's window). An undo of the record itself (its revert_of) is not one. Any order in; the
    window's WBC.overrides answers the same."""
    by, out = {}, {}
    for r in sorted((r for r in records or () if isinstance(r, dict) and _vpath(r)), key=_key):
        p, rev = _vpath(r), r.get("revert_of")
        rev = {str(x) for x in rev} if isinstance(rev, list) else {str(rev)} if rev else set()
        for e in by.get(p, ()):
            if e["id"] not in out and e.get("actor") != r.get("actor") and str(e["id"]) not in rev:
                out[e["id"]] = r
        by.setdefault(p, []).append(r)
    return out


class _Count:
    def __init__(self):
        self.n = dict.fromkeys(("values", "connects", "saves", "failed", "refused", "external"), 0)
        self.objs, self.added, self.removed, self.studies = set(), {}, {}, {}
        self.runs, self.last, self.over = 0, None, 0

    def add(self, r, over=False) -> None:
        op, st = r.get("op"), r.get("status")
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        if over:
            self.over += 1
        if r.get("actor") == "external":
            self.n["external"] += 1
        if st == "refused":
            self.n["refused"] += 1
        elif st == "failed" or (st == "error" and op not in ("run", "reinit", "summary")):
            self.n["failed"] += 1
        elif op == "run":
            if st in _RAN:
                self.runs += 1
                self.last = {"status": st, **{k: r[k] for k in ("errors", "warnings") if k in r}}
        elif op == "reinit":                       # runs nothing: "Reinitialize, then Run" is one run
            return
        elif op == "summary":
            d = str(r.get("do") or "loop")
            self.studies[d] = self.studies.get(d, 0) + 1
        elif st != "changed":
            return
        elif op in ("value", "attr"):
            self.n["values"] += 1
            for kind in ("block", "stream"):
                if tg.get(kind):
                    self.objs.add(f"{kind}:{str(tg[kind]).upper()}")
                    break
        elif op in ("add", "remove"):
            e = (self.added if op == "add" else self.removed).setdefault(str(tg.get("kind") or "item"), {"n": 0, "names": []})
            e["n"] += 1
            name = tg.get("name")
            if name and name not in e["names"] and len(e["names"]) < NAMES_MAX:
                e["names"].append(str(name))
        elif op == "connect":
            self.n["connects"] += 1
        elif op == "save":
            self.n["saves"] += 1

    def out(self, full: bool = False) -> dict:
        n = self.n
        d = {"values": n["values"], "objs": len(self.objs), "added": self.added, "removed": self.removed,
             "connects": n["connects"], "runs": {"n": self.runs, **({"last": self.last} if self.last else {})},
             "studies": self.studies, "saves": n["saves"], "failed": n["failed"], "refused": n["refused"],
             "external": n["external"]}
        if self.over:
            d["overridden"] = self.over
        return d if full else {k: v for k, v in d.items() if v and v != {"n": 0}}


def tally(records, skip_actors=("user",)) -> dict:
    """Counts of change records, whole and ``by`` actor (an actor with nothing to
    count left out; ``skip_actors`` left out entirely). ``values`` / ``objs`` (the distinct
    blocks and streams those values belong to), ``added`` / ``removed`` ({kind: {"n", "names":
    the first NAMES_MAX}}), ``connects``, ``saves``: records whose status is ``changed``;
    ``runs``: run records that ran (ok | warn | error; a Reinitialize is not one: with the run
    after it, it counts once), ``last`` the latest by time
    ({"status"} + its errors / warnings when recorded); ``studies``: summary records by ``do``;
    ``failed``: status failed, or error on anything but a run or a summary (it did not apply);
    ``refused``; ``external``: actor external records of any op and status; ``overridden``
    (only when there are some): values another actor counted here set again later
    (``overrides``). Any order in."""
    skip = set(skip_actors or ())
    top, by = _Count(), {}
    recs = [r for r in records or () if isinstance(r, dict) and r.get("kind", "change") == "change"
            and str(r.get("actor") or "unknown") not in skip]
    over = overrides(recs)
    for r in sorted(recs, key=_key):
        actor, o = str(r.get("actor") or "unknown"), r.get("id") in over
        top.add(r, o)
        by.setdefault(actor, _Count()).add(r, o)
    out = top.out(full=True)
    out["by"] = {a: c.out() for a, c in by.items() if c.out()}
    return out


# ------------------------------------------------------------------------------ words
_W = {
    "zh": dict(
        title="變更紀錄報告", model="模型檔", span="範圍", period="期間", made="產生時間", count="紀錄筆數",
        span_all="全部紀錄", span_today="今天", span_since="{0} 之後", span_group="一組修改：{0}",
        capped="紀錄很多，這份報告只讀了最近 {0} 筆；更早的沒有列入，所以數字是「至少」。",
        read_me="原值與新值都是伺服器在修改前後自己量到的；標成「AI 自述」的是 AI 自己寫的理由，不是量測結果。",
        sum_h="摘要", tl_h="經過", cov_h="這份紀錄記了什麼", app_h="附錄：欄位的代碼路徑",
        app_p="內文用欄位在 Aspen 裡的位置稱呼它；要在 Aspen 裡找到同一個欄位，或請 AI 讀它，用右欄的代碼路徑。",
        app_loc="位置", app_path="代碼路徑", none="此範圍內沒有變更紀錄。", ext_note="其中 {0} 筆是直接在 Aspen 視窗做的，標有「Aspen 視窗」。",
        who_ai="AI", who_user="使用者（工作台）", who_program="程式", who_optimizer="優化器",
        who_external="Aspen 視窗", who_unknown="不明",
        title_ai="AI 的修改", title_user="使用者在工作台的修改", title_program="程式", title_optimizer="優化",
        title_external="使用者在 Aspen 視窗的修改", title_unknown="其他修改",
        src_note="標題取自使用者給 AI 的便條", src_reason="標題取自 AI 自述的理由", by_ai_prog="由 AI 啟動", n_recs="{0} 筆",
        t_values="改了 {0} 個值", t_values_objs="改了 {1} 個單元或物流的 {0} 個值", t_add="新增{0}", t_rm="刪除{0}", t_kind="{0} {1}",
        t_kind_n="{0} 個{1}（{2} 等）", t_connects="接了 {0} 條線",
        t_runs="執行 {0} 次（最後一次：{1}）", t_sweep="掃描 {0} 次", t_seek="調整到目標（Design Spec）{0} 次",
        t_optimize="優化 {0} 次", t_loop="迴圈 {0} 次", t_saves="存檔 {0} 次", t_failed="{0} 筆沒有成功",
        t_refused="{0} 筆被拒絕（沒有執行）", t_sep="；", t_end="。", t_nothing="沒有改到模型。",
        k_block="單元", k_stream="物流", k_component="成分", k_rxnset="反應集", k_reaction="反應", k_chemistry="Chemistry",
        k_row="一列", k_item="項目", list_sep="、",
        o_ok="收斂", o_warn="收斂，{0} 個警告", o_warn_n="收斂，有警告", o_error="有錯誤", o_errors="{0} 個錯誤",
        o_failed="未完成", o_unknown="結果不明", o_done="完成",
        tb_item="項目", tb_all="合計", tb_values="改了的值", tb_objs="涉及的單元／物流", tb_added="新增", tb_removed="刪除",
        tb_connects="接線", tb_runs="執行模擬", tb_studies="掃描／調整／優化", tb_saves="存檔", tb_failed="沒有成功",
        tb_refused="被拒絕",
        r_empty="（空白）", r_unit="（改了單位）", r_basis="（基準 {0} → {1}）", r_attr="（屬性 {0}）", r_new="（新建）",
        r_same="（沒有改變）", r_not="沒有套用", r_said="伺服器回覆：{0}", r_add="新增{0} {1}", r_remove="刪除{0} {1}",
        r_connect="{0} 接到 {1}", r_displaced="，換下 {0}", r_detached="{0} 自 {1} 拆下（接到 {2} 被拒）", r_disconnect="{0} 自 {1} 拆下", r_run="執行模擬：{0}", r_reinit="Reinitialize：{0}",
        r_seq="第 {0} 次執行", r_secs="{0} 秒", r_blocks="有狀況的單元：{0}", r_sweep="掃描 {0}",
        r_seek="調整到目標（Design Spec）：{0}", r_loop="迴圈：{0}", r_loop_n="迴圈", r_sweep_n="掃描", r_seek_n="調整到目標（Design Spec）", r_opt="優化（{0}）", r_opt_n="優化",
        r_restore="還原 {0} 個值", r_points="{0} 點", r_runs="{0} 次", r_conv="{0} 次收斂", r_evals="{0} 次評估",
        r_feasible="{0} 個可行", r_end="結束時為 {0}", fin_restore="模型回到起始值", fin_best="模型停在最佳點",
        fin_last="模型停在最後一點", r_wmore="…還有 {0} 個欄位", r_save="存檔到 {0}", r_backup="（舊檔已先備份）",
        r_save_fail="存檔到 {0} 失敗", r_checkpoint="建立還原點", r_layout="重新排列流程圖", r_reopen="（Aspen 重新開檔）",
        r_patch="改了模型檔", r_open="開啟模型 {0}", r_close="關閉模型 {0}", r_pinch="熱整合分析（Pinch）",
        r_call="{0}（沒有量到改變）", r_begin="開始 {0}，還沒有結束紀錄（還在進行，或伺服器中途被關掉）",
        reason="理由（AI 自述）：{0}", why="積木上的說明：{0}", ext_tag="Aspen 視窗",
        r_over="↳ {0} {1} 改成 {2}", r_over_back="↳ {0} {1} 改回 {2}",
        ext_when="在 Aspen 視窗改的：{0} 之後、{1} 偵測到", ext_found="在 Aspen 視窗改的：{0} 偵測到",
        ext_run="使用者在 Aspen 視窗執行模擬：{0}", ext_save="使用者在 Aspen 視窗存了檔 {0}", side="Aspen 連帶調整",
        in0="上次執行後未變更輸入。", in0_noise="結果仍有變化，可能來自收斂容差或 Reinitialize。",
        in1="上次執行後唯一變更的輸入：", inN="上次執行後變更 {0} 個輸入：",
        joint="這些輸入是一起改的，下面的結果變化無法單獨歸給其中任何一個。", in_more="…還有 {0} 個輸入",
        in_full="（至少這麼多）", in_obj="{0}：{1}", res_h="結果變化（{0} 項，列出前 {1} 項）：", res_h_all="結果變化：",
        res_first="這是這個模型第一次有結果，沒有上一次可以比較。", res_failed="此次執行失敗，Aspen 已清除結果，不做比較。",
        res_none="比較了 {0} 個結果，都沒有變化。", res_partial="（時間有限，只比較了一部分結果）", res_small="（在收斂容差內）",
        msgs="Aspen 訊息：", by_actor="（{0}）", ws_ai="AI", ws_user="使用者", ws_program="程式", ws_optimizer="優化器",
        ws_external="Aspen 視窗", ws_unknown="不明",
        cov_rec="會記下的：AI、使用者在工作台（檢查器輸入的值、執行模擬、儲存模型、套用的點）、程式和優化器對模型的每一次修改——改了哪一格，改之前和改之後的值。這兩個值都是伺服器自己量的。只讀取、沒有修改的動作不列。",
        cov_run="每次執行模擬都記下結果（收斂、警告、錯誤）、上次執行後變更的輸入，以及和上一次相比變化最大的結果。",
        cov_ext_on="直接在 Aspen 視窗做的修改：在下一次比對時記下（AI 下一次動作之前，或離開 Aspen 視窗幾秒後），所以時間寫成「某時之後、某時偵測到」。只改接線，或改了工作台還沒讀過的欄位，可能比對不到。",
        cov_ext_off="直接在 Aspen 視窗做的修改，這個版本的工作台不會記下，所以不在這份報告裡。",
        cov_unrec="不列入紀錄的工具：{0}。", cov_names="欄位名稱依 Aspen 導覽樹的位置與工作台的詞彙表，括號裡是中文說明；代碼路徑見附錄。",
        foot="由 Aspen 工作台依變更紀錄產生 · 模型代號 {0}",
    ),
    "en": dict(
        title="Change report", model="Model file", span="Covers", period="Period", made="Made", count="Records",
        span_all="all records", span_today="today", span_since="after {0}", span_group="one group of changes: {0}",
        capped="There are many records: this report read only the latest {0}, so its numbers are \"at least\".",
        read_me="Every before and after value was measured by the server itself; text marked \"the AI's own reason\" is what the AI wrote, not a measurement.",
        sum_h="Summary", tl_h="What happened", cov_h="What this record covers", app_h="Appendix: code paths of the fields",
        app_p="The text names each field where it sits in Aspen; to find the same field in Aspen, or to have the AI read it, use its code path.",
        app_loc="Where", app_path="Code path", none="No changes were recorded in this range.",
        ext_note="{0} of these records were made directly in Aspen's own window, marked \"Aspen window\".",
        who_ai="AI", who_user="User (workbench)", who_program="Program", who_optimizer="Optimizer",
        who_external="Aspen window", who_unknown="Unknown",
        title_ai="The AI's changes", title_user="The user's changes in the workbench", title_program="Program",
        title_optimizer="Optimization", title_external="Changes made in Aspen's own window", title_unknown="Other changes",
        src_note="titled by the user's note to the AI", src_reason="titled by the AI's own reason", by_ai_prog="started by the AI",
        n_recs="{0} records",
        t_values="changed {0} values", t_values_objs="changed {0} values in {1} blocks or streams", t_add="added {0}",
        t_rm="removed {0}", t_kind="{0} {1}", t_kind_n="{0} {1}s ({2}, ...)",
        t_connects="made {0} connections", t_runs="ran the simulation {0} times (last: {1})", t_sweep="{0} sweeps",
        t_seek="{0} design specs", t_optimize="{0} optimizations", t_loop="{0} loops", t_saves="saved {0} times",
        t_failed="{0} failed", t_refused="{0} refused (not run)", t_sep="; ", t_end=".", t_nothing="nothing changed in the model.",
        k_block="block", k_stream="stream", k_component="component", k_rxnset="reaction set", k_reaction="reaction",
        k_chemistry="Chemistry", k_row="row", k_item="item", list_sep=", ",
        o_ok="converged", o_warn="converged with {0} warnings", o_warn_n="converged with warnings", o_error="errors",
        o_errors="{0} errors", o_failed="did not finish", o_unknown="outcome unknown", o_done="done",
        tb_item="", tb_all="Total", tb_values="Values changed", tb_objs="Blocks / streams involved", tb_added="Added",
        tb_removed="Removed", tb_connects="Connections", tb_runs="Runs", tb_studies="Sweeps / specs / optimizations",
        tb_saves="Saves", tb_failed="Failed", tb_refused="Refused",
        r_empty="(empty)", r_unit=" (unit changed)", r_basis=" (basis {0} → {1})", r_attr=" (attribute {0})", r_new=" (new)",
        r_same=" (no change)", r_not="not applied", r_said="The server said: {0}", r_add="Added {0} {1}",
        r_remove="Removed {0} {1}", r_connect="{0} connected to {1}", r_displaced=", replacing {0}",
        r_detached="{0} detached from {1} (connect to {2} refused)", r_disconnect="Took {0} off {1}",
        r_run="Run simulation: {0}", r_reinit="Reinitialize: {0}", r_seq="run #{0}", r_secs="{0} s",
        r_blocks="Blocks with messages: {0}", r_sweep="Sweep of {0}", r_seek="Design spec on {0}", r_loop="Loop over {0}",
        r_loop_n="Loop", r_sweep_n="Sweep", r_seek_n="Design spec", r_opt="Optimization ({0})",
        r_opt_n="Optimization", r_restore="Put back {0} values", r_points="{0} points",
        r_runs="{0} runs", r_conv="{0} converged", r_evals="{0} evaluations", r_feasible="{0} feasible",
        r_end="ends at {0}", fin_restore="model back at its start values", fin_best="model left at the best point",
        fin_last="model left at the last point", r_wmore="…and {0} more fields", r_save="Saved to {0}",
        r_backup=" (the old file backed up first)", r_save_fail="Saving {0} failed", r_checkpoint="Restore point made",
        r_layout="Redrew the flowsheet", r_reopen=" (Aspen reopened the file)", r_patch="Edited the model file",
        r_open="Opened {0}", r_close="Closed {0}", r_pinch="Heat integration analysis (pinch)",
        r_call="{0} (no change measured)", r_begin="Started {0}: no end recorded (still running, or the server stopped)",
        reason="The AI's own reason: {0}", why="Note on the block: {0}", ext_tag="Aspen window",
        r_over="↳ at {0}, {1} changed it to {2}", r_over_back="↳ at {0}, {1} changed it back to {2}",
        ext_when="Changed in Aspen's window: after {0}, found {1}", ext_found="Changed in Aspen's window: found {0}",
        ext_run="The user ran the simulation in Aspen's window: {0}", ext_save="The user saved {0} in Aspen's window",
        side="Adjusted by Aspen",
        in0="No inputs changed since the last run.", in0_noise="The results moved anyway: convergence tolerance, or a Reinitialize.",
        in1="The only input changed since the last run:", inN="{0} inputs changed since the last run:",
        joint="These inputs changed together: the result changes below cannot be pinned on any one of them.",
        in_more="…and {0} more inputs", in_full=" (at least)", in_obj="{0}: {1}",
        res_h="What changed in the results ({0}, the first {1}):", res_h_all="What changed in the results:",
        res_first="The model's first results: nothing earlier to compare with.",
        res_failed="This run failed and Aspen cleared the results, so nothing is compared.",
        res_none="None of the {0} results compared moved.", res_partial=" (time ran short: only some results compared)",
        res_small=" (within convergence tolerance)", msgs="Aspen's messages:", by_actor=" ({0})",
        ws_ai="AI", ws_user="user", ws_program="program", ws_optimizer="optimizer", ws_external="Aspen window",
        ws_unknown="unknown",
        n_recs_1="1 record", t_values_1="changed 1 value", t_values_objs_one="changed {0} values in 1 block or stream",
        t_values_objs_one_1="changed 1 value in 1 block or stream", t_connects_1="made 1 connection",
        t_runs_1="ran the simulation once ({1})", t_sweep_1="1 sweep", t_seek_1="1 design spec",
        t_optimize_1="1 optimization", t_loop_1="1 loop", t_saves_1="saved once", r_restore_1="Put back 1 value",
        r_points_1="1 point", r_runs_1="1 run", r_evals_1="1 evaluation", r_wmore_1="…and 1 more field",
        in_more_1="…and 1 more input",
        ext_note_1="1 of these records was made directly in Aspen's own window, marked \"Aspen window\".",
        cov_rec="What is recorded: every change to the model by the AI, by the user in the workbench (a value typed in the inspector, Run simulation, Save model, a point applied), by a program or by the optimizer -- which field, and its value before and after. The server measures both values itself. Actions that only read are not listed.",
        cov_run="Every run records how it ended (converged, warnings, errors), the inputs changed since the run before, and the results that moved most.",
        cov_ext_on="Changes made directly in Aspen's own window are recorded at the next check (before the AI's next action, or a few seconds after leaving Aspen's window), so their time reads \"after X, found Y\". A change to connections alone, or to a field the workbench had not read, may be missed.",
        cov_ext_off="Changes made directly in Aspen's own window are not recorded by this version of the workbench, so they are not in this report.",
        cov_unrec="Tools whose changes are not listed: {0}.",
        cov_names="Fields are named by where they sit in Aspen's navigation tree and by the workbench's glossary; their code paths are in the appendix.",
        foot="Made by the Aspen Workbench from its change log · model id {0}",
    ),
}
TABLE_ROWS = ("values", "objs", "added", "removed", "connects", "runs", "studies", "saves", "failed", "refused")


def count(c: dict, k: str) -> int:
    """One number of a tally (or an actor's part) for the report's table: kinds added or
    removed, studies and runs summed to their total."""
    v = c.get(k)
    if isinstance(v, dict):
        return int(v.get("n") or 0) if k == "runs" else \
            sum(int(e.get("n") or 0) if isinstance(e, dict) else int(e or 0) for e in v.values())
    return int(v or 0)


def _lang(x) -> str:
    s = str(x or "").lower()
    return "zh" if s == "zh" or s.startswith(("zh-", "zh_")) else "en"


def _num(v) -> str:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if not math.isfinite(v):
        return str(v)
    g = float(f"{v:.6g}")
    return str(int(g)) if g.is_integer() and abs(g) < 1e15 else repr(g)


def _pair(b, a) -> tuple:
    """Two numbers as text, with as many digits as it takes to tell them apart (6 to 10), as
    runlog.item_text does."""
    sb, sa = _num(b), _num(a)
    if sb == sa and b != a and all(isinstance(x, float) and math.isfinite(x) for x in (a, b)):
        for n in range(7, 11):
            sb, sa = f"{b:.{n}g}", f"{a:.{n}g}"
            if sb != sa:
                break
    return sb, sa


def _clock(t, day=False) -> str:
    if not isinstance(t, (int, float)):
        return "--:--"
    lt = time.localtime(t)
    return f"{lt.tm_mon}/{lt.tm_mday} {lt.tm_hour:02d}:{lt.tm_min:02d}" if day else f"{lt.tm_hour:02d}:{lt.tm_min:02d}"


def _stamp(t) -> str:
    return time.strftime("%Y/%m/%d %H:%M", time.localtime(t)) if isinstance(t, (int, float)) else "—"


# ------------------------------------------------------------------------------ the report
class _Doc:
    """One report being written: its words, the block types, the labels shown -> code paths."""

    _PATH = re.compile(r"\\Data\\[^\s,;()\[\]\"'<>]+")
    _FILE = re.compile(r"(?:[A-Za-z]:\\|\\\\)[^\s\"'<>|]*")

    def __init__(self, lang, types):
        self.lang, self.w, self.types, self.refs = lang, _W[lang], types, {}
        self.colon = "：" if lang == "zh" else ": "

    def t(self, key, *a) -> str:
        """The word ``key`` with ``a`` filled in; ``key_1`` when the first number is 1 and the
        language has one (English singulars)."""
        if a and a[0] == 1 and f"{key}_1" in self.w:
            key += "_1"
        s = self.w.get(key, key)
        return s.format(*a) if a else s

    def pick(self, prefix, key, other) -> str:
        """The word ``prefix_key``, else ``prefix_other``."""
        return self.t(f"{prefix}_{key}" if f"{prefix}_{key}" in self.w else f"{prefix}_{other}")

    def label(self, path, form="full", loc=None) -> str:
        """A field in words (never a backslash); remembered for the appendix."""
        path = str(path or "")
        blk = journal.label(path).get("block")
        lc = loc if isinstance(loc, dict) else AL.loc(path, self.types.get(blk) if blk else None)
        text = AL.text(lc, form, self.lang) or path.rsplit("\\", 1)[-1]
        if path.startswith("\\") and path not in self.refs:
            self.refs[path] = text if form == "full" else (AL.text(lc, "full", self.lang) or text)
        return text

    def _named(self, m) -> str:
        path = m.group(0).rstrip(".:")
        return self.label(path, "short") + m.group(0)[len(path):]

    def clean(self, s) -> str:
        """Free text for the body: whitespace folded, \\Data\\ paths named, file paths cut to
        their name, no backslash left."""
        s = self._PATH.sub(self._named, " ".join(str(s if s is not None else "").split()))
        s = self._FILE.sub(lambda m: re.split(r"[\\/]", m.group(0).rstrip("\\"))[-1], s)
        return s.replace("\\", "/")

    def who(self, actor) -> str:
        return self.pick("who", actor, "unknown")

    def kind(self, k) -> str:
        return self.pick("k", k, "item")

    def outcome(self, st, warns=0, errs=0) -> str:
        if st == "ok":
            return self.t("o_ok")
        if st == "warn":
            return self.t("o_warn", warns) if warns else self.t("o_warn_n")
        if st == "error":
            return self.t("o_errors", errs) if errs and errs > 1 else self.t("o_error")
        return self.t("o_failed") if st in ("failed", "refused") else self.t("o_unknown")

    # -------------------------------------------------------------- counts in words
    def sentence(self, c: dict) -> str:
        """A tally (or one actor's part) as a sentence."""
        sep, parts = self.t("list_sep"), []
        if c.get("values"):
            key = "t_values_objs_one" if c.get("objs") == 1 and "t_values_objs_one" in self.w else "t_values_objs"
            parts.append(self.t(key, c["values"], c["objs"]) if c.get("objs") else self.t("t_values", c["values"]))
        for key, verb in (("added", "t_add"), ("removed", "t_rm")):
            kinds = []
            for k, e in (c.get(key) or {}).items():
                names = sep.join(self.clean(x) for x in e["names"])
                kinds.append(self.t("t_kind", self.kind(k), names) if e["n"] <= len(e["names"])
                             else self.t("t_kind_n", e["n"], self.kind(k), names))
            if kinds:
                parts.append(self.t(verb, sep.join(kinds)))
        if c.get("connects"):
            parts.append(self.t("t_connects", c["connects"]))
        runs = c.get("runs") or {}
        if runs.get("n"):
            last = runs.get("last") or {}
            parts.append(self.t("t_runs", runs["n"], self.outcome(last.get("status"), last.get("warnings") or 0,
                                                                   last.get("errors") or 0)))
        for d, n in (c.get("studies") or {}).items():
            parts.append(self.t(f"t_{d}" if f"t_{d}" in self.w else "t_loop", n))
        for k in ("saves", "failed", "refused"):
            if c.get(k):
                parts.append(self.t(f"t_{k}", c[k]))
        return (self.t("t_sep").join(parts) + self.t("t_end")) if parts else self.t("t_nothing")

    # -------------------------------------------------------------- one record
    def val(self, d) -> str:
        if not isinstance(d, dict):
            return "—" if d is None else self.clean(_num(d))
        if d.get("show") is not None:
            return self.clean(d["show"])
        v = d.get("value")
        return self.t("r_empty") if v is None or v == "" else self.clean(_num(v))

    def change(self, b, a) -> list:
        b, a = b if isinstance(b, dict) else {"value": b}, a if isinstance(a, dict) else {"value": a}
        ub, ua = b.get("unit"), a.get("unit")
        moved = bool(ub or ua) and ub != ua
        sb, sa = self.val(b), self.val(a)
        if sb == sa and b.get("show") is None and a.get("show") is None:
            sb, sa = (self.clean(x) for x in _pair(b.get("value"), a.get("value")))
        out = [("v", sb)] + ([("t", f" {ub}")] if moved and ub else []) + [("t", " → "), ("v", sa)]
        out += [("t", f" {ua}")] if ua else []
        if moved:
            out.append(("q", self.t("r_unit")))
        elif (b.get("basis") or a.get("basis")) and b.get("basis") != a.get("basis"):
            out.append(("q", self.t("r_basis", b.get("basis") or "—", a.get("basis") or "—")))
        return out

    def row(self, r: dict) -> dict:
        """{"t", "who", "text": pieces, "subs": [(level, pieces)], "note": (kind, text) | None, "msgs", "bad"}."""
        op, st, tg = r.get("op"), r.get("status"), r.get("target") if isinstance(r.get("target"), dict) else {}
        bad, subs, ext = st in ("failed", "refused") or (st == "error" and op not in ("run", "reinit", "summary")), [], r.get("actor") == "external"
        name = lambda: tg.get("name") or str(tg.get("path") or "").rsplit("\\", 1)[-1]  # noqa: E731
        if r.get("kind") == "begin":
            text = [("t", self.t("r_begin", r.get("tool") or r.get("do") or "?"))]
        elif op in ("value", "attr"):
            text = [("t", self.label(tg.get("path"), "full", r.get("loc")))]
            if op == "attr":
                text.append(("q", self.t("r_attr", tg.get("attr", r.get("attr")))))
            if bad:
                text += [("t", " → "), ("v", self.val(r.get("req") or r.get("after")))]
            elif st == "changed" and "before" in r:
                text += [("t", self.colon)] + self.change(r["before"], r.get("after"))
            else:
                text += [("t", " = "), ("v", self.val(r.get("after") or r.get("req"))),
                         ("q", self.t("r_new" if r.get("created") else "r_same"))]
        elif op in ("add", "remove"):
            text = [("t", self.t("r_add" if op == "add" else "r_remove", self.kind(tg.get("kind")),
                                 self.clean(name()) + (f" ({tg['type']})" if tg.get("type") else "")))]
        elif op == "connect":
            s = tg.get("stream") or self.t("list_sep").join(map(str, r.get("after") or []))
            where = " ".join(str(x) for x in (tg.get("block"), tg.get("port") or tg.get("field")) if x)
            asked = r.get("asked") if isinstance(r.get("asked"), dict) else {}
            if r.get("detached"):                  # probes: a refused connect took it off anyway (V15)
                to = " ".join(str(asked[k]) for k in ("block", "port") if asked.get(k)) or "?"
                text = [("t", self.clean(self.t("r_detached", s, where, to)))]
            elif journal.is_disconnect(r):         # disconnect_stream, a program's, an undo's
                text = [("t", self.clean(self.t("r_disconnect", s, where)))]
            else:
                gone = self.t("r_displaced", self.t("list_sep").join(map(str, r["displaced"]))) if r.get("displaced") else ""
                text = [("t", self.clean(self.t("r_connect", s, where) + gone))]
        elif op in ("run", "reinit"):
            text, subs = self.run(r, ext)
        elif op in ("summary", "restore"):
            text, subs = self.loop(r)
        elif op == "save":
            w = r["writes"][0] if isinstance(r.get("writes"), list) and r["writes"] and isinstance(r["writes"][0], dict) else {}
            f = self.clean(w.get("path") or r.get("file") or tg.get("path") or "")
            if ext:
                text = [("t", self.t("ext_save", f))]
            else:
                text = [("t", self.t("r_save_fail" if bad else "r_save", f) + ("" if bad or not w.get("backup") else self.t("r_backup")))]
        elif op == "checkpoint":
            text = [("t", self.t("r_checkpoint"))]
        elif op == "patch":
            text = [("t", self.t("r_layout" if r.get("tool") == "layout_flowsheet" else "r_patch")
                     + (self.t("r_reopen") if r.get("reopened") else ""))]
        elif op in ("open", "close"):
            text = [("t", self.t(f"r_{op}", self.clean(r.get("file") or r.get("session") or "")))]
        elif op == "analysis":
            text = [("t", self.t("r_pinch"))]
        else:
            text = [("t", self.t("r_call", r.get("tool") or op or "?"))]
        if ext and op in ("value", "attr", "add", "remove", "connect"):
            since, found = r.get("since"), r.get("t")
            subs.insert(0, (1, [("q", self.t("ext_when", _clock(since), _clock(found)) if isinstance(since, (int, float))
                                  else self.t("ext_found", _clock(found)))]))
        if r.get("side"):
            subs.insert(0, (1, [("q", self.t("side"))]))
        if bad:
            if op not in ("run", "reinit"):               # (a run's outcome already says it)
                text.append(("bad", f" · {self.t('r_not')}"))
            if r.get("result"):
                subs.append((1, [("q", self.t("r_said", self.clean(str(r["result"])[:300])))]))
        note = None
        why = str(r.get("reason") or "").strip()
        if why:
            own = r.get("reason_src") == "why"
            note = ("why" if own else "reason", self.t("why" if own else "reason", self.clean(why)))
        return {"t": r.get("t"), "who": r.get("actor"), "text": text, "subs": subs, "note": note,
                "ext": ext and op not in ("run", "reinit", "save"), "bad": bad}   # (those say "Aspen's window")

    def run(self, r, ext) -> tuple:
        st, op = r.get("status"), r.get("op")
        warns, errs = int(r.get("warnings") or 0), int(r.get("errors") or 0)
        if op == "reinit":
            text = [("t", self.t("r_reinit", self.t("o_done") if st == "ok" else self.t("o_failed")))]
        else:
            how = self.outcome(st, warns, errs)
            text = [("t", self.t("ext_run", how) if ext else self.t("r_run", how))]
        bits = ([self.t("r_seq", r["seq"])] if r.get("seq") else []) + \
               ([self.t("r_secs", _num(round(float(r["secs"]), 1)))] if isinstance(r.get("secs"), (int, float)) else [])
        if bits:
            text.append(("q", " · " + " · ".join(bits)))
        subs = []
        blocks = list(r["blocks"]) if isinstance(r.get("blocks"), dict) else []
        if blocks and st != "ok":
            subs.append((1, [("t", self.t("r_blocks", self.t("list_sep").join(self.clean(b) for b in blocks[:12])))]))
        subs += self.inputs(r.get("inputs"), r.get("delta"))
        subs += self.delta(r.get("delta"), st)
        msgs = r.get("msgs")
        lines = [x for x in (msgs if isinstance(msgs, list) else str(msgs or "").split("\n")) if str(x).strip()]
        if lines and st != "ok":
            subs.append((1, [("t", self.t("msgs"))]))
            subs += [(2, [("q", self.clean(x))]) for x in lines[:MSGS_TOP]]
        return text, subs

    def inputs(self, inp, delta) -> list:
        if not isinstance(inp, dict):
            return []
        n, out = int(inp.get("n") or 0), []
        items = [(2, self.input_item(i)) for i in inp.get("items") or [] if isinstance(i, dict)]
        items += [(2, self.obj_item(o)) for o in inp.get("objs") or [] if isinstance(o, dict)]
        if not n:
            moved = isinstance(delta, dict) and delta.get("items")
            return [(1, [("t", self.t("in0"))] + ([("q", " " + self.t("in0_noise"))] if moved else []))]
        out.append((1, [("t", self.t("in1") if n == 1 else self.t("inN", n))] + ([("q", self.t("in_full"))] if inp.get("full") else [])))
        out += items
        if inp.get("more"):
            out.append((2, [("q", self.t("in_more", inp["more"]))]))
        if n > 1:
            out.append((1, [("q", self.t("joint"))]))
        return out

    def input_item(self, i) -> list:
        who = self.pick("ws", i.get("actor"), "unknown") if i.get("actor") else ""
        return [("t", self.label(i.get("path"), "short") + self.colon)] + \
            self.change(i.get("before"), i.get("after")) + ([("q", self.t("by_actor", who))] if who else [])

    def obj_item(self, o) -> list:
        op = o.get("op")
        if op in ("add", "remove") and o.get("name"):
            return [("t", self.t("r_add" if op == "add" else "r_remove", self.kind(o.get("kind")), self.clean(o["name"])))]
        where = self.label(o["path"], "short") if str(o.get("path") or "").startswith("\\") else self.clean(o.get("path") or "")
        return [("t", self.t("in_obj", op or "?", where))]

    def delta(self, d, st) -> list:
        if st == "error" and not isinstance(d, dict):
            return [(1, [("q", self.t("res_failed"))])]
        if not isinstance(d, dict):
            return []
        if d.get("first"):
            return [(1, [("q", self.t("res_first"))])]
        items = [i for i in d.get("items") or [] if isinstance(i, dict)]
        part = [("q", self.t("res_partial"))] if d.get("partial") else []
        if not items:
            return [(1, [("q", self.t("res_none", d.get("read", 0)))] + part)]
        n = int(d.get("n") or len(items))
        head = self.t("res_h", n, min(DELTA_TOP, len(items))) if n > DELTA_TOP else self.t("res_h_all")
        out = [(1, [("t", head)] + part)]
        for i in items[:DELTA_TOP]:
            b, a, u = i.get("b"), i.get("a"), i.get("u")
            sb, sa = _pair(b, a)
            p = [("t", self.label(i.get("path"), "short") + self.colon),
                 ("v", self.clean(sb)), ("t", " → "), ("v", self.clean(sa))] + ([("t", f" {u}")] if u else [])
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b)) and a != b:
                p.append(("q", f"  {'▲' if a > b else '▼'} {_num(float(f'{abs(a - b):.4g}'))}"))
            if i.get("small"):
                p.append(("q", self.t("res_small")))
            out.append((2, p))
        return out

    def loop(self, r) -> tuple:
        tg, rep, runs, d = r.get("target") or {}, r.get("report") or {}, r.get("runs") or {}, r.get("do") or "loop"
        ws = r["writes"] if isinstance(r.get("writes"), dict) else {}
        var = tg.get("path")
        if not var and r.get("op") == "summary" and d != "optimize" and len(ws) == 1:
            var = next(iter(ws))                          # a loop over one field: that field is what it varied
        own = ws.get(var) if var else None
        name = self.label(journal.split_key(var)[0], "full", r.get("loc") if tg.get("path") else None) if var else ""
        if r.get("op") == "restore":
            s = self.t("r_restore", r.get("n") or len(ws))
        elif d == "optimize":
            s = self.t("r_opt", self.clean(rep["algorithm"])) if rep.get("algorithm") else self.t("r_opt_n")
        elif not name:
            s = self.pick("r", f"{d}_n", "loop_n")
        else:
            s = self.t({"sweep": "r_sweep", "seek": "r_seek"}.get(d, "r_loop"), name)
        bits, unit = [], f" {own['after']['unit']}" if own and isinstance(own.get("after"), dict) and own["after"].get("unit") else ""
        if d == "sweep" and isinstance(r.get("range"), list) and len(r["range"]) == 2:
            bits.append(f"{_num(r['range'][0])}–{_num(r['range'][1])}{unit}")
        if d == "optimize" and rep.get("evaluations") is not None:
            bits.append(self.t("r_evals", rep["evaluations"]))
        if d == "optimize" and rep.get("feasible") is not None:
            bits.append(self.t("r_feasible", rep["feasible"]))
        if d != "optimize" and r.get("op") != "restore" and runs.get("n"):
            bits.append(self.t("r_points" if d == "sweep" else "r_runs", runs["n"]))
        if runs.get("n"):
            bits.append(self.t("r_conv", (runs.get("ok") or 0) + (runs.get("warn") or 0)))
        if d == "optimize" and rep.get("finish"):
            bits.append(self.t(f"fin_{rep['finish']}" if rep["finish"] in ("restore", "best", "last") else "fin_last"))
        elif own and isinstance(own.get("after"), dict) and r.get("op") != "restore":
            bits.append(self.t("r_end", self.val(own["after"]) + unit))
        text = [("t", s)] + ([("q", " · " + " · ".join(bits))] if bits else [])
        skip = r.get("op") == "summary" and d != "optimize"
        rest = [(p, w) for p, w in ws.items() if isinstance(w, dict) and not (skip and p == var)]
        subs = []
        for p, w in rest[:WRITES_TOP]:
            path = journal.split_key(p)[0]
            lab = [("t", self.label(path, "full") + self.colon)]
            subs.append((1, lab + (self.change(w.get("before"), w.get("after")) if w.get("status", "changed") == "changed"
                                   and "before" in w else [("t", "= "), ("v", self.val(w.get("after")))])))
        if len(rest) > WRITES_TOP:
            subs.append((1, [("q", self.t("r_wmore", len(rest) - WRITES_TOP))]))
        return text, subs


def _cards(recs, heads) -> list:
    """The records by change group (else call, else alone), oldest group first, oldest record first."""
    by, out = {}, []
    for r in recs:
        key = f"g:{r['group']}" if r.get("group") else f"c:{r['call']}" if r.get("call") else f"r:{r.get('id')}"
        c = by.get(key)
        if c is None:
            c = by[key] = {"head": heads.get(r.get("group")) or {}, "recs": []}
            out.append(c)
        c["recs"].append(r)
    for c in out:
        c["actor"] = c["head"].get("actor") or c["recs"][0].get("actor") or "unknown"
        c["t0"], c["t1"] = _key(c["recs"][0])[0], _key(c["recs"][-1])[0]
    return out


def _types(types, recs) -> dict:
    """{block name: type}: what the window passed, else what add / remove records say."""
    out = {}
    for r in recs:
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        if tg.get("kind") == "block" and tg.get("name") and tg.get("type"):
            out[str(tg["name"])] = tg["type"]
    if isinstance(types, dict):
        out.update({str(k): v for k, v in types.items() if v})
    elif isinstance(types, list):
        out.update({str(b["name"]): b.get("type") for b in types if isinstance(b, dict) and b.get("name") and b.get("type")})
    return out


def _meta(model) -> dict:
    try:
        d = json.loads((Path(journal.ROOT) / "journal" / model / "meta.json").read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def build(model: str, span="all", fmt: str = "md", lang: str = "en", types=None, coverage=None,
          after=None, group=None, now=None) -> dict:
    """A report of ``model``'s journal: {"name": <model>-changes-<yyyymmdd-hhmm>.<md|html>,
    "text", "n": records in it, "more": SCAN_MAX cut it short, "tally": tally(skip_actors=())}.
    ``span``: "all"; "today" (since local midnight); "since" (records after ``after``: a page
    cursor, a record or a time -- the window's "seen here" mark); "group" (``group``: an id or
    a list). ``types``: {block: type} or the flowsheet's block list, for field names;
    ``coverage``: catalog()["coverage"] for the closing section. Raises on a bad model id
    or an unreadable journal."""
    lang, fmt = _lang(lang), "html" if str(fmt).lower() in ("html", "htm") else "md"
    journal._dir(model)                                   # a bad id raises here
    now = time.time() if now is None else float(now)
    span = str(span or "all")
    if span == "today":
        lt = time.localtime(now)
        after = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    elif span not in ("since", "seen"):
        after = None
    if span != "group":
        group = None
    page = journal.page(model, limit=SCAN_MAX, scan=SCAN_MAX, after=after, group=group)
    if page.get("error"):
        raise RuntimeError(page["error"])
    recs = sorted((r for r in page["records"] if r.get("kind") == "change" or (r.get("kind") == "begin" and r.get("open"))),
                  key=_key)
    tmap = _types(types, recs)
    AL.decorate(recs, tmap)
    doc, meta = _Doc(lang, tmap), _meta(model)
    fname = str(meta.get("name") or model)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", fname.rsplit(".", 1)[0] if "." in fname else fname).strip(" .") or model
    tl = tally(recs, skip_actors=())
    heads = page.get("groups") or {}
    if span == "group":
        h = next((heads[g] for g in ([group] if isinstance(group, str) else list(group or [])) if g in heads), {})
        what = doc.t("span_group", doc.clean(h.get("title") or doc.pick("title", h.get("actor"), "unknown")))
    elif span == "today":
        what = doc.t("span_today")
    elif after is not None:
        what = doc.t("span_since", _stamp(journal._cursor(after, after=True)[0]))
    else:
        what = doc.t("span_all")
    days = {time.localtime(_key(r)[0])[:3] for r in recs}
    period = "—"
    if recs:
        t0, t1 = _key(recs[0])[0], _key(recs[-1])[0]
        period = f"{_stamp(t0)} – {_clock(t1) if len(days) == 1 else _stamp(t1)}"
    data = {
        "lang": lang, "title": f"{doc.t('title')} · {doc.clean(stem)}", "model": model,
        "meta": [(doc.t("model"), doc.clean(fname)), (doc.t("span"), what),
                 (doc.t("period"), period),
                 (doc.t("count"), str(len(recs))), (doc.t("made"), _stamp(now))],
        "capped": doc.t("capped", SCAN_MAX) if page.get("more") else None,
        "tally": tl, "cards": [], "cov": [],
    }
    actors = [a for a in ACTOR_ORDER if a in tl["by"]] + [a for a in tl["by"] if a not in ACTOR_ORDER]
    data["who"] = [(a, doc.who(a), doc.sentence(tl["by"][a])) for a in actors]
    data["ext"] = doc.t("ext_note", tl["external"]) if tl["external"] else None
    cols = [tl] + [tl["by"][a] for a in actors]
    data["table"] = {"head": [doc.t("tb_item"), doc.t("tb_all")] + [doc.who(a) for a in actors],
                     "rows": [(doc.t(f"tb_{k}"), [count(c, k) for c in cols]) for k in TABLE_ROWS if count(tl, k)]}
    over = overrides(recs)
    for i, c in enumerate(_cards(recs, heads), 1):
        h, a = c["head"], c["actor"]
        title = doc.clean(h.get("title")) if h.get("title") else doc.pick("title", a, "unknown")
        when = _clock(c["t0"], len(days) > 1)
        if _clock(c["t1"], len(days) > 1) != when:
            when += f"–{_clock(c['t1'], len(days) > 1)}"
        flags = [doc.t("src_note")] if h.get("source") == "note" else [doc.t("src_reason")] if h.get("source") == "reason" else []
        if a == "program" and h.get("ai_group"):
            flags.append(doc.t("by_ai_prog"))
        rows = []
        for r in c["recs"]:
            row = doc.row(r)
            if row["note"] and row["note"][0] == "reason" and h.get("source") == "reason" and \
                    str(r.get("reason") or "").strip().startswith(str(h.get("title") or "").rstrip("…")):
                row["note"] = None                        # the title already says it (as the Changes tab does)
            row["time"] = _clock(r.get("t"), len(days) > 1)
            row["badge"] = doc.who(r.get("actor")) if r.get("actor") and r.get("actor") != a else None
            x = over.get(r.get("id"))
            if x:                                         # set again later by someone else (WBC.overrides)
                val = lambda d: d.get("value") if isinstance(d, dict) else d  # noqa: E731
                back = journal._same(val(r.get("before")), val(x.get("after")))
                row["subs"].append((1, [("q", doc.t("r_over_back" if back else "r_over", _clock(x.get("t"), len(days) > 1),
                                                    doc.who(x.get("actor")), doc.val(x.get("after"))
                                                    + (f" {x['after']['unit']}" if isinstance(x.get("after"), dict) and x["after"].get("unit") else "")))]))
            rows.append(row)
        data["cards"].append({"n": i, "actor": a, "who": doc.who(a), "title": title, "when": when, "flags": flags,
                              "count": doc.t("n_recs", len(c["recs"])),
                              "sum": doc.sentence(tally(c["recs"], skip_actors=())), "rows": rows})
    data["none"] = doc.t("none") if not recs else None
    cov = coverage if isinstance(coverage, dict) else {}
    ext_on = bool((cov.get("flags") or {}).get("external"))
    data["cov"] = [doc.t("cov_rec"), doc.t("cov_run"), doc.t("cov_ext_on" if ext_on else "cov_ext_off"), doc.t("cov_names")]
    unrec = [str(x) for x in cov.get("unrec") or [] if x]
    if unrec:
        data["cov"].append(doc.t("cov_unrec", doc.t("list_sep").join(unrec)))
    data["refs"] = [(lab, path) for path, lab in doc.refs.items()]
    data["words"] = {k: doc.t(k) for k in ("read_me", "sum_h", "tl_h", "cov_h", "app_h", "app_p", "app_loc", "app_path",
                                           "ext_tag")}
    data["foot"] = doc.t("foot", model)
    text = _html(data) if fmt == "html" else _md(data)
    return {"name": f"{stem}-changes-{time.strftime('%Y%m%d-%H%M', time.localtime(now))}.{fmt}", "text": text,
            "n": len(recs), "more": bool(page.get("more")), "tally": tl}


# ------------------------------------------------------------------------------ Markdown
def _m(s) -> str:
    """Text for Markdown: no raw HTML (a value holding <script> stays text)."""
    return str(s).replace("<", "&lt;")


def _mp(pieces) -> str:
    out = []
    for kind, s in pieces:
        out.append(f"**{_m(s)}**" if kind == "v" and str(s).strip() else _m(s))
    return "".join(out)


def _md(d) -> str:
    w, L = d["words"], []
    L += [f"# {_m(d['title'])}", ""] + [f"- {_m(k)}：{_m(v)}" if d["lang"] == "zh" else f"- {_m(k)}: {_m(v)}"
                                         for k, v in d["meta"]] + [""]
    if d["capped"]:
        L += [f"> {_m(d['capped'])}", ""]
    L += [_m(w["read_me"]), "", f"## {_m(w['sum_h'])}", ""]
    L += [f"- **{_m(name)}**{'：' if d['lang'] == 'zh' else ': '}{_m(s)}" for _, name, s in d["who"]] or [_m(d["none"] or "")]
    L.append("")
    if d["ext"]:
        L += [_m(d["ext"]), ""]
    tb = d["table"]
    L += ["| " + " | ".join(_m(x) for x in tb["head"]) + " |", "|---" + "|---:" * (len(tb["head"]) - 1) + "|"]
    L += ["| " + " | ".join([_m(k)] + [str(x) for x in v]) + " |" for k, v in tb["rows"]] + [""]
    L += [f"## {_m(w['tl_h'])}", ""]
    if d["none"]:
        L += [_m(d["none"]), ""]
    for c in d["cards"]:
        L += [f"### {c['n']}. {_m(c['title'])}", "", " · ".join(_m(x) for x in [c["who"], c["when"], c["count"]] + c["flags"]),
              "", _m(c["sum"]), ""]
        for r in c["rows"]:
            badge = f"【{_m(r['badge'])}】" if r["badge"] else ""
            ext = f"【{_m(w['ext_tag'])}】" if r["ext"] and not r["badge"] else ""
            L.append(f"- {r['time']} · {badge}{ext}{_mp(r['text'])}")
            L += [f"{'  ' * lvl}- {_mp(p)}" for lvl, p in r["subs"]]
            if r["note"]:
                L.append(f"  - {_m(r['note'][1])}")
        L.append("")
    L += [f"## {_m(w['cov_h'])}", ""] + [x for p in d["cov"] for x in (_m(p), "")]
    if d["refs"]:
        L += [f"## {_m(w['app_h'])}", "", _m(w["app_p"]), "", f"| {_m(w['app_loc'])} | {_m(w['app_path'])} |", "|---|---|"]
        L += [f"| {_m(lab)} | `{path}` |" for lab, path in d["refs"]] + [""]
    L += ["---", "", _m(d["foot"]), ""]
    return "\n".join(L)


# ------------------------------------------------------------------------------ HTML
_CSS = """
:root{--ink:#1b2533;--ink2:#3b4757;--mute:#5b6778;--line:#e1e6ee;--bg:#f5f7fb;--card:#fff;--soft:#eef1f6;
--ai:#7c5cff;--user:#3b82f6;--program:#2f855a;--optimizer:#86198f;--external:#64748b;--unknown:#64748b;
--warn:#c98500;--bad:#d03b3b;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--ink:#e6eaf0;--ink2:#c3cad5;--mute:#98a2b3;--line:#2e3744;--bg:#12171e;
--card:#1b222c;--soft:#232b36;--ai:#a18bff;--user:#6ea8ff;--program:#5fbf8a;--optimizer:#d884e2;--external:#9aa7b8;
--unknown:#9aa7b8;--warn:#e0a53a;--bad:#f07575;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 "Segoe UI Variable Text","Segoe UI","Microsoft JhengHei UI","PingFang TC","Noto Sans TC",sans-serif}
main{max-width:880px;margin:0 auto;padding:32px 16px 48px}
h1{font-size:26px;line-height:1.3;margin:0 0 14px}
h2{font-size:19px;margin:36px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:0 0 2px;line-height:1.4}
p{margin:8px 0}
dl.meta{display:grid;grid-template-columns:max-content 1fr;gap:2px 16px;margin:0;color:var(--ink2)}
dl.meta dt{color:var(--mute)} dl.meta dd{margin:0;overflow-wrap:anywhere}
.box{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:6px;padding:8px 12px}
.hint{color:var(--mute);font-size:14px}
.wrap{overflow-x:auto;margin:12px 0}
table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);font-size:14px}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums;vertical-align:top}
th{background:var(--soft);font-weight:600}
th:first-child,td:first-child{text-align:left}
ul.who{margin:8px 0;padding-left:20px}
.pill{display:inline-block;font-size:12px;font-weight:600;line-height:18px;padding:0 8px;border-radius:999px;border:1px solid var(--c);color:var(--c);white-space:nowrap;vertical-align:1px}
.a-ai{--c:var(--ai)}.a-user{--c:var(--user)}.a-program{--c:var(--program)}.a-optimizer{--c:var(--optimizer)}.a-external{--c:var(--external)}.a-unknown{--c:var(--unknown)}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:8px;padding:14px 16px;margin:14px 0;break-inside:avoid-page}
.cm{color:var(--mute);font-size:13px;margin:0 0 4px;display:flex;gap:6px 10px;flex-wrap:wrap;align-items:center}
.cs{margin:0 0 8px;color:var(--ink2)}
ol.rows{list-style:none;margin:0;padding:0}
ol.rows>li{display:grid;grid-template-columns:minmax(3.2em,max-content) 1fr;gap:12px;padding:7px 0;border-top:1px dashed var(--line)}
time{color:var(--mute);font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap;padding-top:1px}
.tx{overflow-wrap:anywhere}
.sub{font-size:14px;color:var(--ink2);margin-top:2px}
.sub.l2{padding-left:1.3em}
.q{color:var(--mute)} .bad{color:var(--bad);font-weight:600}
.note{margin-top:5px;font-size:14px;padding:3px 10px;border-left:3px solid var(--ai);color:var(--ink2)}
.note.why{border-left-color:var(--program)}
code{font-family:"Cascadia Mono",Consolas,monospace;font-size:13px;overflow-wrap:anywhere}
footer{margin-top:40px;color:var(--mute);font-size:13px;border-top:1px solid var(--line);padding-top:10px}
@media (max-width:560px){ol.rows>li{grid-template-columns:1fr;gap:0}h1{font-size:22px}}
@media print{:root{--bg:#fff;--card:#fff}body{font-size:12.5px}main{max-width:none;padding:0}.card{border-color:#ccc}}
"""


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _hp(pieces) -> str:
    out = []
    for kind, s in pieces:
        s = _e(s)
        out.append(f"<b>{s}</b>" if kind == "v" else f'<span class="q">{s}</span>' if kind == "q"
                   else f'<span class="bad">{s}</span>' if kind == "bad" else s)
    return "".join(out)


def _pill(actor, word) -> str:
    return f'<span class="pill a-{_e(actor if actor in ACTOR_ORDER else "unknown")}">{_e(word)}</span>'


def _html(d) -> str:
    w, H = d["words"], []
    H.append(f'<!doctype html><html lang="{"zh-Hant" if d["lang"] == "zh" else "en"}"><head><meta charset="utf-8">'
             f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{_e(d["title"])}</title>'
             f'<style>{_CSS}</style></head><body><main>')
    H.append(f"<header><h1>{_e(d['title'])}</h1><dl class=\"meta\">"
             + "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in d["meta"]) + "</dl></header>")
    if d["capped"]:
        H.append(f'<p class="box">{_e(d["capped"])}</p>')
    H.append(f'<p class="hint">{_e(w["read_me"])}</p><section><h2>{_e(w["sum_h"])}</h2>')
    if d["who"]:
        H.append('<ul class="who">' + "".join(f"<li>{_pill(a, name)} {_e(s)}</li>" for a, name, s in d["who"]) + "</ul>")
    else:
        H.append(f"<p>{_e(d['none'] or '')}</p>")
    if d["ext"]:
        H.append(f'<p class="hint">{_e(d["ext"])}</p>')
    tb = d["table"]
    H.append('<div class="wrap"><table><thead><tr>' + "".join(f"<th>{_e(x)}</th>" for x in tb["head"]) + "</tr></thead><tbody>"
             + "".join("<tr>" + f"<td>{_e(k)}</td>" + "".join(f"<td>{x}</td>" for x in v) + "</tr>" for k, v in tb["rows"])
             + "</tbody></table></div></section>")
    H.append(f"<section><h2>{_e(w['tl_h'])}</h2>")
    if d["none"]:
        H.append(f"<p>{_e(d['none'])}</p>")
    for c in d["cards"]:
        a = c["actor"] if c["actor"] in ACTOR_ORDER else "unknown"
        H.append(f'<article class="card a-{a}"><h3>{c["n"]}. {_e(c["title"])}</h3>'
                 f'<div class="cm">{_pill(a, c["who"])}<span>{_e(c["when"])}</span><span>{_e(c["count"])}</span>'
                 + "".join(f"<span>{_e(f)}</span>" for f in c["flags"]) + f'</div><p class="cs">{_e(c["sum"])}</p><ol class="rows">')
        for r in c["rows"]:
            badge = _pill(r["who"], r["badge"]) + " " if r["badge"] else ""
            ext = _pill("external", w["ext_tag"]) + " " if r["ext"] and not r["badge"] else ""
            subs = "".join(f'<div class="sub l{lvl}">{_hp(p)}</div>' for lvl, p in r["subs"])
            note = f'<div class="note {r["note"][0]}">{_e(r["note"][1])}</div>' if r["note"] else ""
            H.append(f'<li><time>{_e(r["time"])}</time><div class="tx">{badge}{ext}{_hp(r["text"])}{subs}{note}</div></li>')
        H.append("</ol></article>")
    H.append(f"</section><section><h2>{_e(w['cov_h'])}</h2>" + "".join(f"<p>{_e(p)}</p>" for p in d["cov"]) + "</section>")
    if d["refs"]:
        H.append(f'<section><h2>{_e(w["app_h"])}</h2><p class="hint">{_e(w["app_p"])}</p><div class="wrap"><table>'
                 f'<thead><tr><th>{_e(w["app_loc"])}</th><th style="text-align:left">{_e(w["app_path"])}</th></tr></thead><tbody>'
                 + "".join(f'<tr><td>{_e(lab)}</td><td style="text-align:left">'
                           + f"<code>{_e(path)}</code></td></tr>" for lab, path in d["refs"])
                 + "</tbody></table></div></section>")
    H.append(f"<footer>{_e(d['foot'])}</footer></main></body></html>\n")
    return "".join(H)
