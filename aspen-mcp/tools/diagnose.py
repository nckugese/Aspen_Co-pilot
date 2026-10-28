"""Why a run failed, in plain words: the failure card's content.

    mechanisms(text)                 the failure kinds Aspen's words name, most specific first
    explain(mech, lang)              {"mech", "title", "text", "checks"}: EXPLAIN, our own words
    lore(blocks, pm, run_msgs)       the matching entries of the two error-history.md files (keyword or kind)
    upstream(flowsheet, names)       {(kind, NAME)} upstream of some blocks
    order(flowsheet, names)          [(name, failing blocks upstream of it)], upstream first
    card(req)                        the whole card, from the page's state + the journal
    session_card(sess, rec, lang)    card() of a workbench session (state.json's) about one run record
    say(card, name, short)           a card in one English line, for the AI; remember / recall keep cards

``_MECHANISM_PATTERNS`` (Aspen keyword -> mechanism, most specific first) is also what the
optimizers' ``main_tools.classify_mechanisms`` tags failed evaluations with; ``_CARD_PATTERNS``
adds kinds only the card names (seen in real V15 run statuses: a reaction whose stoichiometry is
off, fractions normalized, a feed without a flow, a recycle loop not converged, a column's product
specs above its feed) and the common Heater / Flash warnings (an outlet below its dew point or
above its bubble point, a phase other than the one the Valid phases allow, near the critical
point, no feed flow) -- the optimizers' tags stay as they were. A warning card carries ``state``
(STATE_WARN: the run converged). A check names a field as the GUI does, zh gloss first then
Aspen's label and its code (the Chinese word, then "Distillate rate" and BASIS_D). EXPLAIN and GENERAL are ours (zh / en); Aspen's own
text -- BLKMSG, PER_ERROR, the Run-Status lines -- only ever comes from the run itself, never
from this file.

error-history.md: ``~/.aspen-mcp/error-history.md`` (this machine's, first) and
``<docs>/error-history.md`` (shipped): H2 an error keyword, H3 an entry, ``- **Key**: value``
lines under it; an entry without a cause or a fix is skipped. Parsed on first use and again
when a file's mtime changes. The community sheet is never fetched here: it is untrusted
content off the network, left to the AI's troubleshooting workflow with the user's consent.

Stdlib only (and tools.journal, stdlib too): no COM, no I/O at import; nothing here raises --
an unreadable file or a malformed request leaves that part out.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path

from tools import journal, probes

logger = logging.getLogger(__name__)

# Keywords that identify a meaningful Aspen error line worth recording
# (main_tools.extract_error_keywords). "FLASH" and "MASS IMBALANCE" (reactor) are there so
# flash-convergence and reactor mass-imbalance failures are captured.
_ERROR_KEYWORDS = (
    "NOT IN MASS BALANCE", "MASS IMBALANCE", "DRIED UP", "DRIES UP", "DRY",
    "NOT CONVERGED", "FLOODING", "TEMPERATURE CROSS", "INSIDE LOOP", "OUTSIDE LOOP",
    "SINGULAR", "INFEASIBLE", "INCONSISTENT", "INPUT ERROR",
    "SEVERE ERROR", "OUT OF RANGE", "MISSING", "FLASH",
)

# Ordered keyword -> mechanism map for main_tools.classify_mechanisms(). MOST SPECIFIC
# first: a flash failure often also prints a generic "SEVERE ERROR" / trailing
# mass-balance line, so specific root-cause patterns must win over generic ones.
_MECHANISM_PATTERNS = (
    ("DRIE", "dry_up"),     # matches both DRIES UP and DRIED UP
    ("DRY", "dry_up"),
    ("FLASH", "flash"),
    ("MASS IMBALANCE", "mass_imbalance"),          # reactor (distinct string from below)
    ("NOT IN MASS BALANCE", "not_in_mass_balance"),  # column
    ("FLOODING", "flooding"),
    ("TEMPERATURE CROSS", "temperature_cross"),
    ("INSIDE LOOP", "loop"),
    ("OUTSIDE LOOP", "loop"),
    ("SINGULAR", "singular"),
    ("OUT OF RANGE", "out_of_range"),
    ("INFEASIBLE", "infeasible"),
    ("NOT CONVERGED", "not_converged"),
    ("INCONSISTENT", "input"),
    ("INPUT ERROR", "input"),
    ("MISSING", "input"),
    ("SEVERE ERROR", "severe"),                     # generic, last resort
)

# The card's own, after those (the optimizers never see them).
_CARD_PATTERNS = (
    ("DOES NOT SATISFY MASS BALANCE", "stoich"),                    # RStoic: a reaction's masses
    ("SPECIFICATIONS EXCEEDS FEED FLOW", "not_in_mass_balance"),    # RadFrac: product flow specs above the feed
    ("CONVERGENCE BLOCKS WERE COMPLETED WITH ERRORS", "tear"),      # a recycle loop's solver
    ("FLOWRATE FOR THE STREAM HAS NOT BEEN", "feed_flow"),          # ... specified / initialized
    ("NORMALIZED TO", "normalized"),
    # Heater / Flash warnings (the run converges): the outlet's phase is not the one expected
    ("BELOW THE DEW POINT", "below_dew"),
    ("BELOW DEW POINT", "below_dew"),
    ("BELOW ITS DEW POINT", "below_dew"),
    ("ABOVE THE BUBBLE POINT", "above_bubble"),
    ("ABOVE BUBBLE POINT", "above_bubble"),
    ("ABOVE ITS BUBBLE POINT", "above_bubble"),
    ("VAPOR-ONLY", "phase_spec"),
    ("LIQUID-ONLY", "phase_spec"),
    ("VAPOR ONLY", "phase_spec"),
    ("LIQUID ONLY", "phase_spec"),
    ("SINGLE PHASE", "phase_spec"),
    ("TWO-PHASE", "phase_spec"),
    ("TWO PHASE", "phase_spec"),
    ("NEAR THE CRITICAL", "near_critical"),
    ("NEAR CRITICAL", "near_critical"),
    ("ZERO FEED", "zero_feed"),
    ("FEED FLOW IS ZERO", "zero_feed"),
)
# A warning card's state line (card()'s ``state``): Aspen finished the run and its results stand.
STATE_WARN = {"zh": "此次執行已收斂", "en": "This run converged"}
_GENERIC = frozenset({"input", "severe"})       # named only when nothing more specific is

# mech -> lang -> title, text, checks. Our own words; Aspen's codes in the checks
# are the field names a user finds in the inspector.
EXPLAIN = {
    "not_in_mass_balance": {
        "zh": {"title": "塔質量不平衡",
               "text": "指定的產品量與實際進塔量不相容，例如餾出量或塔底量大於進料。",
               "checks": ["餾出量 Distillate rate（BASIS_D）或塔底量 Bottoms rate（BASIS_B）是否大於進料流量",
                          "上游有反應或分離時，實際進塔量可能少於新鮮進料",
                          "兩個操作規格是否互相矛盾"]},
        "en": {"title": "The column's material balance cannot close",
               "text": "The product amounts specified do not fit what actually enters the column, "
                       "e.g. more distillate or bottoms than feed.",
               "checks": ["Is the Distillate rate (BASIS_D) or Bottoms rate (BASIS_B) above the feed flow?",
                          "With a reaction or a split upstream, the column may get less than the fresh feed",
                          "Do the two operating specs contradict each other?"]}},
    "mass_imbalance": {
        "zh": {"title": "反應器質量不平衡",
               "text": "化學計量或轉化率使某成分的計算量為負，進出物料無法平衡。",
               "checks": ["反應式的係數（反應物、產物各在正確的一側）",
                          "轉化率 Fractional conversion（CONV）是否 ≤ 1，且以限量反應物為基準",
                          "成分的分子量是否正確"]},
        "en": {"title": "The reactor's material balance is off",
               "text": "The stoichiometry or a conversion drives some component negative, so what goes in "
                       "and out no longer matches.",
               "checks": ["The reaction coefficients (reactants and products on the right sides)",
                          "Is each Fractional conversion (CONV) at most 1, based on the limiting reactant?",
                          "Are the components' molecular weights right?"]}},
    "dry_up": {
        "zh": {"title": "塔板乾涸（Dry-up）",
               "text": "部分塔板上沒有液相（或氣相），無法維持氣液接觸。",
               "checks": ["餾出/進料比 Distillate to feed ratio（D:F）是否大於輕成分在進料中的比例",
                          "迴流比 Reflux ratio（BASIS_RR）或再沸比 Boilup ratio（BASIS_BR）是否太小",
                          "進料狀態（溫度、汽化率）與進料板 Feed stage（FEED_STAGE）"]},
        "en": {"title": "The column dries up",
               "text": "Some stages end up with no liquid (or no vapor), so the column cannot keep the "
                       "two phases in contact.",
               "checks": ["Is the Distillate to feed ratio (D:F) above the light components' share of the feed?",
                          "Is the Reflux ratio (BASIS_RR) or Boilup ratio (BASIS_BR) too small?",
                          "The feed's condition (temperature, vapor fraction) and its Feed stage (FEED_STAGE)"]}},
    "flash": {
        "zh": {"title": "閃蒸計算失敗",
               "text": "給定的溫度、壓力或熱負荷，在這個混合物上找不到相平衡的解。",
               "checks": ["溫度 Temperature（TEMP）、壓力 Pressure（PRES）規格是否合理（含單位）",
                          "是否接近臨界點，或有效相態 Valid phases（NPHASE）限定了不可能的相態（例如僅液相）",
                          "物性方法是否適合此系統"]},
        "en": {"title": "A flash calculation found no answer",
               "text": "For this mixture there is no phase equilibrium at the temperature, pressure or duty "
                       "given.",
               "checks": ["Are the Temperature (TEMP) and Pressure (PRES) specs sensible (units too)?",
                          "Is it near the critical point, or do the Valid phases (NPHASE) force an impossible "
                          "phase (liquid only)?",
                          "Does the property method suit the system?"]}},
    "flooding": {
        "zh": {"title": "液泛", "text": "氣體或液體的流量超過這個塔徑（或板間距）能處理的量。",
               "checks": ["塔徑與板間距", "氣液負荷（回流比、再沸比）", "塔板或填料的型式"]},
        "en": {"title": "Flooding", "text": "The vapor or liquid traffic is more than this diameter (or tray "
                                             "spacing) can carry.",
               "checks": ["Column diameter and tray spacing", "The loads (reflux and boilup ratios)",
                          "The tray or packing type"]}},
    "temperature_cross": {
        "zh": {"title": "換熱器溫度交錯", "text": "要求的出口溫度在熱力學上做不到：冷流被加熱得比熱流還熱。",
               "checks": ["出口溫度或熱負荷的規格", "最小溫差", "流向（逆流或並流）"]},
        "en": {"title": "Temperature cross in a heat exchanger",
               "text": "The outlet temperature asked for is thermodynamically impossible: the cold side would "
                       "end up hotter than the hot side.",
               "checks": ["The outlet temperature or duty spec", "The minimum approach temperature",
                          "The flow direction (counter- or co-current)"]}},
    "loop": {
        "zh": {"title": "塔內／外迴圈未收斂", "text": "塔的迭代計算未收斂。",
               "checks": ["初始估計（溫度、流量分布）", "演算法 Algorithm 改用 Newton，並設定阻尼 Damping factor（DAMPING）",
                          "規格是否太極端（迴流比 Reflux ratio、產品量）", "最大迭代次數 Maximum iterations（MAXOL）"]},
        "en": {"title": "The column's inside / outside loop did not converge",
               "text": "The column's iterations did not settle.",
               "checks": ["Initial estimates (temperature and flow profiles)",
                          "Newton as the Algorithm, with a Damping factor (DAMPING)",
                          "Extreme specs (Reflux ratio, product rates)", "Maximum iterations (MAXOL)"]}},
    "singular": {
        "zh": {"title": "方程式互相矛盾或重複", "text": "通常是同時指定了兩個會互相決定的量，數學上沒有唯一解。",
               "checks": ["規格組合：是否有兩個規格實為同一條件", "被點名單元的自由度"]},
        "en": {"title": "The equations contradict or repeat each other",
               "text": "Usually two quantities that determine each other were both specified, so there is "
                       "no unique solution.",
               "checks": ["The spec combination: do two specs say the same thing?",
                          "The degrees of freedom of the block named"]}},
    "out_of_range": {
        "zh": {"title": "數值超出範圍", "text": "例如分率大於 1，或溫度、壓力超出物性資料的範圍。",
               "checks": ["被點名的數值及其單位", "物性資料適用的溫度、壓力範圍"]},
        "en": {"title": "A value is out of its allowed range",
               "text": "For example a fraction above 1, or a temperature or pressure outside the property "
                       "data's range.",
               "checks": ["The value named, and its unit", "The range the property data covers"]}},
    "infeasible": {
        "zh": {"title": "規格無法達成", "text": "在目前的設定下，要求的產品規格無法達成。",
               "checks": ["放寬產品規格",
                          "調整設計變數：理論板數 Stages（NSTAGE）、迴流比 Reflux ratio（BASIS_RR）、進料板 Feed stage（FEED_STAGE）"]},
        "en": {"title": "The specs cannot be met", "text": "With the current setup the product specs asked "
                                                           "for are out of reach.",
               "checks": ["Relax the product specs",
                          "Change a design variable: Stages (NSTAGE), Reflux ratio (BASIS_RR), Feed stage (FEED_STAGE)"]}},
    "not_converged": {
        "zh": {"title": "未收斂", "text": "迭代次數已用盡，結果仍未穩定。",
               "checks": ["先修正最上游的錯誤", "改善初始估計", "為循環回路的撕裂物流設定合理的初值"]},
        "en": {"title": "Not converged", "text": "The iterations ran out before the results settled.",
               "checks": ["Fix the most upstream error first", "Better initial estimates",
                          "Sensible initial values on the recycle loop's tear streams"]}},
    "input": {
        "zh": {"title": "輸入互相矛盾或有缺漏", "text": "Aspen 判定輸入前後不一致或有缺漏。",
               "checks": ["開啟「缺少的輸入」查看缺少的欄位", "被點名的規格是否互相衝突"]},
        "en": {"title": "Inputs contradict each other or are missing",
               "text": "Aspen finds the inputs inconsistent, or something is not given.",
               "checks": ["Open \"Missing inputs\" to see the fields not filled",
                          "Do the specs named conflict with each other?"]}},
    "severe": {
        "zh": {"title": "嚴重錯誤（未說明原因）", "text": "Aspen 只回報了一般性的嚴重錯誤。",
               "checks": ["閱讀完整原文，找出第一個出錯的單元", "先修正最上游的錯誤"]},
        "en": {"title": "A severe error, without a reason", "text": "Aspen reported only a generic severe error.",
               "checks": ["Read the full text and find the first block that failed",
                          "Fix the most upstream error first"]}},
    "stoich": {
        "zh": {"title": "反應式質量不守恆",
               "text": "某反應的係數乘以分子量後，反應物與產物質量不相等。常見於自訂成分或手動輸入分子量。",
               "checks": ["該反應的化學計量係數", "成分的分子量是否與化學式一致"]},
        "en": {"title": "A reaction does not conserve mass",
               "text": "With the coefficients times the molecular weights, the reactants' and products' masses "
                       "differ. Common with user-defined components or molecular weights entered by hand.",
               "checks": ["That reaction's stoichiometric coefficients",
                          "Do the molecular weights agree with the formulas?"]}},
    "tear": {
        "zh": {"title": "循環回路未收斂",
               "text": "回收流（撕裂物流）的迭代未在允許次數內收斂。",
               "checks": ["撕裂物流的初始估計", "收斂方法改用 Broyden，並提高最大迭代次數",
                          "先確認回路中每個單元都能單獨求解"]},
        "en": {"title": "A recycle loop did not converge",
               "text": "The iterations on the recycle (tear) streams did not settle within the allowed number.",
               "checks": ["Initial estimates on the tear streams",
                          "Broyden as the convergence method, with more iterations",
                          "Check each block in the loop solves on its own first"]}},
    "feed_flow": {
        "zh": {"title": "進料未指定流量",
               "text": "某進料物流未指定流量（或初值），計算時可能視為零。",
               "checks": ["該物流的總流量或各成分流量", "是否應由上游計算（回收流需設定初值）"]},
        "en": {"title": "A feed has no flow",
               "text": "A feed stream has no flow (or no initial value), so the calculation may treat it as zero.",
               "checks": ["That stream's total or component flows",
                          "Should it come from upstream instead? (a recycle needs initial values)"]}},
    "normalized": {
        "zh": {"title": "組成已自動正規化",
               "text": "輸入的組成分率加起來不是 1，Aspen 已經按比例調整。通常不是錯誤，但需確認是否符合預期。",
               "checks": ["進料的組成分率加總是否為 1", "流量與分率的基準是否混用"]},
        "en": {"title": "A composition was normalized",
               "text": "The fractions entered did not add up to 1, so Aspen scaled them. Usually not an error, "
                       "but check that it was intended.",
               "checks": ["Do the feed's fractions add up to 1?", "Were flow and fraction bases mixed up?"]}},
    "below_dew": {
        "zh": {"title": "出口低於露點",
               "text": "出口溫度低於露點，部分氣相冷凝，出口為氣液兩相（或全為液相）。需確認此相態是否符合預期。",
               "checks": ["出口溫度 Temperature（TEMP）與壓力 Pressure（PRES）的規格",
                          "有效相態 Valid phases（NPHASE）是否限定為僅氣相",
                          "下游單元能否處理含液相的進料"]},
        "en": {"title": "Outlet below its dew point",
               "text": "The outlet temperature is below the dew point: part of the vapor condenses, so the outlet "
                       "is two-phase (or liquid). Check that this phase is intended.",
               "checks": ["The outlet Temperature (TEMP) and Pressure (PRES) specs",
                          "Are the Valid phases (NPHASE) restricted to vapor only?",
                          "Can the blocks downstream take a feed with liquid in it?"]}},
    "above_bubble": {
        "zh": {"title": "出口高於泡點",
               "text": "出口溫度高於泡點，部分液相汽化，出口為氣液兩相（或全為氣相）。需確認此相態是否符合預期。",
               "checks": ["出口溫度 Temperature（TEMP）與壓力 Pressure（PRES）的規格",
                          "有效相態 Valid phases（NPHASE）是否限定為僅液相",
                          "泵、閥等下游單元能否處理含氣相的進料"]},
        "en": {"title": "Outlet above its bubble point",
               "text": "The outlet temperature is above the bubble point: part of the liquid vaporizes, so the "
                       "outlet is two-phase (or vapor). Check that this phase is intended.",
               "checks": ["The outlet Temperature (TEMP) and Pressure (PRES) specs",
                          "Are the Valid phases (NPHASE) restricted to liquid only?",
                          "Can the pumps or valves downstream take a feed with vapor in it?"]}},
    "phase_spec": {
        "zh": {"title": "相態與指定不符",
               "text": "有效相態限定為單一相（僅氣相或僅液相），但在此條件下實際為兩相或接近臨界點；"
                       "以指定相態計算的結果可能失真，甚至無法求解。",
               "checks": ["有效相態 Valid phases（NPHASE）與相態 Phase（PHASE）的設定",
                          "溫度 Temperature（TEMP）、壓力 Pressure（PRES）是否使物流落在兩相區",
                          "改為氣液兩相（Vapor-Liquid）計算是否更合適"]},
        "en": {"title": "The phase found is not the one specified",
               "text": "The Valid phases allow one phase only (vapor only or liquid only), but at these conditions "
                       "the mixture is two-phase or near its critical point; results computed in the phase "
                       "specified may be off, or not found at all.",
               "checks": ["The Valid phases (NPHASE) and Phase (PHASE) settings",
                          "Do the Temperature (TEMP) and Pressure (PRES) put the stream in the two-phase region?",
                          "Would a Vapor-Liquid calculation suit it better?"]}},
    "near_critical": {
        "zh": {"title": "接近臨界點",
               "text": "操作條件接近混合物的臨界點，氣液兩相的性質趨於一致，相平衡計算容易不穩定。",
               "checks": ["溫度 Temperature（TEMP）與壓力 Pressure（PRES）是否接近臨界值",
                          "物性方法是否適合高壓系統（例如狀態方程式）",
                          "有效相態 Valid phases（NPHASE）的設定"]},
        "en": {"title": "Near the critical point",
               "text": "The conditions are close to the mixture's critical point, where vapor and liquid become "
                       "alike and phase equilibrium is hard to settle.",
               "checks": ["Are the Temperature (TEMP) and Pressure (PRES) close to critical?",
                          "Does the property method suit high pressures (an equation of state)?",
                          "The Valid phases (NPHASE) setting"]}},
    "zero_feed": {
        "zh": {"title": "進料流量為零",
               "text": "單元的進料流量為零，計算已略過，出口物流沒有流量。常見於上游分流比例為 0，或上游單元未正常求解。",
               "checks": ["進料物流的流量", "上游分流器 Split fraction（FRAC）的設定", "上游單元是否正常求解"]},
        "en": {"title": "A block has no feed flow",
               "text": "The block's feed flow is zero, so it was skipped and its outlets carry nothing. Common when "
                       "an upstream split sends it 0, or an upstream block did not solve.",
               "checks": ["The feed streams' flows", "The upstream splitter's Split fraction (FRAC)",
                          "Did the blocks upstream solve?"]}},
    "unknown": {
        "zh": {"title": "未識別的訊息類型",
               "text": "訊息中沒有已知的類型；請參考 Aspen 原文，依一般檢查順序處理。", "checks": []},
        "en": {"title": "Unrecognized message type",
               "text": "The messages match no known kind; read Aspen's own words and go through the "
                       "general checks.", "checks": []}},
}

# The general order of checks (the aspen-error-troubleshooting skill's heuristics, in our words).
GENERAL = {
    "zh": ["先修正最上游的錯誤：下游錯誤常源自上游", "檢查進料的溫度、壓力與組成", "確認物性方法適合這個系統",
           "塔：改用 Newton 演算法並加強阻尼", "循環回路：給撕裂物流初始估計，收斂方法改用 Broyden"],
    "en": ["Fix the most upstream error first: downstream errors often come from it",
           "Check the feeds' temperature, pressure and composition",
           "Make sure the property method suits the system",
           "Columns: the Newton algorithm with stronger damping",
           "Recycle loops: initial estimates on the tear streams, Broyden as the convergence method"],
}

MECH_MAX = 3            # mechanisms a text names at most
BLOCKS_MAX = 12         # failing blocks a card lists
LINES_MAX, WIDTH = 20, 200   # PER_ERROR lines a card block keeps, characters of each
LORE_MAX = 3            # error-history entries a card lists
FIELD_MAX = 600         # characters of an error-history field
USER_HISTORY = None     # ~/.aspen-mcp/error-history.md at call time; kept as a module attribute so it can be overridden
DOCS_HISTORY = Path(__file__).resolve().parent.parent / "docs" / "error-history.md"


def _lang(lang) -> str:
    s = str(lang or "").lower()
    return "zh" if s == "zh" or s.startswith("zh-") or s.startswith("zh_") else "en"


def _words(text) -> str:
    return " ".join(str(text or "").upper().split())


def mechanisms(text, limit: int = MECH_MAX) -> list:
    """The failure kinds Aspen's words name (``_MECHANISM_PATTERNS``, then ``_CARD_PATTERNS``),
    in that order, each once; the generic ones (input, severe) only when nothing more specific
    is named. [] when none."""
    u, found = _words(text), []
    for pat, mech in _MECHANISM_PATTERNS + _CARD_PATTERNS:
        if pat in u and mech not in found:
            found.append(mech)
    specific = [m for m in found if m not in _GENERIC]
    return (specific or found)[:limit]


def explain(mech, lang="en") -> dict:
    """{"mech", "title", "text", "checks"} of a mechanism in ``lang`` (zh / en); an unknown
    mechanism reads as "unknown"."""
    e = EXPLAIN.get(mech) or EXPLAIN["unknown"]
    x = e[_lang(lang)]
    return {"mech": mech if mech in EXPLAIN else "unknown", "title": x["title"], "text": x["text"],
            "checks": list(x["checks"])}


# ----------------------------------------------------------------------------- error-history
_H2 = re.compile(r"^##\s+(.+?)\s*#*\s*$")
_H3 = re.compile(r"^###\s+(.+?)\s*#*\s*$")
_KV = re.compile(r"^\s*[-*]\s+\*\*([^*]+?)\*\*\s*:\s*(.*?)\s*$")
_DOTPATH = re.compile(r"`(Data(?:\.[^`.\s]+)+)`")
_KEYS = {"block type": "block_type", "property method": "method", "cause": "cause", "fix": "fix",
         "diagnostic note": "note", "symptom": "symptom"}
_ELSEWHERE = re.compile(r"\b(upstream|downstream|another|other|preceding|following)\b", re.I)
_lock = threading.Lock()
_hist: dict = {}        # path -> (stat key, entries)


def parse_history(text, src: str = "docs") -> list:
    """The entries of an error-history.md text: [{"src", "keyword": its H2 (upper case), "title":
    its H3, "block_type", "method", "cause", "fix", "note", "symptom", "line"}] (fields it has;
    each at most FIELD_MAX characters). An H3 before any H2, or without a cause or a fix, is
    left out; so is anything else that is not an H2, an H3 or a ``- **Key**: value`` line."""
    out, kw, cur, last = [], None, None, None

    def close():
        if cur is not None and kw and (cur.get("cause") or cur.get("fix")):
            out.append(cur)

    for i, raw in enumerate(str(text or "").splitlines(), 1):
        m3 = _H3.match(raw)
        m2 = None if m3 else _H2.match(raw)
        if m2 or m3:
            close()
            cur, last = None, None
            if m2:
                kw = " ".join(m2.group(1).split()).upper()
            elif kw:
                cur = {"src": src, "keyword": kw, "title": m3.group(1).strip()[:FIELD_MAX], "line": i}
            continue
        if raw.startswith("#"):                 # an H1 (or deeper): ends the entry, not the keyword
            close()
            cur, last = None, None
            continue
        if cur is None:
            continue
        m = _KV.match(raw)
        if m:
            key = " ".join(m.group(1).split()).lower()
            last = _KEYS.get(key, key.replace(" ", "_"))
            cur[last] = m.group(2)[:FIELD_MAX]
        elif last and raw.startswith((" ", "\t")) and raw.strip() and not raw.lstrip().startswith(("-", "*")):
            cur[last] = (cur[last] + " " + raw.strip())[:FIELD_MAX]      # a wrapped value
        else:
            last = None
    close()
    return out


def _user_history() -> Path:
    return Path(USER_HISTORY) if USER_HISTORY else Path.home() / ".aspen-mcp" / "error-history.md"


def _read_history(path: Path, src: str) -> list:
    try:
        st = os.stat(path)
    except OSError:
        return []
    key = (st.st_mtime_ns, st.st_size)
    with _lock:
        hit = _hist.get(str(path))
        if hit and hit[0] == key:
            return hit[1]
    try:
        entries = parse_history(path.read_text(encoding="utf-8", errors="replace"), src)
    except OSError as exc:
        logger.info("diagnose: %s not read (%s)", path, exc)
        return []
    with _lock:
        _hist[str(path)] = (key, entries)
    return entries


def history() -> list:
    """Every entry of both error-history files, this machine's first (see ``parse_history``)."""
    return _read_history(_user_history(), "user") + _read_history(Path(DOCS_HISTORY), "docs")


def _first_word(s) -> str:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9_-]*)", str(s or ""))
    return m.group(1).upper() if m else ""


def _types(s) -> frozenset:
    """The block types an entry's Block type names: each comma-separated part's first word,
    parentheses dropped ("Pump, Compr with performance curves" -> PUMP, COMPR)."""
    return frozenset(filter(None, map(_first_word, re.sub(r"\([^)]*\)", "", str(s or "")).split(","))))


def _fix_path(fix, block, btype, etypes) -> tuple:
    """(the fix's first Aspen path as a tree path -- ``{name}`` put back to ``block`` when it is
    that block's own field: the entry is about this block type and the words before it do not
    point elsewhere ("the upstream heater's") --, the path as the entry wrote it)."""
    m = _DOTPATH.search(str(fix or ""))
    if not m:
        return None, None
    tmpl = "\\" + m.group(1).replace(".", "\\")
    segs = tmpl.split("\\")
    own = len(segs) > 3 and segs[2] == "Blocks" and segs[3] == "{name}" and block and btype and \
        _first_word(btype) in etypes and not _ELSEWHERE.search(str(fix)[:m.start()])
    return (tmpl.replace("{name}", str(block), 1) if own else tmpl), tmpl


def _kinds(text) -> frozenset:
    """The specific failure kinds ``text`` names (``mechanisms``, not the generic input / severe)."""
    return frozenset(mechanisms(text, limit=len(EXPLAIN))) - _GENERIC


def _input_field(path) -> str:
    """The field an Input path names, upper case (``\\Data\\Blocks\\B1\\Input\\FEED_STAGE\\F`` ->
    FEED_STAGE); "" for another path."""
    segs = str(path or "").split("\\")
    i = next((k for k, s in enumerate(segs) if s.lower() == "input"), None)
    return segs[i + 1].upper() if i is not None and i + 1 < len(segs) else ""


def lore(blocks, pm=None, run_msgs=None, limit: int = LORE_MAX, fields=None) -> list:
    """The error-history entries a failure matches, best first: an entry's keyword
    in a block's BLKMSG / PER_ERROR (``blocks``: [{"name", "type", "msg", "lines"}]) or in the
    run's own messages (``run_msgs``) scores 3 -- else, the keyword's failure kind (``_kinds``: a
    heading "COLUMN NOT IN MASS BALANCE" is the kind a RadFrac message about product flow specs
    exceeding the feed names too) named there scores 2 --, the same block type 2 more, the same
    property method (``pm``) 1 more, and the fix's field changed on that block (``fields``:
    {BLOCK: {FIELD}}, upper case -- the failing blocks' fields changed since the last good run)
    1 more; neither keyword nor kind, no entry. Equal scores keep this machine's first.
    [{"src", "keyword", "title", "block_type", "method", "cause", "fix", "fix_path", "fix_template",
    "note", "score", "block"}], at most ``limit``."""
    texts = []
    for b in blocks or ():
        if isinstance(b, dict):
            texts.append((b.get("name"), b.get("type"), _words(" ".join([str(b.get("msg") or "")] +
                                                                         [str(x) for x in b.get("lines") or ()]))))
    if run_msgs:
        texts.append((None, None, _words(" ".join(str(x) for x in run_msgs))))
    texts = [(name, btype, text, _kinds(text)) for name, btype, text in texts]
    method = str(pm or "").strip().upper()
    changed = fields if isinstance(fields, dict) else {}
    best: dict = {}
    for n, e in enumerate(history()):
        kw = " ".join(e["keyword"].split())
        etypes, ekinds = _types(e.get("block_type")), _kinds(kw)
        for name, btype, text, kinds in texts:
            base = 3 if kw in text else 2 if ekinds & kinds else 0
            if not base:
                continue
            fp, tmpl = _fix_path(e.get("fix"), name, btype, etypes)
            own = fp is not None and fp != tmpl
            score = base + (2 if btype and _first_word(btype) in etypes else 0) + \
                (1 if method and str(e.get("method") or "").strip().upper() == method else 0) + \
                (1 if own and _input_field(tmpl) in (changed.get(_up(name)) or ()) else 0)
            k = (e["src"], kw, e["title"])
            if k in best and best[k][0] >= score:
                continue
            best[k] = (score, n, {"src": e["src"], "keyword": e["keyword"], "title": e["title"],
                                  **{f: e[f] for f in ("block_type", "method", "cause", "fix", "note") if e.get(f)},
                                  "fix_path": fp, "fix_template": tmpl, "score": score, "block": name})
    return [x for _, _, x in sorted(best.values(), key=lambda v: (-v[0], v[1]))][:max(0, int(limit))]


def _changed_fields(sus) -> dict:
    """{BLOCK: {FIELD}} of the value / attribute suspects on blocks (``journal.suspects``' items):
    what ``lore`` gives a point to an entry whose fix changes that field."""
    out: dict = {}
    for x in (sus or {}).get("items") or ():
        segs = str((x or {}).get("path") or "").split("\\")
        if len(segs) > 4 and segs[2] == "Blocks" and _input_field(x["path"]):
            out.setdefault(segs[3].upper(), set()).add(_input_field(x["path"]))
    return out


# ----------------------------------------------------------------------------- topology
def _up(x) -> str:
    return str(x or "").strip().upper()


def _edges(fs) -> tuple:
    """({block: [(stream, from block | None)]} the streams into each block, {block: [to blocks]})."""
    into, out = {}, {}
    for s in (fs or {}).get("streams") or ():
        if not isinstance(s, dict) or not s.get("name"):
            continue
        a, b = _up(s.get("from")), _up(s.get("to"))
        if b:
            into.setdefault(b, []).append((_up(s["name"]), a or None))
        if a and b:
            out.setdefault(a, []).append(b)
    return into, out


def upstream(flowsheet, names) -> set:
    """{("block" | "stream", NAME)} upstream of any of the blocks ``names``: the streams into
    them, the blocks those come from, and so on back to the feeds -- a block itself only when a
    recycle leads back to it."""
    into, _ = _edges(flowsheet)
    seen, todo, done = set(), [_up(n) for n in names or ()], set()
    while todo:
        b = todo.pop()
        if b in done:
            continue
        done.add(b)
        for s, a in into.get(b, ()):
            seen.add(("stream", s))
            if a:
                seen.add(("block", a))
                todo.append(a)
    return seen


def _depth(flowsheet) -> dict:
    """{block: the fewest blocks from a feed to it} (breadth first from the blocks feeds enter)."""
    into, out = _edges(flowsheet)
    level = {b: 0 for b, ins in into.items() if any(a is None for _, a in ins)}
    todo = list(level)
    while todo:
        nxt = []
        for b in todo:
            for c in out.get(b, ()):
                if c not in level:
                    level[c] = level[b] + 1
                    nxt.append(c)
        todo = nxt
    return level


def order(flowsheet, names) -> list:
    """[(name, how many of the other ``names`` are upstream of it)] -- those with none first,
    then by the distance from the feeds, then as given. Two blocks in one recycle are not
    upstream of each other."""
    names = [n for n in names or () if n]
    ups = {n: upstream(flowsheet, [n]) for n in names}
    depth = _depth(flowsheet)
    far = len(depth) + 1

    def above(n):
        return sum(1 for m in names if m != n and ("block", _up(m)) in ups[n] and ("block", _up(n)) not in ups[m])

    ranked = [(above(n), depth.get(_up(n), far), i, n) for i, n in enumerate(names)]
    return [(n, a) for a, _, _, n in sorted(ranked)]


# ----------------------------------------------------------------------------- the card
def _lines(xs) -> list:
    return [str(x).rstrip()[:WIDTH] for x in xs or () if x is not None][:LINES_MAX]


def card(req: dict) -> dict:
    """The failure card from what the page holds -- ``req`` {"model", "status":
    {block: {"level", "msg", "lines"}} (sess.status), "run_msgs": the run's Run-Status lines,
    "pm": the global property method, "sim": {"incomplete"?} (a run refused), "missing":
    {"n"}?, "flowsheet": {"blocks": [{"name", "type"}], "streams": [{"name", "from", "to"}]},
    "run": a run record id (the run the card is about; default the latest), "lang"} -- and
    the journal (``journal.suspects``; the run record's ``first_error``, tools/probes, puts its
    block on the card with its words and kind when the page's status lacks them) and the error
    histories (``lore``). No COM.

    {"v": 1, "level": "error" | "warn" | "refused" | "ok", "run": the run's journal record in
    brief | None, "blocks": [{"name", "type", "level", "msg", "lines", "mech", "upstream": the
    failing blocks upstream of it, "first"}] (errors first, upstream first), "explain": [explain()
    + "blocks": whose words named it, "run": the run's own messages did], "general": GENERAL,
    "lore": lore() (the suspects' changed fields given), "suspects": journal.suspects() | None (no
    model), "missing": {"n"} | None, and on a warning card "state": STATE_WARN in ``lang`` (the run
    converged: the card may say so beside its level)}."""
    req = req if isinstance(req, dict) else {}
    lang = _lang(req.get("lang"))
    fs = req.get("flowsheet") if isinstance(req.get("flowsheet"), dict) else {}
    types = {_up(b.get("name")): b.get("type") for b in fs.get("blocks") or () if isinstance(b, dict)}
    status = req.get("status") if isinstance(req.get("status"), dict) else {}
    bad = {n: s for n, s in status.items() if isinstance(s, dict) and s.get("level") in ("error", "warn")}
    errs = [n for n, s in bad.items() if s.get("level") == "error"]
    sim = req.get("sim") if isinstance(req.get("sim"), dict) else {}
    miss = req.get("missing") if isinstance(req.get("missing"), dict) else None
    run_msgs = [str(x) for x in req.get("run_msgs") or () if x is not None]
    refused = bool(sim.get("incomplete"))
    model, rid = req.get("model"), req.get("run")
    rid = rid.get("id") if isinstance(rid, dict) else rid
    # A refused run's suspects centre on the incomplete blocks (missing.objects), not on an
    # older run's block status.
    gaps = []
    for o in (miss or {}).get("objects") or ():
        if isinstance(o, dict) and o.get("sec") in (None, "Blocks") and o.get("name"):
            gaps.append(o["name"])
        elif isinstance(o, str) and o:
            gaps.append(o)
    focus = gaps if refused else errs or list(bad)
    sus = journal.suspects(model, run=rid, on=focus, upstream=upstream(fs, focus)) if model else None
    run = (sus or {}).get("run")
    rst = (run or {}).get("status")
    if rst == "refused" and not refused and focus != gaps:
        focus = gaps
        sus = journal.suspects(model, run=rid, on=focus, upstream=upstream(fs, focus))
    words = "\n".join(run_msgs)
    if refused or rst == "refused":
        level = "refused"
    elif errs or rst == "error" or (rst is None and words.strip() and probes.run_failed(words)):
        level = "error"
    elif bad or rst == "warn" or (rst is None and bool(probes.run_warnings(run_msgs))):
        level = "warn"
    else:
        level = "ok"
    if level == "refused":
        bad, errs, run_msgs = {}, [], []        # Aspen did not run: any block status is an older run's
    # The run record's own first error (tools/probes.first_error): its block is on the card, with
    # its words when the page has none for it, its failure kind named first, and it leads the
    # blocks that are no more upstream than it.
    fe = (run or {}).get("first_error")
    fe = fe if isinstance(fe, dict) and level == "error" and isinstance(fe.get("block"), str) and fe["block"] else None
    fe_name = None
    if fe is not None:
        fe_name = next((n for n in bad if _up(n) == _up(fe["block"])), fe["block"])
        s = dict(bad.get(fe_name) or {"level": "error"})
        fl = [x for x in fe.get("lines") if isinstance(x, str)] if isinstance(fe.get("lines"), list) else []
        if not s.get("lines") and not s.get("msg") and fl:
            s.update(msg=fl[0], lines=fl[1:])
        bad[fe_name] = s
        if s.get("level") == "error":
            errs = [fe_name] + [n for n in errs if n != fe_name]
        if not focus:                           # the page knew no failing block: the suspects centre on it
            focus = [fe_name]
            sus = journal.suspects(model, run=rid or run.get("id"), on=focus, upstream=upstream(fs, focus))
    ranked = order(fs, errs) + order(fs, [n for n in bad if n not in errs])
    blocks = []
    for i, (name, above) in enumerate(ranked[:BLOCKS_MAX]):
        s = bad[name]
        lines = _lines(s.get("lines"))
        mech = mechanisms(" ".join([str(s.get("msg") or "")] + lines))
        if fe is not None and name == fe_name and isinstance(fe.get("kind"), str) and fe["kind"] in EXPLAIN:
            mech = ([fe["kind"]] + [m for m in mech if m != fe["kind"]])[:MECH_MAX]
        blocks.append({"name": name, "type": types.get(_up(name)) or s.get("type"), "level": s["level"],
                       "msg": str(s.get("msg") or "")[:WIDTH], "lines": lines, "mech": mech,
                       "upstream": above, "first": i == 0})
    run_mech = mechanisms(" ".join(run_msgs))
    explain_out, seen = [], {}
    if level != "refused":
        for b in blocks:
            for m in b["mech"]:
                if m not in seen:
                    seen[m] = dict(explain(m, lang), blocks=[], run=False)
                    explain_out.append(seen[m])
                seen[m]["blocks"].append(b["name"])
        for m in run_mech:
            if m not in seen:
                seen[m] = dict(explain(m, lang), blocks=[], run=False)
                explain_out.append(seen[m])
            seen[m]["run"] = True
        if not explain_out and level in ("error", "warn"):
            explain_out.append(dict(explain("unknown", lang), blocks=[b["name"] for b in blocks], run=bool(run_msgs)))
    missing = {"n": miss.get("n")} if miss is not None else ({"n": None} if level == "refused" else None)
    out = {"v": 1, "level": level, "run": (sus or {}).get("run"), "blocks": blocks, "explain": explain_out,
           "general": list(GENERAL[lang]),
           "lore": lore(blocks, req.get("pm"), run_msgs, fields=_changed_fields(sus)) if blocks or run_msgs else [],
           "suspects": sus, "missing": missing}
    if level == "warn":
        out["state"] = STATE_WARN[lang]
    return out


# ----------------------------------------------------------------------------- a session's card, and in words
MISSING_NAMES = 8       # incomplete objects a refused run's card names
SAID_MAX = 16           # cards remember() keeps
_PATHS = re.compile(r"\\Data(?:\\[^\\,;\s]+)+")
_said: dict = {}        # (model, run id) -> card: the workbench's, for the brief and an Ask AI note's text
# A run refused in a session Aspen reported an internal fault in, as main_tools.fault_refusal words
# it (aspen_manager.FAULT_TEXT): no input is missing then.
_FAULT_SAID = "reported an internal fault"


def missing_of(miss, result=None, limit: int = MISSING_NAMES) -> dict:
    """A refused run's "what is missing": {"n", "objects": [{"path", "sec", "name", "type"?,
    "what"?}], "more"?, "stale"?} from the session's ``missing`` (the missing-inputs scan) once it has one,
    else from the paths the refusal (``result``) names -- a container there stands for its
    children (run_simulation's own words)."""
    objs, n, stale = [], 0, False
    if isinstance(miss, dict) and miss.get("state") in ("complete", "incomplete"):
        for o in miss.get("objects") or ():
            if isinstance(o, dict) and o.get("path"):
                objs.append({k: o[k] for k in ("path", "sec", "name", "type", "what") if o.get(k)})
        n, stale = int(miss.get("n") or len(objs)), bool(miss.get("stale"))
    else:
        for p in dict.fromkeys(x.rstrip(".") for x in _PATHS.findall(str(result or ""))):
            segs = p.split("\\")
            objs.append({"path": p, "sec": segs[2] if len(segs) > 2 else "Data", "name": segs[-1]})
        n = len(objs)
    out = {"n": n, "objects": objs[:max(0, int(limit))]}
    if n > len(out["objects"]):
        out["more"] = n - len(out["objects"])
    if stale:
        out["stale"] = True
    return out


def session_card(sess, rec=None, lang="en", model=None, latest: bool = True) -> dict:
    """``card`` for a workbench session as state.json holds it -- ``sess`` {"model", "status",
    "run_msgs", "pm", "flowsheet", "missing", "sim"} -- about its run ``rec`` (a journal run
    record, or its brief; None: the newest the journal has, refused when ``sim.incomplete``).
    ``latest``: the session's block status and run messages are that run's (the workbench builds
    the card right after it); else the record's own ``blocks`` and ``msgs`` stand in (an older
    run). A refused run's ``missing`` names the incomplete objects (``missing_of``) -- unless the
    session was refused for Aspen's internal fault (the record's result says so, _FAULT_SAID):
    then ``fault`` true and no ``missing``, nothing being incomplete. No COM."""
    sess = sess if isinstance(sess, dict) else {}
    rec = rec if isinstance(rec, dict) else {}
    model = model or (sess.get("model") or {}).get("id")
    refused = rec.get("status") == "refused" if rec.get("status") else bool((sess.get("sim") or {}).get("incomplete"))
    fault = refused and _FAULT_SAID in str(rec.get("result") or "")
    if latest:
        status, msgs = sess.get("status") or {}, sess.get("run_msgs") or []
    else:
        bl = rec.get("blocks") if isinstance(rec.get("blocks"), dict) else {}
        status = {str(b): {"level": lv, "msg": "", "lines": []} for b, lv in bl.items() if lv in ("error", "warn")}
        msgs = rec.get("msgs") or []
    miss = sess.get("missing") if isinstance(sess.get("missing"), dict) else None
    c = card({"model": model, "status": status, "run_msgs": msgs, "pm": sess.get("pm"),
              "sim": {"incomplete": True} if refused else {}, "missing": miss if refused and not fault else None,
              "flowsheet": sess.get("flowsheet") or {}, "run": rec.get("id"), "lang": lang})
    if c["level"] == "refused" and fault:
        c.update(fault=True, missing=None)
    elif c["level"] == "refused":
        c["missing"] = missing_of(miss, rec.get("result"))
    return c


def remember(model, c) -> None:
    """Keep the workbench's card of a run (by model and the run record's id) for ``recall``."""
    rid = ((c or {}).get("run") or {}).get("id") if isinstance(c, dict) else None
    if model and rid:
        with _lock:
            _said.pop((model, rid), None)
            _said[(model, rid)] = c
            while len(_said) > SAID_MAX:
                _said.pop(next(iter(_said)))


def recall(model, rid) -> dict | None:
    with _lock:
        return _said.get((model, rid))


def _clock(t) -> str:
    try:
        return journal._clock(t) or ""
    except (ValueError, OverflowError, OSError):
        return ""


def _who(r) -> str:
    return ", ".join(x for x in (r.get("actor"), r.get("via"), _clock(r.get("t"))) if x)


def _change(x, name) -> str:
    """One suspect in words: a field "<name> 40 → 120 (ai, 14:02)", a structure change "removed
    stream S7 (user, 14:03)"."""
    who = ", ".join(v for v in (x.get("actor"), _clock(x.get("t"))) if v)
    if x.get("op") in ("value", "attr"):
        field = name(x["path"]) if name is not None else x.get("path")
        what = f"{field} {journal._val(x.get('before'))} → {journal._val(x.get('after'))}"
    else:
        verb = {"add": "added", "remove": "removed", "connect": "reconnected", "restore": "restored"}.get(x.get("op"), x.get("op"))
        what = " ".join(str(v) for v in (verb, x.get("kind"), x.get("name") or x.get("block"), x.get("port")) if v)
    return f"{what} ({who})" if who else what


def say(c, name=None, short: bool = False) -> str:
    """A card in one English line, for the AI (workbench_read's ``diagnosis``, the brief, an Ask
    AI note about a run): the run, where it failed and the failure kind in our words (EXPLAIN's
    English title and its key), Aspen's own line that named it (not ``short``), the incomplete
    objects of a refused run, what changed since the last good run -- ``name(path)``: a field in
    words (default: its path) -- and, when a later run went through, that it did. "" for no card."""
    if not isinstance(c, dict) or c.get("level") not in ("error", "warn", "refused", "ok"):
        return ""
    r, lv = c.get("run") or {}, c["level"]
    head = f"run #{r['seq']}" if r.get("seq") else "the last run"
    if r and not short:
        head += f" ({_who(r)})"
    blocks = c.get("blocks") or []
    if lv == "refused" and c.get("fault"):
        text = (f"{head} was refused, Aspen did not start: Aspen reported an internal fault in this session "
                "(export or save a copy, then close and reopen the model)")
    elif lv == "refused":
        m = c.get("missing") or {}
        objs = [(f"{o.get('name')} ({o['type']})" if o.get("type") else str(o.get("name") or o.get("path")))
                for o in m.get("objects") or ()]
        text = f"{head} was refused, Aspen did not start: inputs incomplete"
        if objs:
            more = (m.get("n") or 0) - len(objs[:4])
            text += f" ({', '.join(objs[:4])}" + (f" +{more} more" if more > 0 else "") + ")"
    elif lv == "ok":
        text = f"{head} ended ok"
    else:
        b = next((x for x in blocks if x.get("level") == "error"), blocks[0] if blocks else None)
        ex = c.get("explain") or []
        e = next((x for x in ex if b and b["name"] in (x.get("blocks") or ())), ex[0] if ex else None)
        mech = (e or {}).get("mech") or "unknown"
        text = f"{head} {'failed' if lv == 'error' else 'ended with warnings (converged)'}"
        if b:
            text += f" at {b['name']}" + (f" ({b['type']})" if b.get("type") else "")
        text += f": {explain(mech, 'en')['title']} [{mech}]"
        if b and not short:
            said = [str(x) for x in [b.get("msg")] + list(b.get("lines") or ()) if x and str(x).strip()]
            line = next((x for x in said if mech in mechanisms(x, limit=len(EXPLAIN))), said[0] if said else None)
            if line:
                text += f"; Aspen: {' '.join(line.split())[:120]}"
            others = [x["name"] for x in blocks if x is not b]
            if others:
                text += f"; also: {', '.join(others[:4])}" + (f" +{len(others) - 4}" if len(others) > 4 else "")
    s = c.get("suspects") or {}
    st, top = s.get("state"), 2 if short else 4
    items = list(s.get("items") or ()) + list(s.get("struct") or ())
    if st in ("ok", "never_ok") and items:
        since = s.get("since") or {}
        lead = "changed since the last good run" + (f" #{since['seq']}" if since.get("seq") and not short else "") \
            if st == "ok" else "no good run on record; changed since the model was opened"
        more = len(items) - top + (s.get("more") or 0)
        text += f"; {lead}: " + "; ".join(_change(x, name) for x in items[:top]) + (f" (+{more} more)" if more > 0 else "")
    elif st == "none_since":
        text += "; nothing changed since the last good run"
    if not short and lv != "ok" and c.get("lore"):
        lo = c["lore"][0]
        text += f"; error-history ({'this machine' if lo.get('src') == 'user' else 'shipped'}): {lo.get('title')}"
    fx = c.get("fixed") if isinstance(c.get("fixed"), dict) else None
    if fx:
        text += "; since then " + (f"run #{fx['seq']}" if fx.get("seq") else "a run") + f" ended {fx.get('status')}"
    return text
