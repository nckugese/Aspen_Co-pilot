"""Where a tree path is, in words: ``\\Data\\Blocks\\ESTCOL\\Input\\BASIS_RR`` reads
"Blocks › ESTCOL (RadFrac) › Reflux ratio", with the zh-TW gloss 迴流比.

A field is named by the first of:
  1. the glossary below: short English labels for each field and our own
     zh-TW explanations;
  2. the prompt this machine's Aspen gave for the field (HAP_PROMPT, attr 19), learned.json;
  3. the variable description extracted from this machine's Aspen, labels.json "vars";
  4. the code itself.
A name of 2 or 3 gets its zh-TW from data/terms_zh.json (term), where that has it.
An option code is named by the extracted display name, with the extracted one-line description
(the codes a field takes are the docs': tools/doc_index.py). AspenTech's bulk text -- prompts,
option descriptions, display names -- is never in this file: it is read only at run time, from
the extraction of the user's own installation under ~/.aspen-mcp/aspen-strings/<version>/
(tools/aspen_strings.py).

    loc(path, type)          {"sec","obj","type","io","field","code","q","gl","hint","src"}
    text(loc, form, lang)    "full" breadcrumb or "short"; never a backslash
    say(path, type, lang)    short text with the zh gloss, for plain-text messages
    named(path, types, form) short text with the code beside, for the AI (journal lines, the brief)
    option(type, field, code)  {"code","name","desc"}
    meaning(path, value, types)  an input's option code in words, for the inspector: {"en","zh"?,"desc"?}
    choices(path, value, types, codes)  the values a field takes from a list, for the inspector's menu
    header(key)              a form sheet's title from its resource key (tools/gui_sheets.py)
    term(text), terms()      our zh-TW for a title or field name (data/terms_zh.json)
    form_name(form)          a form's navigation-pane title from its class (tools/gui_sheets.py)
    type_name(type)          a record type as Aspen's forms write it (RADFRAC -> RadFrac)
    decorate(record(s), types) journal records + "loc", before/after "show" (and "tip")
    labels(paths, types)     {path: loc}, for the window's Api.labels
    sources()                the files labels come from and their mtimes (the window's Api.strings)
    learn_key(s) / learn     the server's attr-19 learning (learned.json; only it writes)

Pure stdlib, no I/O at import, no COM; files are read on first use and again when their mtime
changes; nothing here raises.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import re
import threading
from pathlib import Path

from tools import aspen_strings as AS

logger = logging.getLogger(__name__)

ARROW, DOT = " › ", " · "
PROMPT_MAX = 40
LEARN_MAX = 5000

# ------------------------------------------------------------------------------ glossary
# scope -> io -> FIELD -> (Aspen's English, zh-TW gloss[, zh-TW hint]). A scope is a block
# type, "*" (any block), STREAM, or a section (COMPONENTS, PROPERTIES, REACTIONS, ...).
_GLOSSARY = {
    "*": {"in": {"TEMP": ("Temperature", "溫度"), "PRES": ("Pressure", "壓力", "0 或負值代表相對於進料的壓降"),
                 "DUTY": ("Duty", "熱負荷", "正值加熱、負值移熱"), "VFRAC": ("Vapor fraction", "汽化率", "0 飽和液、1 飽和汽"),
                 "SPEC_OPT": ("Flash specifications", "閃蒸規格組合"), "DELT": ("Temperature change", "溫度變化"),
                 "DEGSUP": ("Degrees of superheating", "過熱度"), "DEGSUB": ("Degrees of subcooling", "過冷度"),
                 "NPHASE": ("Valid phases", "有效相數"), "PHASE": ("Phase", "相態"), "RXN_ID": ("Reaction sets", "反應組"),
                 "T_EST": ("Temperature estimate", "溫度初估值"), "PDROP": ("Pressure drop", "壓降"),
                 "COEF": ("Reactant coefficient", "反應物係數"), "COEF1": ("Product coefficient", "產物係數"),
                 "OPSETNAME": ("Property method", "這個 block 專用的物性方法"),
                 "FRWATEROPSET": ("Free-water method", "游離水物性方法"), "HENRY_COMPS": ("Henry components", "亨利元件組"),
                 "FEED_STAGE": ("Feed stage", "進料板"), "PROD_STAGE": ("Product stage", "側線出料板")},
          "out": {"B_TEMP": ("Outlet temperature", "出口溫度"), "B_PRES": ("Outlet pressure", "出口壓力"),
                  "B_VFRAC": ("Vapor fraction", "汽化率"), "QCALC": ("Duty", "熱負荷"), "QNET": ("Net duty", "淨熱負荷"),
                  "LIQ_RATIO": ("1st liquid / total liquid", "第一液相占總液相比例"),
                  "X": ("Liquid mole fraction", "液相莫耳分率"), "Y": ("Vapor mole fraction", "汽相莫耳分率"),
                  "X1": ("1st liquid mole fraction", "第一液相莫耳分率"), "X2": ("2nd liquid mole fraction", "第二液相莫耳分率")}},
    "RADFRAC": {"in": {"NSTAGE": ("Stages", "理論板數", "含冷凝器與再沸器"),
                       "BASIS_RR": ("Reflux ratio", "迴流比", "回流液量 ÷ 餾出量"),
                       "BASIS_BR": ("Boilup ratio", "再沸比", "再沸蒸氣量 ÷ 塔底量"),
                       "BASIS_D": ("Distillate rate", "餾出量"), "BASIS_B": ("Bottoms rate", "塔底量"),
                       "BASIS_VN": ("Boilup rate", "再沸蒸氣量"), "D:F": ("Distillate to feed ratio", "餾出/進料比"),
                       "B:F": ("Bottoms to feed ratio", "塔底/進料比"), "QN": ("Reboiler duty", "再沸器熱負荷"),
                       "Q1": ("Condenser duty", "冷凝器熱負荷"), "CONDENSER": ("Condenser", "冷凝器型式"),
                       "REBOILER": ("Reboiler", "再沸器型式"), "CALC_MODE": ("Calculation type", "計算類型"),
                       "NO_PHASE": ("Valid phases", "有效相數"), "FEED_STAGE": ("Feed stage", "進料板", "由塔頂往下數"),
                       "FEED_CONVEN": ("Convention", "進料方式"), "PRES1": ("Top pressure", "塔頂壓力"),
                       "STAGE_PRES": ("Stage pressure", "板壓力"), "DP_STAGE": ("Stage pressure drop", "每板壓降"),
                       "HEATER_DUTY": ("Heater duty", "側加熱／冷卻熱負荷"), "CONV_METH": ("Convergence", "收斂方法"),
                       "ALGORITHM": ("Algorithm", "演算法"), "MAXOL": ("Maximum iterations", "最大迭代次數"),
                       "PROD_STAGE": ("Product stage", "側線出料板"), "PROD_FLOW": ("Product flow", "側線產物流量"),
                       "PROD_PHASE": ("Product phase", "產物相態"), "BASIS_L1": ("Reflux rate", "迴流量"),
                       "RW": ("Free water reflux ratio", "游離水迴流比"), "OPT_PRES": ("Pressure drop for rest of column", "其餘塔段壓降指定方式"),
                       "DP_COL": ("Column pressure drop", "其餘塔段總壓降"), "RR_BASIS": ("Reflux ratio basis", "迴流比基準"),
                       "BR_BASIS": ("Boilup ratio basis", "再沸比基準"), "D_BASIS": ("Distillate rate basis", "餾出量基準"),
                       "B_BASIS": ("Bottoms rate basis", "塔底量基準"), "L1_BASIS": ("Reflux rate basis", "迴流量基準"),
                       "VN_BASIS": ("Boilup rate basis", "再沸蒸氣量基準"), "D:F_BASIS": ("Distillate to feed ratio basis", "餾出／進料比基準"),
                       "B:F_BASIS": ("Bottoms to feed ratio basis", "塔底／進料比基準")},
                "out": {"REB_DUTY": ("Reboiler duty", "再沸器熱負荷"), "COND_DUTY": ("Condenser duty", "冷凝器熱負荷"),
                        "TOP_TEMP": ("Top temperature", "塔頂溫度"), "MOLE_RR": ("Reflux ratio", "迴流比"),
                        "MOLE_D": ("Distillate rate", "餾出量"), "MOLE_B": ("Bottoms rate", "塔底量"),
                        "MOLE_VN": ("Boilup rate", "再沸蒸氣量"), "BU_RATIO": ("Boilup ratio", "再沸比"),
                        "MASS_BR": ("Mass boilup ratio", "質量再沸比"), "PRES1": ("Top pressure", "塔頂壓力"),
                        "SCDUTY": ("Subcooled duty", "過冷熱負荷"), "MOLE_L1": ("Reflux rate", "迴流量"),
                        "RW": ("Free water reflux ratio", "游離水迴流比"), "REB_POUT": ("Reboiler pressure", "再沸器壓力"),
                        "REB_TOUT": ("Reboiler temperature", "再沸器溫度"), "B_TEMP": ("Stage temperature", "各板溫度"),
                        "B_PRES": ("Stage pressure", "各板壓力")}},
    "RPLUG": {"in": {"TYPE": ("Reactor type", "反應器型式"), "LENGTH": ("Length", "長度"), "DIAM": ("Diameter", "管徑"),
                     "NTUBE": ("Tubes", "管數", "多管式反應器的管數"), "CAT_PRESENT": ("Catalyst present", "有觸媒"),
                     "BED_VOIDAGE": ("Bed voidage", "床空隙率"), "CAT_RHO": ("Particle density", "觸媒顆粒密度"),
                     "DIA_PART": ("Particle diameter", "顆粒直徑"), "SPHERICITY": ("Shape factor", "形狀因子"),
                     "IGN_CAT_VOL": ("Ignore catalyst volume", "計算滯留時間時忽略觸媒體積")},
              "out": {"RES_TIME": ("Residence time", "滯留時間"), "TMIN": ("Minimum temperature", "最低溫度"),
                      "TMAX": ("Maximum temperature", "最高溫度"), "COOLANT_TIN": ("Thermal fluid inlet temperature", "熱媒入口溫度"),
                      "COOLANT_VIN": ("Thermal fluid inlet vapor fraction", "熱媒入口汽化率"),
                      "B_TEMP": ("Temperature profile", "沿管溫度分布"), "B_VFRAC": ("Vapor fraction profile", "沿管汽化率分布")}},
    "HEATX": {"in": {"SPEC": ("Exchanger specification", "換熱器規格"), "VALUE": ("Specification value", "規格值"),
                     "MODE": ("Model fidelity", "計算模型"), "PROGRAM_MODE": ("Calculation mode", "計算模式"),
                     "TYPE": ("Flow direction", "流動方向"), "SIDE_VAR": ("Specification side", "規格指定在哪一側"),
                     "AREA": ("Area", "換熱面積"), "UA": ("UA", "總括熱傳係數 × 面積"),
                     "MIN_TAPP": ("Minimum temperature approach", "最小溫差"),
                     "PRES_HOT": ("Hot side outlet pressure", "熱側出口壓力"), "PRES_COLD": ("Cold side outlet pressure", "冷側出口壓力")},
              "out": {"HOTINT": ("Hot inlet temperature", "熱流入口溫度"), "HOTINP": ("Hot inlet pressure", "熱流入口壓力"),
                      "HOTINVF": ("Hot inlet vapor fraction", "熱流入口汽化率"), "HOT_TEMP": ("Hot outlet temperature", "熱流出口溫度"),
                      "HOT_PRES": ("Hot outlet pressure", "熱流出口壓力"), "HOT_VFRAC": ("Hot outlet vapor fraction", "熱流出口汽化率"),
                      "COLDINT": ("Cold inlet temperature", "冷流入口溫度"), "COLDINP": ("Cold inlet pressure", "冷流入口壓力"),
                      "COLDINVF": ("Cold inlet vapor fraction", "冷流入口汽化率"), "COLD_TEMP": ("Cold outlet temperature", "冷流出口溫度"),
                      "COLD_PRES": ("Cold outlet pressure", "冷流出口壓力"), "COLD_FRAC": ("Cold outlet vapor fraction", "冷流出口汽化率"),
                      "HX_DUTY": ("Heat duty", "換熱量"), "HX_AREAC2": ("Required area", "所需換熱面積"), "HX_UA": ("UA", "UA 值"),
                      "HX_DTLM": ("LMTD (corrected)", "修正後對數平均溫差"), "HX_FMTD": ("LMTD correction factor", "LMTD 修正係數")}},
    "HEATER": {"in": {"DPPARM": ("Pressure-drop correlation parameter", "壓降關聯式參數")}},
    "RSTOIC": {"in": {"CONV": ("Fractional conversion", "轉化率", "關鍵元件轉化的比例，0–1"), "KEY_CID": ("Key component", "關鍵元件"),
                      "OPT_EXT_CONV": ("Conversion or extent", "用轉化率還是反應程度指定"), "EXTENT": ("Molar extent", "反應程度"),
                      "SERIES": ("Reactions occur in series", "反應依序進行")}},
    "RCSTR": {"in": {"VOL": ("Volume", "體積"), "RES_TIME": ("Residence time", "滯留時間"),
                     "SPEC_TYPE": ("Specification type", "尺寸規格"), "SPEC_OPT": ("Operating condition", "操作條件規格"),
                     "PHASE": ("Valid phases", "有效相")},
              "out": {"TOT_VOL": ("Total volume", "總體積"), "TOT_RES_TIME": ("Residence time", "滯留時間"),
                      "VAP_VOL": ("Vapor volume", "氣相體積"), "LIQ_VOL": ("Liquid volume", "液相體積"),
                      "VAP_RES_TIME": ("Vapor residence time", "氣相滯留時間"),
                      "COND_RES_TIM": ("Condensed phase residence time", "凝相滯留時間")}},
    "RYIELD": {"in": {"MOLE_YIELD": ("Component yield", "元件產率")}},
    "PUMP": {"in": {"PRES": ("Outlet pressure", "出口壓力"), "EFF": ("Efficiency", "效率"), "OPT_SPEC": ("Outlet specification", "出口規格"),
                    "DELP": ("Pressure increase", "升壓"), "PRATIO": ("Pressure ratio", "壓力比"), "POWER": ("Power required", "所需功率"),
                    "DEFF": ("Driver efficiency", "驅動機效率"), "PUMP_TYPE": ("Model", "泵或水力渦輪")},
             "out": {"POC": ("Outlet pressure", "出口壓力"), "BRAKE_POWER": ("Brake power", "軸功率"), "WNET": ("Net work", "淨功"),
                     "FLUID_POWER": ("Fluid power", "流體功率"), "ELEC_POWER": ("Electricity", "耗電"),
                     "HEAD_CAL": ("Head developed", "揚程"), "CEFF": ("Efficiency used", "採用的效率"),
                     "VFLOW": ("Volumetric flow rate", "體積流量"), "PDRP": ("Pressure change", "壓力變化")}},
    "COMPR": {"in": {"PRES": ("Outlet pressure", "出口壓力"), "SEFF": ("Isentropic efficiency", "等熵效率"), "TYPE": ("Type", "壓縮計算方法"),
                     "OPT_SPEC": ("Outlet specification", "出口規格"), "DELP": ("Pressure increase", "升壓"),
                     "PRATIO": ("Pressure ratio", "壓力比"), "POWER": ("Power required", "所需功率"),
                     "TEMP": ("Outlet temperature", "出口溫度"), "PEFF": ("Polytropic efficiency", "多變效率"),
                     "MEFF": ("Mechanical efficiency", "機械效率")},
              "out": {"POC": ("Outlet pressure", "出口壓力"), "TOC": ("Outlet temperature", "出口溫度"),
                      "BRAKE_POWER": ("Brake power", "軸功率"), "WNET": ("Net work", "淨功"), "IND_POWER": ("Indicated power", "指示功率"),
                      "EPC": ("Efficiency used", "採用的效率"), "TOS": ("Isentropic outlet temperature", "等熵出口溫度"),
                      "DELP_CAL": ("Pressure change", "壓力變化"), "PRES_RATIO": ("Pressure ratio", "壓力比")}},
    "VALVE": {"in": {"P_OUT": ("Outlet pressure", "出口壓力"), "P_DROP": ("Pressure drop", "壓降"), "MODE": ("Calculation type", "計算類型"),
                     "OPT_DESIGN": ("Pressure specification", "壓力規格"), "VAL_POSN": ("Valve % opening", "閥開度 (%)"),
                     "FLO_COEF": ("Flow coefficient", "流量係數 Cv")},
              "out": {"P_OUT_OUT": ("Outlet pressure", "出口壓力"), "VALVE_DP": ("Pressure drop", "壓降"),
                      "VALVE_POSN": ("Valve % opening", "閥開度 (%)")}},
    "FSPLIT": {"in": {"FRAC": ("Split fraction", "分流比例"), "BASIS_LIMIT": ("Limit flow", "流量上限")},
               "out": {"STREAMFRAC": ("Split fraction", "分流比例")}},
    "DISTL": {"in": {"D_F": ("Distillate to feed ratio", "餾出／進料比")}},
    "EXTRACT": {"in": {"HEATER_DUTY": ("Stage heater duty", "板上加熱／冷卻熱負荷")}},
    "DSTWU": {"in": {"LIGHTKEY": ("Light key", "輕關鍵元件"), "HEAVYKEY": ("Heavy key", "重關鍵元件"),
                     "RECOVL": ("Light key recovery", "輕關鍵元件在餾出的回收率"), "RECOVH": ("Heavy key recovery", "重關鍵元件在塔底的回收率"),
                     "PTOP": ("Condenser pressure", "冷凝器壓力"), "PBOT": ("Reboiler pressure", "再沸器壓力"),
                     "RR": ("Reflux ratio", "迴流比"), "NSTAGE": ("Number of stages", "理論板數")},
              "out": {"MIN_REFLUX": ("Minimum reflux ratio", "最小迴流比"), "ACT_REFLUX": ("Actual reflux ratio", "實際迴流比"),
                      "MIN_STAGES": ("Minimum number of stages", "最少理論板數"), "ACT_STAGES": ("Actual number of stages", "實際理論板數"),
                      "FEED_LOCATN": ("Feed stage", "進料板位置")}},
    "STREAM": {"in": {"TEMP": ("Temperature", "溫度"), "PRES": ("Pressure", "壓力"), "TOTFLOW": ("Total flow", "總流量"),
                      "FLOW": ("Component flow", "成分流量", "各成分的量；基準看 Composition 的單位"),
                      "FLOWBASE": ("Flow basis", "流量基準"), "VFRAC": ("Vapor fraction", "汽化率"),
                      "BASIS": ("Composition basis", "組成基準"), "MIXED_SPEC": ("State variables", "狀態變數")},
               "out": {"TOT_FLOW": ("Total mole flow", "總莫耳流量"), "RES_TEMP": ("Temperature", "溫度"), "RES_PRES": ("Pressure", "壓力"),
                       "TEMP_OUT": ("Temperature", "溫度"), "PRES_OUT": ("Pressure", "壓力"), "VFRAC_OUT": ("Vapor fraction", "汽化率"),
                       "MOLEFLOW": ("Component mole flow", "成分莫耳流量"), "MOLEFRAC": ("Mole fraction", "莫耳分率"),
                       "MASSFLOW": ("Component mass flow", "成分質量流量"), "MASSFRAC": ("Mass fraction", "質量分率"),
                       "TEMP": ("Temperature", "溫度"), "PRES": ("Pressure", "壓力"), "VFRAC": ("Vapor fraction", "汽化率"),
                       "MOLEFLMX": ("Total mole flow", "總莫耳流量"), "MASSFLMX": ("Total mass flow", "總質量流量"),
                       "VOLFLMX": ("Total volume flow", "總體積流量")}},
    "COMPONENTS": {"in": {"TYPE": ("Type", "元件類型"), "ANAME": ("Component name", "元件名稱，資料庫裡的名字")}},
    "PROPERTIES": {"in": {"GBASEOPSET": ("Base method", "基礎物性方法"), "GOPSETNAME": ("Method name", "物性方法"),
                          "GHEN": ("Henry components", "亨利元件組")}},
    "REACTIONS": {"in": {"REACTYPE": ("Reaction type", "反應類型"), "EXPONENT": ("Exponent", "濃度次方"),
                         "PRE_EXP": ("Pre-exponential factor", "頻率因子 k"), "ACT_ENERGY": ("Activation energy", "活化能"),
                         "COEF": ("Coefficient", "化學計量係數"), "COEF1": ("Product coefficient", "產物係數")}},
}
FIELDS = {(s, io, f): (v[0], v[1], v[2] if len(v) > 2 else None)
          for s, ios in _GLOSSARY.items() for io, fs in ios.items() for f, v in fs.items()}
_EN_ZH = {v[0].lower(): v[1] for v in reversed(list(FIELDS.values()))}   # a field name's zh-TW (the first one's)


# Our zh-TW words for the titles the workbench shows -- form, sheet, collection, model object, palette
# tab -- and for field names the glossary above does not have (named by a prompt or the docs), keyed by
# the English (data/terms_zh.json; the window gets it in the catalog: terms()).
TERMS = Path(__file__).resolve().parent / "data" / "terms_zh.json"


@functools.lru_cache(maxsize=1)
def _terms() -> dict:
    try:
        d = json.loads(TERMS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("aspen-labels: %s not read: %r", TERMS, exc)
        return {}
    return {str(k).lower(): str(v) for k, v in d.items()} if isinstance(d, dict) else {}


def terms() -> dict:
    """{english, lower case: zh-TW} of data/terms_zh.json."""
    return dict(_terms())


def term(text) -> str | None:
    """Our zh-TW for an English title or field name (any case), else None."""
    return _terms().get(" ".join(str(text or "").split()).lower())


def _fkey(field) -> str:
    """A field as labels.json keys it: upper case, non-alphanumerics as '_' (PUMP-TYPE -> PUMP_TYPE)."""
    return re.sub(r"[^A-Z0-9]", "_", str(field or "").upper())


# Block types as Aspen spells them (attr 6 already does; this is for upper-case input).
_TYPES = {t.upper(): t for t in (
    "RadFrac", "DSTWU", "Distl", "Extract", "MultiFrac", "PetroFrac", "SCFrac", "BatchSep", "RPlug", "RCSTR", "RStoic",
    "RGibbs", "RYield", "REquil", "RBatch", "Heater", "HeatX", "MHeatX", "HXFlux", "Flash2", "Flash3", "Decanter",
    "Mixer", "FSplit", "SSplit", "Sep", "Sep2", "Pump", "Compr", "MCompr", "Valve", "Pipe", "Pipeline", "Dupl", "Mult",
    "Crystallizer", "Crusher", "Screen", "Cyclone", "Filter", "Dryer", "Granulator", "FabFl", "CFuge", "HyCyc", "CCD",
    "SWash", "VScrub", "ESP", "ClChng", "Selector", "Analyzer", "Hierarchy", "User", "User2", "User3")}

# The top of Aspen's navigation tree, by the \Data\ segment.
SECTIONS = {"Blocks": "Blocks", "Streams": "Streams", "Components": "Components", "Properties": "Methods",
            "Reactions": "Reactions", "Flowsheeting Options": "Flowsheeting Options",
            "Model Analysis Tools": "Model Analysis Tools", "Convergence": "Convergence", "Setup": "Setup",
            "Utilities": "Utilities"}
_UNNAMED = {"Components", "Methods", "Setup"}       # a short label names the section, not "Specifications"

# ------------------------------------------------------------------------------ files
_lock = threading.Lock()
_cache: dict = {}                       # name -> (stat key, value)
_batch = threading.local()              # decorate()/labels(): one stat per file per call


def _stat(p) -> tuple | None:
    try:
        st = os.stat(p)
        return (str(p), st.st_mtime_ns, st.st_size)
    except (OSError, TypeError, ValueError):
        return None


def _cached(name: str, path, load):
    """load(path) once per (path, mtime, size); inside a batch, the value it already has."""
    hit = _cache.get(name)
    if hit is not None and getattr(_batch, "on", False):
        return hit[1]
    key = _stat(path) if path else None
    if hit is not None and hit[0] == key:
        return hit[1]
    try:
        val = load(path) if key else None
    except Exception as exc:  # noqa: BLE001 -- a bad file reads as no file
        logger.warning("aspen-labels: cannot read %s: %r", path, exc)
        val = None
    with _lock:
        _cache[name] = (key, val)
    return val


def _json(p):
    v = json.loads(Path(p).read_text(encoding="utf-8"))
    return v if isinstance(v, dict) else None


def _base() -> Path:
    return Path(AS.ROOT) / "aspen-strings"


def _where() -> tuple:
    """(labels.json or None, learned.json) -- aspen_strings.labels_file() and the folder beside
    it (else the status's version, else "local"); worked out again only when status.json changes."""
    hit = _cache.get("where")
    if hit is not None and getattr(_batch, "on", False):
        return hit[1]
    key = _stat(_base() / "status.json")
    if hit is not None and hit[0] == key:
        return hit[1]
    f = AS.labels_file()
    if f is not None:
        learned = f.parent / "learned.json"
    else:
        ver = AS.status().get("aspen")
        learned = _base() / (re.sub(r"[^\w.-]", "_", str(ver)) if ver else "local") / "learned.json"
    with _lock:
        _cache["where"] = (key, (f, learned))
    return f, learned


def _labels() -> dict:
    return _cached("labels", _where()[0], _json) or {}


def _learned_path() -> Path:
    return _where()[1]


def _learned() -> dict:
    d = _cached("learned", _learned_path(), _json) or {}
    f = d.get("fields")
    return f if isinstance(f, dict) else {}


# ------------------------------------------------------------------------------ helpers
def _safe(default):
    """Never raise into the caller: log and return default(*args)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            try:
                return fn(*a, **k)
            except Exception as exc:  # noqa: BLE001
                logger.warning("aspen-labels: %s failed: %r", fn.__name__, exc)
                return default(*a, **k)
        return wrapper
    return deco


def _tkey(type_) -> str:
    return str(type_ or "").strip().upper()


def _tname(type_) -> str | None:
    t = str(type_ or "").strip()
    if not t:
        return None
    return _TYPES.get(t.upper()) or (_labels().get("types") or {}).get(t.upper()) or t


_LEAD = re.compile(r"^(?:lets? you (?:type|enter|specify|select|choose|define|deselect/select|select/deselect)"
                   r"(?: or create)?(?: in)?|when (?:selected|checked),(?: allows you to)?|specif(?:y|ies)"
                   r"|indicates|specified|calculated|the|not available; for future development\.)\s+", re.I)
_CUT = re.compile(r"\. |, | \(|;| = |/(?=[A-Z])|\.$|:\s|:$")
_TAILWORDS = {"the", "a", "an", "of", "in", "for", "to", "and", "or", "with", "on", "at", "by", "from"}


def short_prompt(text) -> str:
    """A field name from a prompt: 'Lets you type the number of stages, including ...' ->
    'Number of stages'. Leading 'Lets you type/select (the)', 'Specified', 'Calculated' go;
    the text ends at the first '. ', ', ', ' (' or ';'; at most PROMPT_MAX characters."""
    s = " ".join(str(text or "").split())
    for _ in range(3):
        s2 = _LEAD.sub("", s)
        if s2 == s:
            break
        s = s2
    m = _CUT.search(s)
    s = (s[:m.start()] if m else s).strip(" .,;:-")
    if len(s) > PROMPT_MAX:
        words = s[:PROMPT_MAX].split(" ")[:-1]
        while words and words[-1].lower() in _TAILWORDS:
            words.pop()
        s = (" ".join(words) if len(" ".join(words)) >= 12 else s[:PROMPT_MAX - 1]).rstrip(" ,;:-") + "…"
    return (s[:1].upper() + s[1:]) if s else ""


# ------------------------------------------------------------------------------ loc
def _resolve(path, type_=None) -> tuple[dict, str]:
    """(loc, option scope) of a path."""
    segs = [s for s in str(path or "").split("\\") if s]
    if len(segs) > 1 and segs[0].lower() == "data":
        segs = segs[1:]
    io_i = next((i for i, s in enumerate(segs) if s in ("Input", "Output")), None)
    head, tail = (segs[:io_i], segs[io_i + 1:]) if io_i is not None else (segs, [])
    io = "out" if io_i is not None and segs[io_i] == "Output" else "in"
    raw = head[0] if head and (head[0] in SECTIONS or io_i is not None or len(head) > 1) else None
    rest = head[1:] if raw else head
    sec, obj, tname, scopes, extra, vars_ok = SECTIONS.get(raw, raw), None, None, [], [], False
    T = _tkey(type_)
    if raw in ("Blocks", "Streams") and rest:
        obj, extra = rest[0], rest[1:]
        if raw == "Blocks":
            tname, scopes, vars_ok = _tname(type_), [s for s in (T, "*") if s], True
        else:
            scopes = ["STREAM"]
    elif raw == "Reactions" and len(rest) >= 2 and rest[0] in ("Reactions", "Chemistry"):
        sec, obj, extra, tname = rest[0], rest[1], rest[2:], (str(type_) if type_ else None)
        scopes = [rest[0].upper()]
    elif raw in ("Flowsheeting Options", "Model Analysis Tools") and len(rest) >= 2:
        obj, extra, tname, scopes = rest[1], rest[2:], rest[0], [rest[0].upper(), raw.upper()]
    elif raw == "Convergence" and len(rest) >= 2 and rest[0] == "Convergence":
        obj, extra, tname, scopes = rest[1], rest[2:], (str(type_) if type_ else None), ["CONVERGENCE"]
    elif raw == "Utilities" and rest:
        obj, extra, tname, scopes = rest[0], rest[1:], (str(type_) if type_ else None), ["UTILITIES"]
    else:
        obj = ARROW.join(rest) or None
        scopes = [raw.upper()] if raw else [s for s in (T, "*") if s]
        vars_ok = not raw
    if io_i is None and extra:                       # e.g. ...\COL1\Ports\WD(OUT: no Input/Output
        tail, extra = extra, []
    if raw == "Streams" and io == "out" and len(tail) > 1 and tail[0] == "STR_MAIN":
        tail = tail[1:]
    code = tail[0] if tail else None
    q = [s for s in tail[1:] if s != "MIXED"]
    loc = {"sec": sec, "obj": obj, "type": tname, "io": io, "field": code, "code": code, "q": q,
           "gl": None, "hint": None, "src": "code"}
    if code:
        F = code.upper()
        hit = next((FIELDS[k] for k in ((s, io, F) for s in scopes) if k in FIELDS), None)
        if hit:
            loc.update(field=hit[0], gl=hit[1], hint=hit[2], src="glossary")
        else:
            lk = f"{scopes[0] if scopes else '*'}|{io}|{F}"
            name = short_prompt(_learned().get(lk) or "")
            if name:
                loc.update(field=name, src="prompt", gl=term(name))
            elif vars_ok:
                v = _labels().get("vars") or {}
                name = short_prompt(v.get(F) or v.get(_fkey(F)) or "")
                if name:
                    loc.update(field=name, src="aspen", gl=term(name))
    return loc, (scopes[0] if scopes else "*")


def _fallback_loc(path, *a, **k) -> dict:
    segs = [{"Output": "Results"}.get(s, s) for s in str(path or "").split("\\") if s and s not in ("Data", "Input")]
    return {"sec": segs[0] if segs else None, "obj": ARROW.join(segs[1:-1]) or None, "type": None, "io": "in",
            "field": segs[-1] if len(segs) > 1 else None, "code": None, "q": [], "gl": None, "hint": None, "src": "code"}


@_safe(_fallback_loc)
def loc(path, type=None) -> dict:  # noqa: A002 -- the plan's name
    """Where `path` is, as words: {"sec", "obj", "type", "io", "field", "code", "q", "gl",
    "hint", "src"}. `type` is the block type (attr 6, e.g. RadFrac) for a block path."""
    return _resolve(path, type)[0]


def _text(lc, form="full", lang="en") -> str:
    lc = lc if isinstance(lc, dict) else {}
    zh, out, field = lang == "zh", lc.get("io") == "out", lc.get("field")
    q = [str(x) for x in lc.get("q") or []]
    short = form == "short"
    notes = ([lc["gl"]] if zh and lc.get("gl") else []) + (["結果"] if zh and out and short else [])
    leaf = str(field) if field else ""
    if leaf and notes:
        leaf += f"（{'，'.join(notes)}）"
    elif leaf and out and short:
        leaf += " (result)"
    leaf = DOT.join([x for x in [leaf] + q if x])
    if short:
        sec, obj = lc.get("sec"), lc.get("obj")
        head = sec if (sec in _UNNAMED or not obj or ARROW in str(obj)) else obj
        parts = [head, leaf]
    else:
        obj = lc.get("obj")
        obj = f"{obj} ({lc['type']})" if obj and lc.get("type") else obj
        parts = [lc.get("sec"), obj, "Results" if out and leaf else None, leaf]
    return ARROW.join(str(p) for p in parts if p).replace("\\", "/")


@_safe(lambda lc, *a, **k: "")
def text(lc, form: str = "full", lang: str = "en") -> str:
    """The loc as one line: "full" Blocks › ESTCOL (RadFrac) › Results › Reboiler duty, "short"
    ESTCOL › Reboiler duty (result). lang "zh" adds the gloss after the field (迴流比) and says
    （結果） instead. A str is taken as a path. Never contains a backslash."""
    return _text(loc(lc) if isinstance(lc, str) else lc, form, lang)


@_safe(lambda path, *a, **k: text(_fallback_loc(path), "short"))
def say(path, type=None, lang: str = "en", form: str = "short") -> str:  # noqa: A002
    """text(loc(path, type), form, lang): 'ESTCOL › Reflux ratio（迴流比）' for a message."""
    return _text(loc(path, type), form, lang)


@_safe(lambda path, *a, **k: str(path or ""))
def named(path, types=None, form: str = "code") -> str:
    """A field for the AI: its short label with the code beside -- "code": FEED › Temperature
    [TEMP\\MIXED], "path": the whole path in the brackets, "label": the words alone. A field no
    label names is already its code (B1 › XYZ_Q · 2). `types` maps block names to types."""
    b = _block_of(path)
    lc = loc(path, _types_map(types).get(b) if b else None)
    text = _text(lc, "short")
    if form != "code":
        return f"{text} [{path}]" if form == "path" else text
    segs = [s for s in str(path or "").split("\\") if s]
    i = next((k for k, s in enumerate(segs) if s in ("Input", "Output")), None)
    code = "\\".join(segs[i + 1:]) if i is not None else ""
    return text if lc.get("src") == "code" or not code else f"{text} [{code}]"


@_safe(lambda paths, *a, **k: {})
def labels(paths, types=None) -> dict:
    """{path: loc} for many paths at once; `types` maps block names to types."""
    tmap = _types_map(types)
    paths = [paths] if isinstance(paths, str) else paths if isinstance(paths, (list, tuple, set)) else []
    out = {}
    try:
        for i, p in enumerate(paths):
            _batch.on = i > 0
            b = _block_of(p)
            out[str(p)] = loc(p, tmap.get(b) if b else None)
    finally:
        _batch.on = False
    return out


def _block_of(path) -> str | None:
    s = [x for x in str(path or "").split("\\") if x]
    return s[2] if len(s) > 2 and s[0].lower() == "data" and s[1] == "Blocks" else None


def _types_map(types) -> dict:
    if isinstance(types, dict):
        return {str(k): v for k, v in types.items()}
    if isinstance(types, (list, tuple)):
        return {str(b.get("name")): b.get("type") for b in types if isinstance(b, dict) and b.get("name")}
    return {}


# ------------------------------------------------------------------------------ options
@_safe(lambda type, field, code, *a, **k: {"code": code, "name": None, "desc": None})
def option(type, field, code) -> dict:  # noqa: A002
    """{"code", "name", "desc"} of an option value: the display name extracted from this Aspen
    (when aspen_strings.MATCH_NAMES) and its one-line description. Unknown codes keep only
    "code". `type` is the block type, or STREAM / COMPONENTS / REACTIONS."""
    T, F, c = _tkey(type), _fkey(field), "" if code is None else str(code)
    out = {"code": code, "name": None, "desc": None}
    codes = ((_labels().get("options") or {}).get(T) or {}).get(F) or {}
    ext = codes.get(c) or next((v for k, v in codes.items() if k.upper() == c.upper()), None)
    if ext and ext[0] and AS.MATCH_NAMES:
        out["name"] = ext[0]
    if ext and len(ext) > 1 and ext[1]:
        out["desc"] = ext[1]
    return out


_SPECIFY = re.compile(r"^specify\s+", re.I)
MEANING_MAX = 52         # characters of an option's meaning made from its description
CHOICES_MAX = 40         # values a field's list offers
# Our words for option codes no extraction names, field by field on every block or stream type
# (the docs list the codes; Aspen's strings give them no name): (English, zh-TW).
_OWN_OPTIONS = {
    "NPHASE": {"1": ("One phase", "單相"), "2": ("Vapor-Liquid", "汽-液"), "3": ("Vapor-Liquid-Liquid", "汽-液-液")},
    "NO_PHASE": {"2": ("Vapor-Liquid", "汽-液"), "3": ("Vapor-Liquid-Liquid", "汽-液-液")},
    "MIXED_SPEC": {"TP": ("Temperature & pressure", "溫度＋壓力"), "TV": ("Temperature & vapor fraction", "溫度＋汽化率"),
                   "PV": ("Pressure & vapor fraction", "壓力＋汽化率")},
}


def _field_of(path, types):
    """(type, field) of an input path: a block's type (``types``), a stream's STREAM; (None, None) else."""
    s = str(path or "").split("\\Input\\", 1)
    if len(s) < 2:
        return None, None
    b = _block_of(path)
    t = _types_map(types).get(b) if b else ("STREAM" if "\\Streams\\" in s[0] else None)
    return t, _fkey(s[1].split("\\")[0])


def _code(v) -> str:
    return str(v).removesuffix(".0") if v is not None else ""


def _words(type_, field, code) -> dict | None:
    """{"en", "zh"?, "desc"?} of one option code (meaning's), or None."""
    o = option(type_, field, code) if type_ else {"name": None, "desc": None}
    name, desc = o.get("name"), o.get("desc")
    if not name and desc:
        d = desc.strip().rstrip(".")
        if len(_SPECIFY.sub("", d)) <= MEANING_MAX and not re.search(r"[;:(]", d):
            name = re.sub(r"\s+and\s+", " & ", _SPECIFY.sub("", d)) if _SPECIFY.match(d) else d
            name, desc = name[:1].upper() + name[1:], None
    own = (_OWN_OPTIONS.get(field) or {}).get(_code(code).upper())
    if not name and own:
        return {"en": own[0], "zh": own[1], **({"desc": desc} if desc else {})}
    if not name:
        return {"desc": desc} if desc else None
    parts = [term(p) or _EN_ZH.get(p.lower()) for p in re.split(r"\s*[,&]\s*", name)]
    out = {"en": name}
    if term(name) or all(parts):
        out["zh"] = term(name) or "＋".join(parts)
    if desc:
        out["desc"] = desc
    return out


@_safe(lambda *a, **k: None)
def meaning(path, value, types=None) -> dict | None:
    """What an input field's option code means, for the inspector to show in its place:
    {"en", "zh"?, "desc"?} -- ``en`` the display name, else the one-line description when short
    ("Specify pressure and duty." -> "Pressure & duty"), else our words (_OWN_OPTIONS), ``zh``
    our words for each of its parts (the glossary's field names, data/terms_zh.json: 壓力＋熱負荷)
    where every part has some, ``desc`` the description where ``en`` is not made from it. None
    for a value that is no option this Aspen's extraction or our words name."""
    t, f = _field_of(path, types)
    if not f or value is None or isinstance(value, bool) or not _code(value).strip() or (isinstance(value, float) and not value.is_integer()):
        return None
    return _words(t, f, _code(value))


@_safe(lambda *a, **k: None)
def choices(path, value, types=None, codes=()) -> list | None:
    """The values an input field takes from a list, for the inspector's menu: the docs' codes
    (``codes``: its Type cell), this Aspen's extraction's (its combo values), our own words'
    (_OWN_OPTIONS, where neither lists any), each {"code", "en"?, "zh"?, "desc"? (where it has no
    name)} (_words); at most CHOICES_MAX. None for a field
    with no list, or one whose value is none of them (a number given with a basis: the docs list
    the bases there)."""
    t, f = _field_of(path, types)
    if not f:
        return None
    ext = ((_labels().get("options") or {}).get(_tkey(t)) or {}).get(f) or {} if t else {}
    seen, out = set(), []
    for c in [*codes, *ext] or list(_OWN_OPTIONS.get(f) or {}):
        c = _code(c)
        if c and c.upper() not in seen:
            seen.add(c.upper())
            w = _words(t, f, c) or {}
            out.append({"code": c, **{k: w[k] for k in ("en", "zh", "desc") if w.get(k) and (k != "desc" or not w.get("en"))}})
    if not out or (value not in (None, "") and _code(value).upper() not in seen):
        return None
    return out[:CHOICES_MAX]


@_safe(lambda key, *a, **k: None)
def header(key) -> str | None:
    """The title of a form sheet in this Aspen (labels.json "headers"); None when not extracted."""
    v = (_labels().get("headers") or {}).get(str(key or ""))
    return v if isinstance(v, str) and v else None


@_safe(lambda form, *a, **k: None)
def form_name(form) -> str | None:
    """A form's title in this Aspen's navigation pane (labels.json "forms"); None when not extracted."""
    v = (_labels().get("forms") or {}).get(str(form or ""))
    return v if isinstance(v, str) and v else None


@_safe(lambda type, *a, **k: str(type or ""))
def type_name(type) -> str:  # noqa: A002
    """A record type's display name (the glossary, then the extraction), else the code."""
    return _tname(type) or ""


# ------------------------------------------------------------------------------ records
def _decorate_one(rec, tmap) -> None:
    tg = rec.get("target") if isinstance(rec, dict) else None
    path = tg.get("path") if isinstance(tg, dict) else None
    if not path:
        return
    b = tg.get("block")
    typ = (tmap.get(b) if b else None) or tg.get("type")
    lc, scope = _resolve(path, typ)
    rec["loc"] = lc
    for side in ("before", "after", "req"):
        d = rec.get(side)
        if not isinstance(d, dict) or "value" not in d:
            continue
        v = d["value"]
        if isinstance(v, str) and lc.get("code"):
            o = option(scope, lc["code"], v)
            if o["name"] and o["name"] != v:
                d["show"] = o["name"]
            if o["desc"]:
                d["tip"] = o["desc"]
        if d.get("trunc") and isinstance(v, str):
            d["show"] = d.get("show", v) + "…"


@_safe(lambda recs, *a, **k: recs)
def decorate(recs, types=None):
    """Journal record(s), in place: "loc" of target.path; before/after/req get "show" -- an
    option code's name, or a truncated value marked with '…' -- and "tip", the option's
    description. `types` maps block names to types ({name: type} or the flowsheet's block
    list); else target.type. Returns what it was given; a record it cannot read is left."""
    tmap = _types_map(types)
    many = isinstance(recs, list)
    try:
        for i, r in enumerate(recs if many else [recs]):
            _batch.on = i > 0
            try:
                _decorate_one(r, tmap)
            except Exception as exc:  # noqa: BLE001
                logger.warning("aspen-labels: record not decorated: %r", exc)
    finally:
        _batch.on = False
    return recs


# ------------------------------------------------------------------------------ learning
@_safe(lambda *a, **k: None)
def learn_key(path, type=None) -> str | None:  # noqa: A002
    """"RADFRAC|in|BASIS_RR" for a field the glossary does not name and nothing was learned for
    yet (learned "" counts: tried): the fields whose attr 19 is worth reading. Else None."""
    lc, scope = _resolve(path, type)
    if not lc.get("code") or lc["src"] == "glossary":
        return None
    key = f"{scope}|{lc['io']}|{lc['code'].upper()}"
    return None if key in _learned() else key


@_safe(lambda *a, **k: {})
def learn_keys(paths, types=None, cap: int | None = None) -> dict:
    """{learn_key: the first of ``paths`` with it} for the fields worth an attr-19 read, at
    most ``cap`` keys; one stat per file for the whole list. ``types`` maps block names to
    types, as for labels()."""
    tmap, out = _types_map(types), {}
    try:
        for i, p in enumerate(paths or ()):
            _batch.on = i > 0
            b = _block_of(p)
            key = learn_key(p, tmap.get(b) if b else None)
            if key and key not in out:
                if cap is not None and len(out) >= cap:
                    break
                out[key] = str(p)
    finally:
        _batch.on = False
    return out


@_safe(lambda *a, **k: {"labels": None, "labels_mtime": None, "learned_mtime": None})
def sources() -> dict:
    """{"labels": labels.json in use or None, "labels_mtime", "learned_mtime"} (None: no
    file): a label the window keeps may read better once either changes."""
    f, learned = _where()

    def mtime(p):
        try:
            return os.stat(p).st_mtime if p else None
        except OSError:
            return None
    return {"labels": str(f) if f else None, "labels_mtime": mtime(f), "learned_mtime": mtime(learned)}


@_safe(lambda *a, **k: 0)
def learn(prompts: dict) -> int:
    """Merge {learn_key: HAP_PROMPT text, "" when there was none} into learned.json (oldest
    dropped past LEARN_MAX; tmp + replace). The server is its only writer; call once per
    batch. Returns how many keys were new."""
    new = {str(k): str(v or "") for k, v in (prompts or {}).items() if k}
    if not new:
        return 0
    p = _learned_path()
    with _lock:
        try:
            cur = _json(p) or {}
        except (OSError, ValueError):
            cur = {}
        fields = cur.get("fields") if isinstance(cur.get("fields"), dict) else {}
        n = sum(1 for k in new if k not in fields)
        fields.update(new)
        while len(fields) > LEARN_MAX:
            fields.pop(next(iter(fields)))
        aspen = AS.status().get("aspen") or p.parent.name
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(json.dumps({"v": 1, "aspen": aspen, "fields": fields}, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, p)
        finally:
            tmp.unlink(missing_ok=True)
        _cache.pop("learned", None)
    return n
