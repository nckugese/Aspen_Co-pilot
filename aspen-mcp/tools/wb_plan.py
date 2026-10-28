"""A block program's plan, checked offline: nothing here reads Aspen, the disk or the clock.

The workbench's "Check" and a proposal's review need to know, before anything runs,
what each step of a program would do to the model as it is *and* as the earlier steps leave it:
a value set on the block the first step places is fine, a stream connected to a port its block
type does not have is not. Everything here works on the program (tools/workbench_tools.py's
normalized statements), the window's flowsheet (``snapshot()``: blocks with their types,
streams with their ends, component labels) and the port table (searcher/block_ports.json):

    active(program)                        the program without its turned-off steps
    outline(program)                       one row per statement: id, n, depth, kind, when (off)
    created(program, flowsheet=None)       {(sid, path): {"created": n} | {"gone": n}} -- the paths
                                           whose block / stream / component an earlier step places
                                           or removes (their existence is not the model's to judge)
    Shadow(flowsheet, ports)               the flowsheet as the steps leave it: names, types, ports
    check(program, flowsheet, ports, lang) outline rows with each step's problems
    view(res, program, held, extra)        check()'s result as tab.check: each step's current
                                           value -> proposed one, the pre-check's problems too
    classes(program)                       what the program does, for the brakes' mode gate
    pause_errors(program, lang)            [(sid, text)]: a step that stops for the user, in a loop
    shape(st)                              the five structure statements' fields (normalize)
    shape_group(st), shape_extra(st)       a group heading's fields; any statement's principle / tech
    groups(program, principles)            the groups a program runs in: its group
                                           headings, else the automatic grouping -- the check's
                                           ``groups`` and a run's pauses by group use the same call
    shadow(program, flowsheet, ports, ...) what the program's top-level structure steps leave the
                                           flowsheet, against what it is now (the
                                           window's preview, tab.check.shadow)

Groups: ``{"do": "group", "title", "why"?, "principle"?}`` is a heading with no
body. A group is the top-level statements from one heading up to the next (or the end); the
heading changes nothing and runs as nothing, so the outline's numbering, a resume by sid, the
breakpoints and the progress are as without it. A program without headings is grouped by
groups()'s own rules (the same for every program, whoever wrote it).

Structure statements (the only ones that change the flowsheet's shape; names, types and ports
only -- a block's settings are set statements):

    {"do": "place",     "block": "H1", "type": "HeatX"}
    {"do": "place",     "stream": "S3B", "type": "MATERIAL"}        type optional: MATERIAL | HEAT | WORK
    {"do": "connect",   "stream": "S3B", "block": "H1", "port": "C(OUT)"}
    {"do": "remove",    "block": "B4"}  |  {"do": "remove", "stream": "S7"}
    {"do": "remove",    "stream": "S3", "block": "B2", "port": "F(IN)"}     disconnect: the stream stays
    {"do": "component", "add": "WATER"}  |  {"do": "component", "remove": "WATER"}
    {"do": "method",    "method": "NRTL"}

Aspen V15's own behaviour the check assumes (seen live): a stream end already on a port,
connected to another port of the same direction, is moved there without an error (a warning, ``moves``) -- except onto the block at the stream's other
end (``loop``: refused, and the refused add has already taken the old end off); the port it is on
already: nothing happens; an occupied single outlet refuses a second stream (connect_stream then
displaces it: ``occupied``); a heat or work stream on a material port and the reverse are refused
(``energy``), and so is a stream type other than MATERIAL / HEAT / WORK; blocks and streams are
separate names; FindNode and port names are exact-case -- a lower-case name of an existing block
crashed V15 through place_block -- so normalize upper-cases names and ports (the table's are). The
tools refuse what V15 would get wrong: a block named like an existing Design-Spec, Calculator,
Transfer or Measurement (it crashed V15; ``clash``) and a component listed already by its label,
alias or databank name, any case (a second WATER became WATER1, unknown to Aspen; ``comp_exists``)
-- the flowsheet's ``flowsheeting`` and ``component_names`` (workbench_tools.taken_names) say which.
Problem levels: error (the run is refused, or would stop there), warn, info (said, not counted).
A problem keeps its words in both of the window's languages, so a check made in one reads right
after the user switches to the other: ``texts`` the main line (the object, then what is wrong),
``help`` the explanation; ``text`` is the explanation in the language it was made in.
"""
from __future__ import annotations

import json

from tools import ids

STRUCTURE =("place", "connect", "remove", "component", "method")
PAUSING = ("yourturn",)                           # a step that stops the run for the user
DESTRUCTIVE = ("remove",)                         # but a disconnect; + component remove, save to a file: classes()
NESTED = ("then", "else", "body")                 # workbench_tools._NESTED
LOOPS = ("repeat", "until", "sweep", "seek")      # workbench_tools._LOOPS
CHANGING = ("set", "run", "sweep", "seek", "optimize", "save")   # brake_effects._CHANGING
STREAM_TYPES = ("MATERIAL", "HEAT", "WORK")
TECH = ("read", "calc", "def", "log", "table", "plot", "pinch")   # technical steps unless "tech" says so
GROUP_TITLE_MAX = 60                              # characters of a group heading's title
GROUPS_MAX = 8                                    # groups (pauses) the automatic grouping makes at most
PRINCIPLES_MAX = 2                                # principle keys a statement keeps
GROUP_OBJS = 20                                   # objects a group lists
_KEY_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")


def key_ok(k) -> bool:
    """A principle library key: lower-case letters, digits and _ (a file name, never a path)."""
    return isinstance(k, str) and bool(k) and set(k) <= _KEY_CHARS
ROWS_MAX = 100                                    # tab.check rows; the rest counted in "more"
TEXT_MAX = 120                                    # characters of a row's value (a path, a name)
PROBLEM_MAX = 240                                 # ... of a problem's text and of each of its facts
ROW_PROBLEMS = 5                                  # problems a tab.check row lists (all are counted)
SHADOW_MAX = 60                                   # objects tab.check.shadow lists, then "more"
LANGS = ("en", "zh")                              # the window's languages: a problem's ``texts``
# Where a step that writes inputs leaves them when nothing is said (workbench_tools._FINISH's first)
FINISH = {"sweep": "restore", "seek": "last", "optimize": "restore"}
PREVIEW = ("set", "sweep", "seek", "optimize", "yourturn")    # the rows view() gives cur (and new)
# Outlets that take several streams (connect adds one more: nothing displaced).
MULTI_OUT = {("FSPLIT", "P(OUT)"), ("SSPLIT", "P(OUT)"), ("SEP", "P(OUT)"), ("SEP2", "P(OUT)"),
             ("MIXER", "WD(OUT)"), ("RADFRAC", "SP(OUT)"), ("MULTIFRAC", "SP(OUT)"), ("PETROFRAC", "SP(OUT)")}
# Heat / work ports by their prefix (a material stream there, or a heat stream elsewhere, is refused).
# (WD is water decant, PS a pseudo-product: material.)
_ENERGY_PORTS = {"HS": "HEAT", "WS": "WORK", "Q-IN": "HEAT", "Q-OUT": "HEAT",
                 "CHS": "HEAT", "RHS": "HEAT", "MHS": "HEAT", "SHS": "HEAT", "PHS": "HEAT"}
COMMON_METHODS = ("IDEAL", "NRTL", "NRTL-RK", "NRTL-HOC", "NRTL-2", "UNIQUAC", "UNIQ-RK", "UNIQ-HOC", "UNIFAC",
                  "UNIF-LL", "UNIF-DMD", "WILSON", "WILS-RK", "WILS-HOC", "PENG-ROB", "PR-BM", "PRWS", "PRMHV2",
                  "RK-SOAVE", "RKS-BM", "RK-ASPEN", "SRK", "SR-POLAR", "CHAO-SEA", "GRAYSON", "BK10", "LK-PLOCK",
                  "STEAM-TA", "STEAMNBS", "IAPWS-95", "ELECNRTL", "ENRTL-RK", "POLYNRTL", "PC-SAFT", "PSRK",
                  "SOLIDS", "COMPS", "BWR-LS", "BWRS", "HYSGLYCO", "CPA", "SRK-KD", "PENG-ROB-KD")

# Problems: (en, zh) with {} fields from the problem's facts.
_TEXT = {
    "exists":       ("{kind} {name} already exists", "{kind_zh} {name} 已經存在"),
    "bad_id":       ("{kind} ID {name} has {why}: an ID takes at most 8 characters, letters, digits and -, and "
                     "Aspen refuses another or cuts it and loses its results. Use {suggest} or another ID that fits",
                     "{kind_zh}名稱 {name} {why_zh}：名稱最多 8 個字元，只能用英文字母、數字和 -，否則 Aspen 會拒絕，"
                     "或截斷後拿不到結果。請改用 {suggest} 或其他合規的名稱"),
    "type_unknown": ("block type {type} is not in the port table: Aspen judges it when this runs",
                     "埠表裡沒有 {type} 這個類型：執行時由 Aspen 判斷"),
    "stream_type":  ("stream type {type} is not MATERIAL, HEAT or WORK: Aspen refuses it",
                     "物流類型 {type} 不是 MATERIAL、HEAT 或 WORK：Aspen 會拒絕"),
    "missing":      ("{kind} {name} does not exist", "{kind_zh} {name} 不存在"),
    "gone":         ("{kind} {name} was removed by step {n}", "{kind_zh} {name} 已在第 {n} 步移除"),
    "port":         ("{type} {block} has no port {port}; its ports: {ports}",
                     "{type} {block} 沒有 {port} 這個埠；可用的埠：{ports}"),
    "occupied":     ("{block} {port} already holds {other}: {other} is taken off and left unconnected",
                     "{block} {port} 已連接 {other}：{other} 將被換下並斷開"),
    "moves":        ("{stream} moves here from {was}", "{stream} 會從 {was} 改接到這裡"),
    "loop":         ("{stream}'s other end is on {block}: Aspen refuses a stream into its own block{off}",
                     "{stream} 的另一端已經接在 {block}：Aspen 不接回同一個單元{off_zh}"),
    "energy":       ("{port} is a {want} port: {stream} is a {have} stream",
                     "{port} 是{want_zh}埠，{stream} 是{have_zh}物流"),
    "same_port":    ("{stream} is on {block} {port} already: nothing changes",
                     "{stream} 已經接在 {block} {port}：不會有變化"),
    "not_on_port":  ("{stream} is not on {block} {port}{where}", "{stream} 沒有接在 {block} {port}{where_zh}"),
    "loose":        ("{name}'s streams stay, unconnected at that end: {streams}",
                     "{name} 的物流保留，該端將斷開：{streams}"),
    "comp_exists":  ("{name} is listed already{listed}: add_component refuses it",
                     "成分清單裡已經有 {name}{listed_zh}：add_component 不會再加一次"),
    "clash":        ("{kind} {name} exists: Aspen crashes on a block named like a Design-Spec, Calculator, "
                     "Transfer or Measurement", "已經有 {kind} {name}：單元名稱與 Design-Spec、Calculator、Transfer、"
                     "Measurement 相同會使 Aspen 當機"),
    "label":        ("{name} is listed as {label}{why}", "{name} 列為 {label}{why_zh}"),
    "comp_missing": ("component {name} is not listed{hint}", "成分清單裡沒有 {name}{hint_zh}"),
    "comp_flows":   ("every stream's input of {name} goes with it", "所有物流中 {name} 的輸入將一併刪除"),
    "method":       ("{method} is not a property method this check knows: Aspen judges it when this runs",
                     "{method} 不是檢查認得的物性方法：執行時由 Aspen 判斷"),
    "in_loop":      ("a flowsheet change cannot sit in a loop ({loop}): each pass would change it again",
                     "流程圖的修改不能放在迴圈裡（{loop}）：每一圈都會再改一次"),
    "in_loop_call": ("procedure {proc} changes the flowsheet and is called in a loop ({loop})",
                     "程序 {proc} 會改流程圖，卻在迴圈裡（{loop}）被呼叫"),
    "yt_in_loop":   ("a manual step cannot sit in a loop ({loop}): each pass would pause again",
                     "手動步驟不能放在迴圈內（{loop}）：每一圈都會再次暫停"),
    "yt_in_loop_call": ("procedure {proc} has a manual step and is called in a loop ({loop})",
                        "程序 {proc} 含手動步驟，不能在迴圈內（{loop}）呼叫"),
    "group_nested": ("a group heading inside an if, a loop or a procedure is ignored: a group heading sits at the "
                     "top level", "群組標題放在 if、迴圈或程序內不生效：群組標題只能放在最上層"),
    "group_title":  ("the group has no title: it is named from its steps", "群組沒有標題：依其步驟自動命名"),
    "group_empty":  ("no step follows this group heading before the next one or the end: put its steps after it, "
                     "or remove it", "此群組標題之後、下一個標題或結尾之前沒有步驟：請把步驟放在標題之後，或移除此標題"),
    "principle_unknown": ("principle {key} is not in the principle library: it is not shown",
                          "原理 {key} 不在原理文庫中：不會顯示"),
}
# The same problems as the window's main line: the object, then what is wrong (en, zh); _TEXT is
# the explanation (``help``).
_SHORT = {
    "exists":       ("{kind} {name}: already exists", "{kind_zh} {name}：已存在"),
    "bad_id":       ("{kind} {name}: ID over 8 characters or invalid, use {suggest}",
                     "{kind_zh} {name}：名稱不合規，建議 {suggest}"),
    "type_unknown": ("{type}: type not in port table", "{type}：埠表無此類型"),
    "stream_type":  ("{type}: invalid stream type", "{type}：物流類型無效"),
    "missing":      ("{kind} {name}: not found", "{kind_zh} {name}：不存在"),
    "gone":         ("{kind} {name}: removed at step {n}", "{kind_zh} {name}：已於第 {n} 步移除"),
    "port":         ("{block}: no port {port}", "{block}：無 {port} 埠"),
    "occupied":     ("{block} {port}: occupied by {other}", "{block} {port}：已接 {other}"),
    "moves":        ("{stream}: moved from {was}", "{stream}：自 {was} 改接"),
    "loop":         ("{stream}: self-loop on {block}", "{stream}：{block} 自身迴路"),
    "energy":       ("{stream}: {have} stream on {want} port {port}", "{stream}：{have_zh}物流接{want_zh}埠 {port}"),
    "same_port":    ("{stream}: already on {block} {port}", "{stream}：已接在 {block} {port}"),
    "not_on_port":  ("{stream}: not on {block} {port}", "{stream}：未接在 {block} {port}"),
    "loose":        ("{name}: streams left unconnected", "{name}：物流將斷開"),
    "comp_exists":  ("{name}: component already listed", "{name}：成分已存在"),
    "clash":        ("{name}: name used by {kind}", "{name}：與 {kind} 同名"),
    "label":        ("{name}: label {label}", "{name}：代號 {label}"),
    "comp_missing": ("{name}: component not listed", "{name}：成分不存在"),
    "comp_flows":   ("{name}: stream inputs removed", "{name}：物流輸入一併刪除"),
    "method":       ("{method}: unknown property method", "{method}：未知物性方法"),
    "in_loop":      ("Flowsheet change in loop ({loop})", "迴圈內修改流程圖（{loop}）"),
    "in_loop_call": ("{proc}: flowsheet change in loop ({loop})", "{proc}：迴圈內修改流程圖（{loop}）"),
    "yt_in_loop":   ("Manual step in loop ({loop})", "迴圈內的手動步驟（{loop}）"),
    "yt_in_loop_call": ("{proc}: manual step in loop ({loop})", "{proc}：迴圈內的手動步驟（{loop}）"),
    "group_nested": ("Group heading not at top level: ignored", "群組標題不在最上層：不生效"),
    "group_title":  ("Group without a title", "群組沒有標題"),
    "group_empty":  ("Group without steps", "群組沒有步驟"),
    "principle_unknown": ("{key}: principle not in library", "{key}：原理不在文庫"),
}
_LEVEL = {"exists": "error", "bad_id": "error", "type_unknown": "warn", "stream_type": "error", "missing": "error", "gone": "error",
          "port": "error", "occupied": "warn", "moves": "warn", "loop": "error", "energy": "error",
          "same_port": "info", "not_on_port": "error", "loose": "warn", "comp_exists": "error", "clash": "error",
          "label": "info", "comp_missing": "error", "comp_flows": "warn", "method": "warn", "in_loop": "error",
          "in_loop_call": "error", "yt_in_loop": "error", "yt_in_loop_call": "error",
          "group_nested": "warn", "group_title": "warn", "group_empty": "warn",
          "principle_unknown": "warn"}
_KIND_ZH = {"block": "單元", "stream": "物流", "component": "成分"}
_ENERGY_ZH = {"HEAT": "熱", "WORK": "功", "MATERIAL": "物質"}


# ---------------------------------------------------------------------------- the statements
def _name(st: dict, key: str) -> str:
    v = st.get(key)
    return "" if v is None else str(v).strip().upper()


def shape(st: dict) -> dict:
    """A structure statement's fields as normalize keeps them: names, types and ports upper-cased
    (a block type as written), the required ones present. ``st`` is changed in place and
    returned. Raises ValueError naming what is missing and the statement's form."""
    do = st.get("do")
    form = {"place": '{"do": "place", "block": "H1", "type": "HeatX"} or {"do": "place", "stream": "S1"}',
            "connect": '{"do": "connect", "stream": "S1", "block": "H1", "port": "H(IN)"}',
            "remove": '{"do": "remove", "block": "B4"}, {"do": "remove", "stream": "S7"} or '
                      '{"do": "remove", "stream": "S3", "block": "B2", "port": "F(IN)"} (disconnect)',
            "component": '{"do": "component", "add": "WATER"} or {"do": "component", "remove": "WATER"}',
            "method": '{"do": "method", "method": "NRTL"}'}[do]

    def bad(what):
        return ValueError(f"{do}: {what}; write it as {form}")

    keys = {"place": ("block", "stream", "type"), "connect": ("stream", "block", "port"),
            "remove": ("block", "stream", "port"), "component": ("add", "remove"), "method": ("method",)}[do]
    vals = {k: _name(st, k) for k in keys}
    if do == "place" and st.get("type") is not None:
        vals["type"] = str(st["type"]).strip() if st.get("block") not in (None, "") else vals["type"]
    for k in keys:
        if vals[k]:
            st[k] = vals[k]
        else:
            st.pop(k, None)
    if do == "place":
        if bool(vals["block"]) == bool(vals["stream"]):
            raise bad("give 'block' or 'stream' (one of them)" if not vals["block"]
                      else "give 'block' or 'stream', not both")
        if vals["block"] and not vals["type"]:
            raise bad(f"'type' is missing (the block type of {vals['block']}, e.g. HeatX)")
    elif do == "connect":
        missing = [k for k in keys if not vals[k]]
        if missing:
            raise bad(" and ".join(f"'{k}'" for k in missing) + (" is" if len(missing) == 1 else " are") + " missing")
    elif do == "remove":
        if vals["port"]:
            missing = [k for k in ("stream", "block") if not vals[k]]
            if missing:
                raise bad(" and ".join(f"'{k}'" for k in missing) + " missing: a disconnect names the stream, "
                          "the block and the port")
        elif bool(vals["block"]) == bool(vals["stream"]):
            raise bad("give 'block' or 'stream'" if not vals["block"] else
                      "'port' is missing (a disconnect), or give only the block or only the stream")
    elif do == "component":
        if bool(vals["add"]) == bool(vals["remove"]):
            raise bad("give 'add' or 'remove' (one of them)")
    elif not vals["method"]:
        raise bad("'method' is missing")
    return st


def shape_group(st: dict) -> dict:
    """A group heading's fields as normalize keeps them: ``title`` on one line, at most
    GROUP_TITLE_MAX characters (none: the check warns group_title and the window names it from
    its steps). A heading has no body: an empty one is dropped, steps in one raise ValueError.
    ``st`` is changed in place and returned."""
    for key in NESTED:
        if st.get(key):
            raise ValueError('group: a heading has no body -- the top-level steps after it, up to the next '
                             'group, are its steps; write it as {"do": "group", "title": "Add the scrubber", '
                             '"why": "..."} followed by its steps')
        st.pop(key, None)
    title = " ".join(str(st.get("title") or "").split())
    if len(title) > GROUP_TITLE_MAX:
        title = title[:GROUP_TITLE_MAX - 1] + "…"
    if title:
        st["title"] = title
    else:
        st.pop("title", None)
    return st


def shape_extra(st: dict) -> dict:
    """Any statement's learning fields as normalize keeps them: ``principle`` a list of at most
    PRINCIPLES_MAX library keys (a string or a list; lower-case letters, digits and _, others
    dropped), ``tech`` only when true (it files the step under the technical ones a group lists
    apart, nothing more). ``st`` is changed in place and returned."""
    v = st.get("principle")
    if isinstance(v, str):
        v = v.split(",")
    keys = []
    for k in v if isinstance(v, (list, tuple)) else ():
        k = str(k).strip().lower()
        if key_ok(k) and k not in keys:
            keys.append(k)
    if keys:
        st["principle"] = keys[:PRINCIPLES_MAX]
    else:
        st.pop("principle", None)
    if st.get("tech") is not True:
        st.pop("tech", None)
    return st


def what(st: dict) -> dict | None:
    """A structure statement's fields for a row (``what``); None for any other statement."""
    do = st.get("do")
    if do not in STRUCTURE:
        return None
    keys = {"place": ("block", "stream", "type"), "connect": ("stream", "block", "port"),
            "remove": ("block", "stream", "port"), "component": ("add", "remove"), "method": ("method",)}[do]
    return {k: _cut(st[k]) for k in keys if st.get(k) not in (None, "")}


def _walk(program):
    for st in program or ():
        if isinstance(st, dict):
            yield st
            for key in NESTED:
                yield from _walk(st.get(key) or [])


def active(program) -> list[dict]:
    """The program without its turned-off steps (``off: true``): what runs. A turned-off loop or
    if takes its body with it. The statements are copies wherever a body lost a step."""
    out = []
    for st in program or ():
        if not isinstance(st, dict) or st.get("off") is True:
            continue
        if any(key in st for key in NESTED):
            st = dict(st)
            for key in NESTED:
                if key in st:
                    st[key] = active(st[key])
        out.append(st)
    return out


def _cut(v, n=TEXT_MAX):
    if isinstance(v, str) and len(v) > n:
        return v[:n - 1] + "…"
    return v


# ---------------------------------------------------------------------------- outline
def outline(program) -> list[dict]:
    """One row per statement in the program's order: {"id", "n" (the top-level steps 1..N; None
    for a nested statement and for a def / proc, which are not steps), "depth", "kind", "when"}
    -- when: "now" (the value is known when it starts), "runtime" (in a loop, in a procedure, or
    an expression), "branch" (in an if's branch) -- or "off": True instead of "when" for a
    turned-off step and everything in it."""
    rows, n = [], 0

    def walk(sts, depth, loop, branch, proc, off):
        nonlocal n
        for st in sts or ():
            if not isinstance(st, dict):
                continue
            do = st.get("do")
            row = {"id": st.get("id"), "n": None, "depth": depth, "kind": do}
            if depth == 0 and do not in ("def", "proc"):
                n += 1
                row["n"] = n
            dead = off or st.get("off") is True
            if dead:
                row["off"] = True
            else:
                row["when"] = ("runtime" if loop or proc or (do == "set" and st.get("expr") not in (None, ""))
                               else "branch" if branch else "now")
            rows.append(row)
            for key in NESTED:
                if key in st:
                    walk(st[key], depth + 1, loop or do in LOOPS, branch or do == "if", proc or do == "proc", dead)
    walk(program, 0, False, False, False, False)
    return rows


# ---------------------------------------------------------------------------- the shadow flowsheet
def _way(port: str) -> str:
    return "from" if str(port).upper().endswith("(OUT)") else "to"


def _energy(port: str) -> str:
    """MATERIAL, HEAT or WORK: what a port takes, by its prefix."""
    return _ENERGY_PORTS.get(str(port).upper().split("(")[0], "MATERIAL")


def short_label(name: str, taken=()) -> str:
    """The label properties_tools.add_component gives a component: the name itself up to 8
    characters, else its first 8 letters and digits; a label listed already gets a number
    (WATER -> WATER1)."""
    name = str(name).strip()
    label = name
    if len(name) > 8:
        label = name.upper().replace(" ", "").replace("-", "").replace(",", "")[:8]
    taken = {str(t).upper() for t in taken}
    if label.upper() in taken:
        base = label[:6] if len(label) > 6 else label
        for i in range(1, 100):
            cand = f"{base}{i}"
            if len(cand) <= 8 and cand.upper() not in taken:
                return cand
    return label


class Shadow:
    """The flowsheet as a program's steps leave it: block types, stream ends (block and port;
    the port None when the flowsheet did not say), component labels. Each ``do_*`` applies one
    structure statement and returns its problems [(code, facts)]; ``made`` / ``gone`` remember the
    step (n) that placed / removed an object: ("block" | "stream" | "component", NAME)."""

    def __init__(self, flowsheet=None, ports=None):
        fs = flowsheet or {}
        self.blocks = {str(b.get("name")).upper(): str(b.get("type") or "") for b in fs.get("blocks") or []
                       if isinstance(b, dict) and b.get("name")}
        self.streams = {}
        for s in fs.get("streams") or []:
            if not isinstance(s, dict) or not s.get("name"):
                continue
            ends = {}
            for way in ("from", "to"):
                if s.get(way):
                    port = s.get(way + "_port")
                    ends[way] = (str(s[way]).upper(), str(port).upper() if port else None)
            typ = str(s["type"]).upper() if s.get("type") else None       # unknown: not judged
            self.streams[str(s["name"]).upper()] = {"type": typ, **ends}
        self.comps = [str(c).upper() for c in fs.get("components") or [] if c]
        # a component's other names add_component refuses (ANAME, DBNAME); None: not read
        names = fs.get("component_names")
        self.names = None if not isinstance(names, dict) else {
            str(lab).upper(): {k: str(v).strip().upper() for k, v in (d or {}).items() if str(v or "").strip()}
            for lab, d in names.items() if isinstance(d, dict)}
        # Design-Spec, Calculator, Transfer, Measurement names, as listed: a block named so crashes V15
        self.rivals = {str(n): kind for kind, lst in (fs.get("flowsheeting") or {}).items() for n in lst or []}
        self.ports: dict[str, list[str]] = {}
        for typ, lst in (ports or {}).items():                 # Mcompr / MCompr: one type
            have = self.ports.setdefault(str(typ).upper(), [])
            have += [str(p) for p in lst or [] if str(p).upper() not in {x.upper() for x in have}]
        self.made: dict = {}
        self.gone: dict = {}

    # -- lookups
    def _obj(self, kind, name):
        """None when the object is there; else the problem: gone (a step removed it) or missing."""
        have = self.blocks if kind == "block" else self.streams
        if name in have:
            return None
        if (kind, name) in self.gone:
            return "gone", {"kind": kind, "name": name, "n": self.gone[(kind, name)]}
        return "missing", {"kind": kind, "name": name}

    def type_ports(self, btype) -> list[str] | None:
        return self.ports.get(str(btype or "").upper())

    def on_port(self, block, port) -> list[str]:
        """The streams on (block, port) as far as known (ends without a port are not counted)."""
        return [s for s, e in self.streams.items() for way in ("from", "to") if e.get(way) == (block, port)]

    def _mark(self, kind, name, n, made=True):
        key = (kind, name)
        if made:
            self.made[key] = n
            self.gone.pop(key, None)
        else:
            self.gone[key] = n
            self.made.pop(key, None)

    def _bad_id(self, kind, name) -> list:
        """A new block or stream ID Aspen refuses or cuts (tools/ids.py): the step is an error,
        and the ID is still placed here so the steps after it are checked as written."""
        why = ids.problem(name)
        if why is None:
            return []
        s = str(name).strip()
        bad = [c for c in dict.fromkeys(s) if not ids.OK.fullmatch(c)]
        why_zh = "、".join(([f"有 {len(s)} 個字元"] if len(s) > ids.MAX else [])
                          + ([f"含{'空格' if bad == [' '] else ' ' + ' '.join(bad[:4])}"] if bad else []))
        taken = self.blocks if kind == "block" else self.streams
        return [("bad_id", {"kind": kind, "name": s, "why": why, "why_zh": why_zh,
                            "suggest": ids.suggest(s, taken, "B" if kind == "block" else "S")})]

    # -- the statements
    def do_place(self, st, n) -> list:
        if st.get("block"):
            name, typ = st["block"], str(st.get("type") or "")
            if name in self.blocks:
                return [("exists", {"kind": "block", "name": name})]
            if name in self.rivals:                        # (the tool's test: the upper-cased name, as listed)
                return [("clash", {"kind": self.rivals[name], "name": name})]
            out = self._bad_id("block", name) + ([] if self.type_ports(typ) is not None or not self.ports else
                                                 [("type_unknown", {"type": typ})])
            self.blocks[name] = typ
            self._mark("block", name, n)
            return out
        name, typ = st["stream"], str(st.get("type") or "MATERIAL").upper()
        if name in self.streams:
            return [("exists", {"kind": "stream", "name": name})]
        out = self._bad_id("stream", name) + ([] if typ in STREAM_TYPES else [("stream_type", {"type": typ})])
        self.streams[name] = {"type": typ}
        self._mark("stream", name, n)
        return out

    def do_connect(self, st, n) -> list:
        stream, block, port = st["stream"], st["block"], st["port"]
        out = [p for p in (self._obj("stream", stream), self._obj("block", block)) if p]
        if out:
            return out
        btype = self.blocks[block]
        known = self.type_ports(btype)
        if known is not None:
            hit = next((p for p in known if p.upper() == port.upper()), None)
            if hit is None:
                return [("port", {"type": btype, "block": block, "port": port, "ports": ", ".join(known)})]
            port = hit.upper()
        s, way = self.streams[stream], _way(port)
        have, want = s.get("type"), _energy(port)
        if known is not None and have in STREAM_TYPES and have != want:
            return [("energy", {"port": port, "want": want, "stream": stream, "have": have})]
        cur, other = s.get(way), s.get("to" if way == "from" else "from")
        if other and other[0] == block:
            at = " ".join(x for x in cur if x) if cur else ""
            return [("loop", {"stream": stream, "block": block, "was": at,
                              "off": f", and takes it off {at} anyway" if at else "",
                              "off_zh": f"，且仍會將其從 {at} 拆下" if at else ""})]
        if cur == (block, port):
            return [("same_port", {"stream": stream, "block": block, "port": port})]
        probs = []
        if cur and not (cur[0] == block and cur[1] is None):          # (a port not known: cannot tell)
            probs.append(("moves", {"stream": stream, "was": " ".join(x for x in cur if x)}))
        if way == "from" and (btype.upper(), port) not in MULTI_OUT:
            for o in self.on_port(block, port):
                if o != stream:
                    probs.append(("occupied", {"block": block, "port": port, "other": o}))
                    self.streams[o].pop("from", None)
        s[way] = (block, port)
        return probs

    def do_remove(self, st, n) -> list:
        if st.get("port"):                                 # disconnect: the stream stays
            stream, block, port = st["stream"], st["block"], st["port"]
            out = [p for p in (self._obj("stream", stream), self._obj("block", block)) if p]
            if out:
                return out
            s, way = self.streams[stream], _way(port)
            cur = s.get(way)
            if not cur or cur[0] != block or (cur[1] is not None and cur[1] != port):
                where = f" (it is on {' '.join(x for x in cur if x)})" if cur else " (that end is free)"
                where_zh = f"（目前接在 {' '.join(x for x in cur if x)}）" if cur else "（該端未連接）"
                return [("not_on_port", {"stream": stream, "block": block, "port": port,
                                         "where": where, "where_zh": where_zh})]
            s.pop(way, None)
            return []
        kind = "block" if st.get("block") else "stream"
        name = st[kind]
        miss = self._obj(kind, name)
        if miss:
            return [miss]
        out = []
        if kind == "block":
            loose = []
            for sname, s in self.streams.items():
                for way in ("from", "to"):
                    if (s.get(way) or (None,))[0] == name:
                        s.pop(way, None)
                        loose.append(sname)
            if loose:
                out.append(("loose", {"name": name, "streams": ", ".join(dict.fromkeys(loose))}))
            del self.blocks[name]
        else:
            del self.streams[name]
        self._mark(kind, name, n, made=False)
        return out

    def listed(self, name):
        """(label, how, name) of the listed component that ``name`` is -- its label, alias (ANAME)
        or databank name (DBNAME), any case: what add_component refuses to add again -- or None.
        Without the names read, a long name whose label is listed is taken as that compound."""
        want = str(name).upper()
        if want in self.comps:
            return want, "label", want
        if self.names is None:
            lab = short_label(name).upper()
            return (lab, "label", lab) if len(want) > 8 and lab in self.comps else None
        return next(((lab, how, v) for lab in self.comps for how, v in (self.names.get(lab) or {}).items()
                     if v == want), None)

    def do_component(self, st, n) -> list:
        if st.get("add"):
            name = st["add"]
            hit = self.listed(name)
            if hit is not None:                             # the tool refuses it (it once made WATER1)
                lab, how, v = hit
                word = {"aname": ("its alias", "別名"), "dbname": ("its databank name", "資料庫名稱")}.get(how)
                listed = "" if lab == name.upper() else f" as {lab}" + (f" ({word[0]} {v})" if word else "")
                listed_zh = "" if lab == name.upper() else f"（列為 {lab}" + (f"，{word[1]} {v}" if word else "") + "）"
                return [("comp_exists", {"name": name, "label": lab, "listed": listed, "listed_zh": listed_zh})]
            label, first = short_label(name, self.comps), short_label(name)
            out = []
            if label.upper() != name.upper():               # a long name: its first 8 letters, numbered if taken
                why, why_zh = (" (longer than 8 characters)", "（超過 8 個字元）") if label == first else \
                    (f" ({first} is another compound's label)", f"（{first} 已經是另一個化合物的代號）")
                out.append(("label", {"name": name, "label": label, "why": why, "why_zh": why_zh}))
            self.comps.append(label.upper())
            if self.names is not None:
                self.names[label.upper()] = {"aname": name.upper()} if label.upper() != name.upper() else {}
            self._mark("component", label.upper(), n)
            return out
        name = st["remove"]
        if name not in self.comps:
            if ("component", name) in self.gone:
                return [("gone", {"kind": "component", "name": name, "n": self.gone[("component", name)]})]
            hit = self.listed(name)                         # remove_component takes the label only
            hint = f" (it is listed by its label {hit[0]})" if hit else ""
            hint_zh = f"（它以代號 {hit[0]} 列出）" if hit else ""
            return [("comp_missing", {"name": name, "hint": hint, "hint_zh": hint_zh})]
        self.comps.remove(name)
        if self.names is not None:
            self.names.pop(name, None)
        self._mark("component", name, n, made=False)
        return [("comp_flows", {"name": name})]

    def do_method(self, st, n) -> list:
        m = st["method"]
        return [] if m in COMMON_METHODS else [("method", {"method": m})]

    def apply(self, st, n) -> list:
        return getattr(self, "do_" + st["do"])(st, n)

    def path_mark(self, path):
        """{"created": n} / {"gone": n} when an earlier step placed / removed the path's block or
        stream, or a component the path ends with; None otherwise."""
        parts = [p for p in str(path or "").split("\\") if p]
        objs = []
        if len(parts) >= 3 and parts[0].lower() == "data" and parts[1].lower() in ("blocks", "streams"):
            objs.append(("block" if parts[1].lower() == "blocks" else "stream", parts[2].upper()))
        if len(parts) >= 4:
            objs.append(("component", parts[-1].upper()))
        for key in objs:
            if key in self.gone:
                return {"gone": self.gone[key], "kind": key[0], "name": key[1]}
        for key in objs:
            if key in self.made:
                return {"created": self.made[key], "kind": key[0], "name": key[1]}
        return None


# ---------------------------------------------------------------------------- the walk
def _paths(st) -> list[str]:
    """The tree paths one statement reads or writes (workbench_tools._paths, one statement)."""
    out = []
    if st.get("path") and st.get("do") != "save":
        out.append(str(st["path"]))
    if isinstance(st.get("left"), dict) and st["left"].get("path"):
        out.append(str(st["left"]["path"]))
    for key in ("variables", "objectives", "constraints"):
        for e in st.get(key) or []:
            if isinstance(e, dict):
                out += [str(e["path"])] if e.get("path") else []
                out += [str(p) for p in (e.get("paths") or {}).values() if p]
    if st.get("do") == "table":
        rows = st.get("rows") or []
        for c in st.get("columns") or []:
            if isinstance(c, dict) and c.get("path"):
                t = str(c["path"])
                out += [t.replace("{row}", str(r)) for r in rows] if rows else [t]
    if st.get("do") == "pinch":
        out += [str(r[k]).strip() for r in st.get("streams") or [] if isinstance(r, dict)
                for k in ("t_in", "t_out", "duty") if str(r.get(k) or "").strip().startswith("\\")]
    return list(dict.fromkeys(out))


class _Walk:
    """The program in the order it runs -- a call runs its procedure's body there, procedures
    nobody calls last -- with the Shadow applying each structure statement. A loop's body is
    walked once. ``n`` is the top-level step a statement runs in (the outline's numbering, the
    turned-off steps counted)."""

    def __init__(self, program, flowsheet, ports, skip=()):
        self.nums = {r["id"]: r["n"] for r in outline(program) if r["n"] is not None}
        self.program = [st for st in active(program) if st.get("id") not in skip]   # (applied before a stop)
        self.shadow = Shadow(flowsheet, ports)
        self.procs = {}
        for st in self.program:
            if st.get("do") == "proc" and st.get("name") not in self.procs:
                self.procs[st.get("name")] = st
        self.probs: dict[str, list] = {}           # sid -> [(code, facts)]
        self.marks: dict = {}                      # (sid, path) -> path_mark (its first run)
        self.called: set = set()

    def add(self, sid, code, facts):
        lst = self.probs.setdefault(sid, [])
        if (code, facts) not in lst:
            lst.append((code, facts))

    def run(self):
        self.block(self.program, None, None, None, ())
        for name, proc in self.procs.items():      # never called: as if called at the end
            if name not in self.called:
                self.block(proc.get("body") or [], None, None, None, (name,))
        return self

    def block(self, sts, n, loop, own, chain):
        """``loop``: the loop this runs in, if any; ``own``: the same, when the loop is in this
        procedure (or the program) itself -- a structure statement there is in_loop, one in a
        procedure a loop calls is the call's in_loop_call."""
        for st in sts:
            do = st.get("do")
            if do in ("def", "proc"):
                continue
            k = self.nums.get(st.get("id")) if n is None else n
            self.one(st, k, own)
            if do == "call":
                name = st.get("name")
                self.called.add(name)
                proc = self.procs.get(name)
                if proc is not None and name not in chain and len(chain) < 20:
                    if loop and any(x.get("do") in STRUCTURE for x in self._reach(proc, (*chain, name))):
                        self.add(st["id"], "in_loop_call", {"proc": name, "loop": loop})
                    if loop and any(x.get("do") in PAUSING for x in self._reach(proc, (*chain, name))):
                        self.add(st["id"], "yt_in_loop_call", {"proc": name, "loop": loop})
                    self.block(proc.get("body") or [], k, loop, None, (*chain, name))
            inner = do if do in LOOPS else None
            for key in NESTED:
                if key in st:
                    self.block(st[key], k, loop or inner, own or inner, chain)

    def _reach(self, proc, chain):
        """Every statement a procedure runs, the procedures it calls included."""
        for st in _walk(proc.get("body") or []):
            yield st
            name = st.get("name") if st.get("do") == "call" else None
            if name in self.procs and name not in chain and len(chain) < 20:
                yield from self._reach(self.procs[name], (*chain, name))

    def one(self, st, n, own):
        sid, do = st.get("id"), st.get("do")
        for path in _paths(st):
            mark = self.shadow.path_mark(path)
            if mark and (sid, path) not in self.marks:
                self.marks[(sid, path)] = mark
                if "gone" in mark:
                    self.add(sid, "gone", {"kind": mark["kind"], "name": mark["name"], "n": mark["gone"]})
        if do in PAUSING and own:
            self.add(sid, "yt_in_loop", {"loop": own})
        if do in STRUCTURE:
            if own:
                self.add(sid, "in_loop", {"loop": own})
            for code, facts in self.shadow.apply(st, n):
                self.add(sid, code, facts)


def created(program, flowsheet=None) -> dict:
    """{(sid, path): {"created": n, ...} | {"gone": n, ...}} for every path a statement reads or
    writes whose block, stream or component an earlier step (n: its top-level step) places or
    removes. Without a flowsheet a place counts as creating what it names."""
    return _Walk(program, flowsheet, None).run().marks


def _text(code, facts, lang, table=None) -> str:
    en, zh = (table or _TEXT)[code]
    f = dict(facts)
    f.setdefault("kind_zh", _KIND_ZH.get(f.get("kind"), f.get("kind")))
    for k in ("want", "have"):
        if k in f:
            f[k + "_zh"] = _ENERGY_ZH.get(f[k], f[k])
    for k in ("where", "off", "hint", "listed", "why"):
        f.setdefault(k + "_zh", f.get(k, ""))
    try:
        return _cut((zh if lang == "zh" else en).format(**f), PROBLEM_MAX)
    except (KeyError, IndexError):
        return code


def problem(code, facts, lang="en") -> dict:
    """One problem as a row carries it: {"level", "code", "text" (the explanation in ``lang``, as
    the run log says it), "texts" ({"en", "zh"}: the window's main line -- the object, then what
    is wrong -- in its own language, whatever it was when the check ran), "help" ({"en", "zh"}:
    the explanation, shown on demand), "facts"}."""
    help_ = {x: _text(code, facts, x) for x in LANGS}
    return {"level": _LEVEL[code], "code": code, "text": help_["zh" if lang == "zh" else "en"],
            "texts": {x: _text(code, facts, x, _SHORT) for x in LANGS}, "help": help_,
            "facts": {k: _cut(v, PROBLEM_MAX) for k, v in facts.items() if not k.endswith("_zh")}}


def shadow(program, flowsheet=None, ports=None, skip=(), gmap=None) -> dict | None:
    """What the program leaves the flowsheet as, against what it is now (the
    window's preview; tab.check.shadow): {"add": {"blocks": [{name, type, g}], "streams": [{name,
    from, from_port, to, to_port, g}]} (a stream's None fields left out), "remove": {"blocks": [{name, g}], "streams":
    [{name, g}]}, "move": [{stream, end ("from" | "to"), was, now ({block, port} | None), g}],
    "more": bool}. Only the top-level place / connect / remove steps that run (turned-off ones and
    ``skip``, the steps a stopped approval applied, left out) are applied, in order, to a Shadow:
    a step in an if, a loop or a procedure is conditional and is not drawn. ``g``: the group
    (``gmap``: a top-level step's n -> its group's n; None without) of the step that last made the
    difference. A stream's end left loose by its block's removal is no move (the removal says it);
    an end whose port was not known moved only when its block did. At most SHADOW_MAX objects,
    in that order ("more": some were left out). None when the steps change nothing drawn."""
    base, s = Shadow(flowsheet, ports), Shadow(flowsheet, ports)
    nums = {r["id"]: r["n"] for r in outline(program) if r["depth"] == 0 and r["n"] is not None}
    touch: dict = {}                                       # (stream, way) -> n of the step that moved that end
    for st in active(program):
        if not isinstance(st, dict) or st.get("id") in skip or st.get("do") not in ("place", "connect", "remove"):
            continue
        n = nums.get(st.get("id"))
        before = {k: (v.get("from"), v.get("to")) for k, v in s.streams.items()}
        s.apply(st, n)
        for k, v in s.streams.items():
            was = before.get(k)
            for i, way in enumerate(("from", "to")):
                if was is not None and was[i] != v.get(way):
                    touch[(k, way)] = n
    gmap = gmap or {}

    def g(n):
        return gmap.get(n) if n is not None else None

    def end(e):
        return {"block": e[0], "port": e[1]} if e else None

    gone = [b for b in base.blocks if b not in s.blocks]
    add_b = [{"name": b, "type": t or None, "g": g(s.made.get(("block", b)))}
             for b, t in s.blocks.items() if b not in base.blocks]
    add_s, move = [], []
    for k, v in s.streams.items():
        if k not in base.streams:
            f, t = v.get("from") or (None, None), v.get("to") or (None, None)
            row = {"name": k, "from": f[0], "from_port": f[1], "to": t[0], "to_port": t[1], "g": g(s.made.get(("stream", k)))}
            add_s.append({x: y for x, y in row.items() if y is not None})     # (a loose end, no group: left out)
            continue
        b = base.streams[k]
        for way in ("from", "to"):
            was, now = b.get(way), v.get(way)
            if was == now or (was and now and was[0] == now[0] and (was[1] is None or now[1] is None)):
                continue
            if now is None and was and was[0] in gone:
                continue
            move.append({"stream": k, "end": way, "was": end(was), "now": end(now), "g": g(touch.get((k, way)))})
    rem_b = [{"name": b, "g": g(s.gone.get(("block", b)))} for b in gone]
    rem_s = [{"name": k, "g": g(s.gone.get(("stream", k)))} for k in base.streams if k not in s.streams]
    if not (add_b or add_s or move or rem_b or rem_s):
        return None
    left, cut = SHADOW_MAX, []
    for lst in (add_b, add_s, move, rem_b, rem_s):
        cut.append(lst[:max(left, 0)])
        left -= len(lst)
    return {"add": {"blocks": cut[0], "streams": cut[1]}, "remove": {"blocks": cut[3], "streams": cut[4]},
            "move": cut[2], "more": left < 0}


def check(program, flowsheet=None, ports=None, lang: str = "en", skip=(), grouping: bool = False,
          principles=None, preview: bool = False, ran=()) -> dict:
    """The offline check: {"ok", "errors", "warns", "steps": rows (at most ROWS_MAX), "more"}.
    A row is outline()'s plus "problems" [problem()], and "what" (a structure statement's
    fields) or "path" (the first path it reads or writes) with "created": n when an earlier step
    places that path's object. Turned-off steps are listed ("off") and not checked; a step that
    only runs in a loop and changes the flowsheet is an error (in_loop), and so is a call in a
    loop of a procedure that does -- and the same for a step that stops for the user (PAUSING).
    ``skip``: top-level sids applied already (a stopped approval that will continue): listed
    ("applied"), neither checked nor walked -- the flowsheet has what they did. ``grouping``:
    also "groups" (groups(), without "ids"), each row's "g" (its group's n;
    a nested row its top-level step's; None in a def / proc), "tech" (true: a technical step)
    and "obj" (the block or stream it acts on, obj_of), and the group problems -- a heading not at
    the top level (group_nested), one without a title (group_title), one with no step that runs
    before the next heading or the end (group_empty), a principle key not in ``principles`` (the
    library's keys; None: not judged, principle_unknown). ``preview``: also
    "shadow" (shadow(): what the top-level structure steps leave drawn, each change by group
    where ``grouping``), left out when they change nothing drawn. ``ran``: top-level sids that
    applied in an earlier run and start turned off (a proposal's ``ran``): a group of them is not
    empty."""
    w = _Walk(program, flowsheet, ports, skip).run()
    index = {st.get("id"): st for st in _walk(program)}
    gs, gof = [], {}
    if grouping:
        gs = groups(program, principles)
        gof = {sid: g["n"] for g in gs for sid in g["ids"] + g["heads"]}
        tops = {st.get("id") for st in program or () if isinstance(st, dict)}
        offs = {st.get("id") for st in program or () if isinstance(st, dict) and st.get("off") is True}
        for g in gs:                                      # a heading with no step that runs after it
            if g["sid"] and all(x in offs for x in g["ids"]) and not any(x in ran for x in g["ids"]):
                w.add(g["sid"], "group_empty", {})
        for st in _walk(active(program)):
            sid = st.get("id")
            if st.get("do") == "group":
                if sid not in tops:
                    w.add(sid, "group_nested", {})
                elif not st.get("title"):
                    w.add(sid, "group_title", {})
            if principles is not None:
                for k in st.get("principle") or ():
                    if k not in principles:
                        w.add(sid, "principle_unknown", {"key": k})
    rows, errors, warns, top = [], 0, 0, None
    for row in outline(program):
        st = index.get(row["id"])
        row = dict(row)
        if grouping:
            if row["depth"] == 0:
                top = row["id"]
            row["g"] = gof.get(top)
            if st is not None and is_tech(st):
                row["tech"] = True
            o = obj_of(st) if st is not None else None
            if o:
                row["obj"] = o
        if row["id"] in skip and row["depth"] == 0:
            row["applied"] = True
        if st is not None:
            desc = what(st)
            if desc is not None:
                row["what"] = desc
            else:
                ps = _paths(st)
                if ps:
                    row["path"] = _cut(ps[0])
                    mark = next((w.marks[(st.get("id"), p)] for p in ps if (st.get("id"), p) in w.marks
                                 and "created" in w.marks[(st.get("id"), p)]), None)
                    if mark:
                        row["created"] = mark["created"]
        if not row.get("off"):
            row["problems"] = [problem(c, f, lang) for c, f in w.probs.get(row["id"], [])]
            errors += sum(p["level"] == "error" for p in row["problems"])
            warns += sum(p["level"] == "warn" for p in row["problems"])
        rows.append(row)
    out = {"ok": errors == 0, "errors": errors, "warns": warns, "steps": rows[:ROWS_MAX],
           "more": max(0, len(rows) - ROWS_MAX)}
    if grouping:
        out["groups"] = [{k: v for k, v in g.items() if k not in ("ids", "heads")} for g in gs[:ROWS_MAX]]
    if preview:
        sh = shadow(program, flowsheet, ports, skip, {n: g["n"] for g in gs for n in g["rows"]})
        if sh is not None:
            out["shadow"] = sh
    return out


def pause_errors(program, lang: str = "en") -> list[tuple[str, str]]:
    """[(sid, text)] of the steps that stop for the user (PAUSING) but would run in a loop -- the
    step itself (yt_in_loop) or a call in a loop of a procedure that has one (yt_in_loop_call) --
    turned-off steps left out; nothing walked when the program has no such step."""
    if not any(st.get("do") in PAUSING for st in _walk(program)):
        return []
    w = _Walk(program, None, None).run()
    return [(sid, _text(c, f, lang)) for sid, probs in w.probs.items() for c, f in probs
            if c in ("yt_in_loop", "yt_in_loop_call")]


def note(code: str, text: str, level: str = "error", texts: dict | None = None, help: dict | None = None,
         **facts) -> dict:
    """A problem only Aspen can tell (the pre-check's: a path not found or not enterable, a unit
    its field does not take, an expression, a name...), as check()'s problems are: ``text`` the
    explanation in the check's language, ``texts`` / ``help`` the main line and the explanation
    in both languages ({"en", "zh"}) when the caller has them."""
    out = {"level": level, "code": code, "text": _cut(" ".join(str(text).split()), PROBLEM_MAX)}
    for key, d in (("texts", texts), ("help", help)):
        if isinstance(d, dict):
            out[key] = {x: _cut(" ".join(str(d[x]).split()), PROBLEM_MAX) for x in LANGS if d.get(x)}
    out["facts"] = {k: _cut(v, TEXT_MAX) for k, v in facts.items() if v is not None}
    return out


def _later(program) -> set:
    """Ids of the statements in a loop's or a procedure's body (any depth): they run later,
    maybe many times -- what the model holds now is not what they start from."""
    out = set()

    def walk(sts, inside):
        for st in sts or ():
            if not isinstance(st, dict):
                continue
            if inside:
                out.add(st.get("id"))
            for key in NESTED:
                if key in st:
                    walk(st[key], inside or st.get("do") in LOOPS or st.get("do") == "proc")
    walk(program, False)
    return out


def _unit(st) -> str | None:
    return _cut(str(st["unit"])) if st.get("unit") else None


def _new(st) -> dict | None:
    """What a set / sweep / seek / optimize row proposes (view's ``new``)."""
    do = st.get("do")
    if do == "set":
        if st.get("expr") not in (None, ""):
            return {"expr": _cut(str(st["expr"])), "unit": _unit(st)}
        return {"value": _cut(st.get("value")), "unit": _unit(st)}
    if do == "sweep":
        return {"from": st.get("from"), "to": st.get("to"), "steps": st.get("steps"), "unit": _unit(st),
                "finish": st.get("finish") or FINISH[do]}
    if do == "seek":
        return {"lower": st.get("lower"), "upper": st.get("upper"), "target": st.get("target"), "unit": _unit(st),
                "finish": st.get("finish") or FINISH[do]}
    if do == "optimize":
        return {"vars": len(st.get("variables") or []), "finish": st.get("finish") or FINISH[do]}
    return None


def view(res: dict, program, held=None, extra=None) -> dict:
    """tab.check: check()'s result (``res``) with each step's current value
    and what it proposes, and the problems only Aspen can tell. A set / sweep / seek / optimize
    row gets ``new`` (_new: a set's {"value", "unit"} or {"expr", "unit"}) and, unless it runs
    in a loop or a procedure (``when`` runtime: it starts from what earlier passes leave),
    ``cur``: ``held(path)`` -- (value, unit) the model holds now, None when the path is not
    there -- as {"value", "unit"}; None when an earlier step places its object (``created``)
    or it cannot be read. ``extra``: {sid: [problem]} (note()), listed after the row's own and
    counted in errors / warns whether its row is listed or not. A row lists ROW_PROBLEMS at most.
    ``res`` is changed in place and returned."""
    index = {st.get("id"): st for st in _walk(program)}
    later = _later(program)
    extra = extra or {}
    for row in res["steps"]:
        st = index.get(row["id"])
        if row.get("off") or st is None:
            continue
        mine = row.get("problems") or []
        row["problems"] = (mine + list(extra.get(row["id"]) or ()))[:ROW_PROBLEMS]
        if st.get("do") not in PREVIEW or row.get("applied"):
            continue
        new = _new(st)
        if new is not None:
            row["new"] = new
        if row["id"] in later or not row.get("path"):
            continue
        got = None if row.get("created") or held is None else held(_paths(st)[0])
        row["cur"] = None if got is None else {"value": _cut(got[0]), "unit": got[1] or None}
    for probs in extra.values():
        res["errors"] += sum(p["level"] == "error" for p in probs)
        res["warns"] += sum(p["level"] == "warn" for p in probs)
    res["ok"] = res["errors"] == 0
    return res


# ---------------------------------------------------------------------------- groups
def is_tech(st: dict) -> bool:
    """A technical step: one the group card counts apart ("2 more steps: read, calc") -- ``tech``
    true, or a read, calc, def, log, table, plot or pinch. Display only: a save, a run or a set
    marked tech still changes the model."""
    return st.get("tech") is True or st.get("do") in TECH


def _path_obj(path) -> str | None:
    parts = [p for p in str(path or "").split("\\") if p]
    if len(parts) >= 3 and parts[0].lower() == "data" and parts[1].lower() in ("blocks", "streams"):
        return ("block:" if parts[1].lower() == "blocks" else "stream:") + parts[2].upper()
    return None


def obj_of(st: dict) -> str | None:
    """The block or stream a statement acts on, "block:NAME" / "stream:NAME": a place or remove its
    object, a connect or disconnect the block it connects; any other statement its first path's
    (a set's, a read's, an optimize's first variable...). None: no block or stream (a run, a log,
    a component, a path elsewhere)."""
    do = st.get("do")
    if do == "place" or (do == "remove" and not st.get("port")):
        return f"block:{st['block']}" if st.get("block") else f"stream:{st['stream']}" if st.get("stream") else None
    if do in ("connect", "remove"):
        return f"block:{st['block']}" if st.get("block") else None
    if do in STRUCTURE or do == "group":
        return None
    ps = _paths(st)
    return _path_obj(ps[0]) if ps else None


def changing(program) -> set:
    """The sids of the top-level statements that change the model -- a value, a run, a save, the
    flowsheet, in their bodies or in the procedures they call (proposals.steps' ``changing``),
    turned-off ones left out."""
    act = active(program)
    procs = {s.get("name"): s for s in _walk(act) if s.get("do") == "proc"}

    def changes(st, seen):
        for x in _walk([st]):
            if x.get("do") in CHANGING or x.get("do") in STRUCTURE:
                return True
            if x.get("do") == "call" and x.get("name") in procs and x["name"] not in seen:
                if changes(procs[x["name"]], seen | {x["name"]}):
                    return True
        return False
    return {s.get("id") for s in act if s.get("do") not in ("def", "proc") and changes(s, frozenset())}


def _follower(st) -> bool:
    """A step that wires what the group around it makes (a connect, a stream placed, a
    disconnect): it joins the group before it."""
    do = st.get("do")
    return do == "connect" or (do == "place" and bool(st.get("stream"))) or (do == "remove" and bool(st.get("port")))


def _content(items) -> list:
    return [e for e in items if not e["tech"] and not e["off"]]


def _single(items, kind) -> bool:
    """A group of one set (one placed block) -- a run beside it aside."""
    c = [e for e in _content(items) if e["st"].get("do") != "run"]
    return len(c) == 1 and c[0]["st"].get("do") == "place" and bool(c[0]["st"].get("block")) \
        if kind == "place" else len(c) == 1 and c[0]["st"].get("do") == kind


def _names_arg(names) -> str:
    return ", ".join(names[:3]) + ("…" if len(names) > 3 else "")


def _auto_title(items) -> dict:
    """An automatic group's name, as the window's template (i18n gc_auto_*) and its arguments:
    the blocks it places (else the streams it places), else the blocks / streams it removes, else
    the one object it sets (gc_auto_set) or how many (gc_auto_sets), else Preparation."""
    c = _content(items)
    placed = [e["st"]["block"] for e in c if e["st"].get("do") == "place" and e["st"].get("block")] or \
        [e["st"]["stream"] for e in c if e["st"].get("do") == "place" and e["st"].get("stream")]
    if placed:
        return {"key": "gc_auto_place", "args": [_names_arg(placed)]}
    gone = [e["st"].get("block") or e["st"].get("stream") for e in c
            if e["st"].get("do") == "remove" and not e["st"].get("port")]
    if gone:
        return {"key": "gc_auto_remove", "args": [_names_arg(gone)]}
    objs = list(dict.fromkeys(e["gobj"] for e in c if e["gobj"]))
    if len(objs) == 1:
        return {"key": "gc_auto_set", "args": [objs[0].split(":", 1)[1]]}
    if objs:
        return {"key": "gc_auto_sets", "args": [len(objs)]}
    return {"key": "gc_auto_prep", "args": []}


def groups(program, principles=None) -> list[dict]:
    """The groups a program runs in, in order: [{"n" (1..), "sid" (the heading's; None for an
    automatic group), "key" (the journal's ``gsid``: the heading's sid, or "~" + the group's first
    step's), "title" (the heading's; None: the window names it from ``tpl`` {"key": an i18n
    gc_auto_* template, "args"}), "auto" (no heading), "why", "principle" [keys -- the heading's,
    else its steps'; only those in ``principles`` when given], "rows" [the top-level steps' n, the
    heading's left out], "ids" [their sids], "heads" [the headings' sids in it], "tech" (how many technical steps run,
    is_tech), "tech_kinds" [their kinds], "objs" [the blocks and streams its other steps act on:
    obj_of, and the streams it wires], "at" (the sid of its first step that changes the model --
    where a run by group pauses; None: it changes nothing)}]. Pure, the same for the check and the
    run (their numbers agree).

    With group headings (top-level, turned on): each heading starts a group. Steps before the
    first one join it when they are all technical (or turned off), else they are a group of their
    own (Preparation). Without: consecutive steps on the same block or stream (obj_of) are one
    group -- a structure step's object being the block it places or connects; a connect, a stream
    placed and a disconnect join the group before them, and so does a step on nothing (a run, an
    if, a call, a save); a set on a stream that group placed or wired stays in it; technical and
    turned-off steps join the next group (the last, at the end). Then consecutive groups of a
    single set are merged (gc_auto_sets), and so are consecutive groups that only place one block
    each (a run among them aside); while more than GROUPS_MAX remain, the group with the fewest
    steps merges into its smaller neighbour. Either way a last group that only runs the
    simulation merges into the one before it (its pause would add nothing)."""
    nums = {r["id"]: r["n"] for r in outline(program) if r["depth"] == 0 and r["n"] is not None}
    chg = changing(program)
    entries = []
    for st in program or ():
        if not isinstance(st, dict) or st.get("id") not in nums:
            continue
        off = st.get("off") is True
        head = st.get("do") == "group" and not off
        do = st.get("do")
        entries.append({"id": st["id"], "n": nums[st["id"]], "st": st, "head": head, "off": off,
                        "tech": not head and (off or do == "group" or is_tech(st)),
                        "gobj": obj_of(st) if do in PREVIEW or do in STRUCTURE else None})
    if not entries:
        return []
    out = []
    if any(e["head"] for e in entries):
        pre, cur = [], None
        for e in entries:
            if e["head"]:
                cur = {"head": e["st"], "items": []}
                out.append(cur)
            elif cur is None:
                pre.append(e)
            else:
                cur["items"].append(e)
        if pre and _content(pre):
            out.insert(0, {"head": None, "items": pre})
        elif pre:
            out[0]["items"][:0] = pre
    else:
        cur, buf = None, []
        for e in entries:
            if e["tech"]:
                buf.append(e)
                continue
            st = e["st"]
            if cur is None or not (_follower(st) or e["gobj"] is None or e["gobj"] in cur["aff"]):
                cur = {"head": None, "items": [], "aff": set()}
                out.append(cur)
            cur["items"] += buf + [e]
            buf = []
            if e["gobj"] and not _follower(st):
                cur["aff"].add(e["gobj"])
            if _follower(st) and st.get("stream"):
                cur["aff"].add("stream:" + st["stream"])
        if buf:
            if cur is None:
                out.append({"head": None, "items": buf})
            else:
                cur["items"] += buf
        for kind in ("set", "place"):                     # runs of one-set / one-placement groups: one
            merged = []
            for g in out:
                one = kind if _single(g["items"], kind) else None
                if merged and one and merged[-1].get("one") == kind:
                    merged[-1]["items"] = merged[-1]["items"] + g["items"]
                    continue
                merged.append(dict(g, one=one))
            out = merged
        while len(out) > GROUPS_MAX:
            i = min(range(len(out)), key=lambda k: (len(out[k]["items"]), k))
            j = i + 1 if i == 0 else i - 1 if i == len(out) - 1 else \
                (i - 1 if len(out[i - 1]["items"]) <= len(out[i + 1]["items"]) else i + 1)
            a, b = min(i, j), max(i, j)
            out[a] = {"head": None, "items": out[a]["items"] + out[b]["items"]}
            del out[b]
    for g in out:
        g["heads"] = [g["head"]["id"]] if g.get("head") is not None else []
    if len(out) > 1:                                      # a last group that only runs: into the one before
        c = _content(out[-1]["items"])
        if c and all(e["st"].get("do") == "run" for e in c):
            out[-2] = dict(out[-2], items=out[-2]["items"] + out[-1]["items"],
                           heads=out[-2]["heads"] + out[-1]["heads"])
            del out[-1]
    res = []
    for k, g in enumerate(out, 1):
        items, head = g["items"], g.get("head")
        runs = [e for e in items if not e["off"]]
        tech = [e for e in runs if e["tech"]]
        objs = []
        for e in _content(items):
            for o in (obj_of(e["st"]), "stream:" + e["st"]["stream"] if _follower(e["st"]) and e["st"].get("stream")
                      else None):
                if o and o not in objs:
                    objs.append(o)
        lib = (lambda ks: [x for x in ks if x in principles]) if principles is not None else list
        own = lib(dict.fromkeys(x for e in _content(items) for x in e["st"].get("principle") or ()))
        if head is not None:                              # (a heading without a key: its steps' keys)
            why, keys = head.get("why"), lib(head.get("principle") or ()) or own
        else:
            why = next((e["st"].get("why") for e in _content(items) if e["st"].get("why")), None)
            keys = own
        title = head.get("title") if head is not None else None
        first = head["id"] if head is not None else (items[0]["id"] if items else None)
        grp = {"n": k, "sid": head["id"] if head is not None else None,
               "key": first if head is not None else "~" + str(first),
               "title": title, "auto": head is None, "why": why, "principle": keys[:PRINCIPLES_MAX],
               "rows": [e["n"] for e in items], "ids": [e["id"] for e in items], "heads": g["heads"],
               "tech": len(tech), "tech_kinds": list(dict.fromkeys(e["st"].get("do") for e in tech)),
               "objs": objs[:GROUP_OBJS], "at": next((e["id"] for e in items if e["id"] in chg), None)}
        if title is None:
            grp["tpl"] = _auto_title(items)
        res.append(grp)
    return res


# ---------------------------------------------------------------------------- the brakes' gate
def classes(program) -> dict:
    """What a program would do when it runs (turned-off steps left out), for the mode gate an AI's
    workbench_run passes: {"writes": it changes the model (a value, a run, a save, the flowsheet),
    "structure": it changes the flowsheet's shape, "destructive": [sid of every remove of a block
    or stream, component removal and save to a file]}. A disconnect (a remove with a port) is not
    one: like the disconnect_stream tool (risk None) it takes nothing away, and a reconnect undoes it."""
    sts = list(_walk(active(program)))
    return {"writes": any(st.get("do") in CHANGING or st.get("do") in STRUCTURE for st in sts),
            "structure": any(st.get("do") in STRUCTURE for st in sts),
            "destructive": [st.get("id") for st in sts
                            if (st.get("do") in DESTRUCTIVE and not (st.get("do") == "remove" and st.get("port")))
                            or (st.get("do") == "component" and st.get("remove"))
                            or (st.get("do") == "save" and str(st.get("path") or "").strip())]}


def size(check_result) -> int:
    """Bytes of a check result as state.json stores it (compact JSON)."""
    return len(json.dumps(check_result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
