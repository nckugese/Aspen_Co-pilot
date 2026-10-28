"""What Aspen still needs before it can run: a cheap COMPSTATUS scan and a per-object diagnosis.

    scan(app)             every object whose COMPSTATUS (attribute 12) carries the incomplete
                          bit 0x40, and every block with a required port left open
    deep(app, path)       one object in detail: the form sheets Aspen marks incomplete and
                          their empty fields (the sheet layer), else its unset / zero-valued
                          fields with their GUI prompts, mode switches, GUI catalog rules; ports
    report(app, ...)      scan + deep for the flagged objects, the one Aspen's Next goes to
                          first; bounded, and stops between objects when asked
    render(report)        check_inputs' text
    refusal_paths(scan)   the paths run_simulation's refusal names
    traps(app, folders)   setups Aspen's input translator rejects though no bit says so
    refresh(app, scan)    read the flagged blocks' inputs the way the GUI does, before trusting
                          their bits (a just-placed block is flagged until then)

The sheet layer (tools/gui_sheets.py; V15 only, else the field walk below): which of the
object's form sheets Aspen's completion flags mark incomplete -- where the GUI's Next goes --
and the fields on each that are empty, enterable and enabled (certainty "unset", source
"sheet", ``sheet`` naming it: empty there, not each of them required). The catalog rules are
not consulted then; a flagged object no sheet accounts for gets the field walk. An object
whose own bit is clear has nothing missing but its ports.

The field walk: only what the server can decide counts as missing (``deep()["missing"]``): a
field an unconditional GUI rule names while it is empty (certainty "required"), and an empty
field (certainty "unset" -- Aspen says the object is incomplete, not which empty field it needs;
scalars come before empty lists). Rules matched by keyword overlap stay in ``candidates``
(certainty "candidate"): a reader checks their conditions. The rules need the catalog read
from the user's own Aspen (tools/gui_rules.py); until it is there ``deep()["rules"]`` is
"loading" or "unavailable", no field is rule-decided, and render() says so.

Either way a port Aspen flags as required and open, a column's operating specs short of the
number its condenser and reboiler call for (``_SPECS``: no form flag names them one by one),
an MCompr knockout stream's phase, and -- nothing else required found -- the components or
the property method object itself are required items. An item's ``rule`` is Aspen's catalog
text (source "rule") or a sentence of this server's own (ports, specs, the components' and
the method's object), which also comes as ``rule_zh``; ``rule_by`` "server" marks the
requirements that are this project's rule, not Aspen's (source "spec"); check_inputs' text
prints those and the components' and the method's item with their ``rule``.

Live V15: a block with an open required port (a Heater with no feed) keeps its own
bit clear; the port node carries 0x40 (an open optional port 0x80), several ports at once when
any one of them will do, and so does \\Data\\Flowsheet. Aspen does not run such a model at all
(CONCHK.4 in the history file, no block executes), so run_simulation refuses it. A fresh RadFrac's Input holds
~1270 nodes, most of them empty lists. The tree is read by one raw Invoke per call (cached
DISPIDs): win32com's attribute access binds every name on every fresh node (FindNode ~1.1 ms,
Elements.Count ~1.1 ms, Name ~0.37 ms, vs ~0.05-0.2 ms). Objects that take no raw call (a
plain Python stand-in) are read through attributes. Stdlib and tools.* only; no I/O at import.
"""
from __future__ import annotations

import logging
import os
import re
import time

from tools import aspen_labels, dispid, flowsheet_tools, gui_rules, gui_sheets, ids, knowledge_tools

logger = logging.getLogger(__name__)

_SCAN_CONTAINERS = [
    "\\Data\\Blocks",
    "\\Data\\Streams",
    "\\Data\\Reactions\\Chemistry",
    "\\Data\\Reactions\\Reactions",
    "\\Data\\Components\\Henry-Comps",
    "\\Data\\Components\\Comp-Groups",
    "\\Data\\Flowsheeting Options\\Balance",
    "\\Data\\Flowsheeting Options\\Calculator",
    "\\Data\\Flowsheeting Options\\Design-Spec",
    "\\Data\\Flowsheeting Options\\Transfer",
    "\\Data\\Model Analysis Tools\\Sensitivity",
    "\\Data\\Model Analysis Tools\\Optimization",
]
_SCAN_SINGLETONS = [
    "\\Data\\Components\\Specifications",
    "\\Data\\Properties\\Specifications",
]
# A child of these costs, the first time anything touches it after a run, as long as an Export:
# Aspen loads its case results then (live V15: 126 s at 20000 cases, 7 s at 5000; FindNode of it
# and Elements.Item alike -- the folder itself, its Count and its own bit take 1-2 ms). The
# folder's own bit carries a child's incomplete flag, so its children are read only when that
# bit is set, and only for a caller that lists them (report: check_inputs); run_simulation's
# refusal names the folder itself.
_HEAVY = frozenset({"\\Data\\Model Analysis Tools\\Sensitivity"})
_FLOWSHEET = "\\Data\\Flowsheet"                  # 0x40 while a required port is open
_BLOCKS = _SCAN_CONTAINERS[0]
_TYPED = (_BLOCKS, "\\Data\\Streams")             # scan() reads the record type of these
INCOMPLETE = 0x40
EMPTY_CAP = 400                                   # check_inputs' walk stops after this many empty fields
LIGHT_CAP = 150                                   # the panel's: a fresh RadFrac 114 ms at 150, 370 ms at 400 (live)
KEEP = {"unset": 40, "zeros": 20, "modes": 20, "missing": 40,   # list lengths kept per object
        "sheets": 8, "fields": 12}
# heat, work and pseudo-stream ports (listed apart from material ones, as hints)
_NON_MATERIAL = re.compile(r"^(?:[A-Z]?HS|WS|PS|Q-IN|Q-OUT)\(", re.IGNORECASE)
_PLAIN = (str, int, float, bool, type(None))


# ----------------------------------------------------------------------------- tree access
_GET, _CALL = 2, 3                               # DISPATCH_PROPERTYGET, | DISPATCH_METHOD
_RAISED = -2147352567                            # DISP_E_EXCEPTION: the member ran and raised
_REFUSED = range(-2147352575, -2147352556)       # DISP_E_*: IDispatch refused the call itself
_IDS: dict = {}                                  # member name -> DISPID (IHNode, IHNodeCol: dual)


class _NoRaw(BaseException):
    """The object takes no raw Invoke by name: redo the whole call through attributes. A
    BaseException, so the walk's ``except Exception`` (a node Aspen will not read) lets it by."""


def _hr(exc):
    hr = getattr(exc, "hresult", None)
    if hr is None and getattr(exc, "args", None) and isinstance(exc.args[0], int):
        hr = exc.args[0]
    return hr


def _rget(ole, name, *args):
    """``ole.<name>(*args)`` as one Invoke by cached DISPID on a raw IDispatch."""
    try:
        d = _IDS.get(name)
        if d is None:
            d = ole.GetIDsOfNames(name)
            d = _IDS[name] = d[0] if isinstance(d, (tuple, list)) else d
        return ole.Invoke(d, 0, _CALL if args else _GET, True, *args)
    except (AttributeError, TypeError) as exc:
        raise _NoRaw(name) from exc
    except Exception as exc:
        hr = _hr(exc)
        if isinstance(hr, int) and hr in _REFUSED and hr != _RAISED:
            _IDS.pop(name, None)
            raise _NoRaw(name) from exc
        raise


class _Raw:
    """Nodes are raw IDispatch objects; every read is one Invoke."""

    @staticmethod
    def root(tree):
        try:
            return tree._oleobj_
        except AttributeError as exc:
            raise _NoRaw("_oleobj_") from exc

    find = staticmethod(lambda tree, path: _rget(tree, "FindNode", path))
    elements = staticmethod(lambda node: _rget(node, "Elements"))
    count = staticmethod(lambda col: _rget(col, "Count"))
    item = staticmethod(lambda col, key: _rget(col, "Item", key))
    name = staticmethod(lambda node: str(_rget(node, "Name")))
    value = staticmethod(lambda node: _rget(node, "Value"))
    attr = staticmethod(lambda node, n: _rget(node, "AttributeValue", n))
    dim = staticmethod(lambda node: _rget(node, "Dimension"))
    rowcount = staticmethod(lambda col, d: _rget(col, "RowCount", d))
    label = staticmethod(lambda col, d, i: _rget(col, "Label", d, i))


class _Attr:
    """Nodes are win32com (or plain Python) objects; values and attributes still go through
    tools/dispid.py, which falls back to the attribute itself."""

    root = staticmethod(lambda tree: tree)
    find = staticmethod(lambda tree, path: tree.FindNode(path))
    elements = staticmethod(lambda node: node.Elements)
    count = staticmethod(lambda col: col.Count)
    item = staticmethod(lambda col, key: col.Item(key))
    name = staticmethod(lambda node: str(dispid.get(node, "Name")))
    value = staticmethod(lambda node: dispid.get(node, "Value"))
    attr = staticmethod(lambda node, n: dispid.get(node, "AttributeValue", n))
    dim = staticmethod(lambda node: dispid.get(node, "Dimension"))
    rowcount = staticmethod(lambda col, d: col.RowCount(d))
    label = staticmethod(lambda col, d, i: col.Label(d, i))


def _both(fn, app, *args, **kw):
    """fn(via, tree, ...) through raw Invokes, else through attributes."""
    tree = app.Tree
    try:
        return fn(_Raw, _Raw.root(tree), *args, **kw)
    except _NoRaw:
        return fn(_Attr, tree, *args, **kw)


def _bit(via, node) -> bool:
    try:
        v = via.attr(node, 12)                    # HAP_COMPSTATUS
        return isinstance(v, int) and bool(v & INCOMPLETE)
    except Exception:
        return False


def _kids(via, node) -> int:
    """How many children; 0 for a leaf (Aspen raises there) or when it cannot be read."""
    try:
        col = via.elements(node)
        n = via.count(col) if col is not None else 0
        return n if isinstance(n, int) else 0
    except Exception:
        return 0


def _record_type(via, node):
    try:
        v = via.attr(node, 6)                     # HAP_RECORDTYPE
    except Exception:
        return None
    return str(v) if v else None


def _open_ports(via, block) -> list[str]:
    """The block's ports Aspen flags incomplete: required and not connected."""
    try:
        col = via.elements(via.item(via.elements(block), "Ports"))
        ports = [via.item(col, j) for j in range(via.count(col))]
        return [via.name(p) for p in ports if _bit(via, p)]
    except Exception:
        return []


# ----------------------------------------------------------------------------- scan
def _object(via, path: str, node, typed: bool) -> dict:
    parts = path.split("\\")
    return {"path": path, "sec": parts[-2], "name": parts[-1],
            "type": _record_type(via, node) if typed else None, "open_ports": [], "ports_only": False}


def _scan(via, tree, ports: bool, heavy: bool = False, trust: bool = False, budget_ms=None) -> dict:
    t0 = time.perf_counter()
    objects, containers, blocks = [], [], []      # blocks: (node, its object or None), Aspen's order
    deadline, cut = None if budget_ms is None else t0 + budget_ms / 1000, False
    for cont in _SCAN_CONTAINERS:
        node = via.find(tree, cont)
        if node is None:
            continue
        flagged = _bit(via, node)
        if flagged:
            containers.append(cont)
        if cont in _HEAVY and not (flagged and heavy):
            continue
        if trust and not flagged and not (ports and cont == _BLOCKS):
            continue
        if deadline is not None and time.perf_counter() > deadline:
            cut = True
            continue
        try:
            col = via.elements(node)
            count = via.count(col)
        except Exception:
            continue
        for i in range(count):
            if deadline is not None and time.perf_counter() > deadline:
                cut = True
                break
            try:
                child = via.item(col, i)
                o = (_object(via, cont + "\\" + via.name(child), child, cont in _TYPED)
                     if _bit(via, child) else None)
            except Exception:
                continue
            if o is not None:
                objects.append(o)
            if cont == _BLOCKS:
                blocks.append((child, o))
    for p in _SCAN_SINGLETONS:
        node = via.find(tree, p)
        if node is not None and _bit(via, node):
            objects.append(_object(via, p, node, False))
    fs = via.find(tree, _FLOWSHEET)
    flowsheet = None if fs is None else _bit(via, fs)
    if flowsheet and ports and deadline is not None and time.perf_counter() > deadline:
        cut = True
    elif flowsheet and ports:
        ordered = []
        for b, o in blocks:
            open_ = _open_ports(via, b)
            if open_ and o is None:
                try:
                    o = _object(via, _BLOCKS + "\\" + via.name(b), b, True)
                    o["ports_only"] = True
                except Exception:
                    o = None
            if o is not None:
                o["open_ports"] = open_
                ordered.append(o)
        objects = ordered + [o for o in objects if not o["path"].startswith(_BLOCKS + "\\")]
    sc = {"t": time.time(), "scan_ms": 0.0, "objects": objects, "containers": containers,
          "flowsheet": flowsheet}
    sc["complete"] = not objects and not containers and not flowsheet
    sc["runnable"] = not refusal_paths(sc)
    if deadline is not None:
        sc["cut"] = cut
    sc["scan_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return sc


def scan(app, ports: bool = False, heavy: bool = False, trust: bool = False, budget_ms=None) -> dict:
    """The flagged objects (children of the containers, then the singletons), the containers
    whose own bit is set, and ``flowsheet``: \\Data\\Flowsheet's bit (None: no such node).
    With ``ports`` and that bit set, every block's ports are read too (~2 ms a block live): a
    block with an open required port gets ``open_ports``, and is listed ``ports_only`` when its
    own bit is clear. The children of a _HEAVY folder (Sensitivity) are read only with
    ``heavy`` and the folder's own bit set -- never otherwise: after a run the first touch of
    one costs as long as an Export. ``complete``: nothing flagged at all; ``runnable``:
    run_simulation would start (open required ports count only when read: ``ports``). Without ``ports``: 15 FindNode + one read per object, ~7-13 ms
    live (a 23-block model ~32 ms). ``trust``: a container whose own bit is clear is not opened
    -- V15 sets it whenever a child's is (checked live on several models and a blank one through
    placing, specifying, clearing and removing; the 23-block model ~5 ms); the Blocks
    container still is with ``ports``. The workbench's automatic scan trusts; check_inputs,
    run_simulation and the panel's own check do not. ``budget_ms`` (with ``trust`` only): no
    more children or ports are read once it is spent (``cut``); the containers' own bits, the
    singletons and \\Data\\Flowsheet still are, so ``complete`` stays exact."""
    return _both(_scan, app, ports, heavy, trust, budget_ms)


def refusal_paths(sc: dict) -> list[str]:
    """What run_simulation names: the flagged children of each container, the container itself
    when its own bit is set and none of them is listed (a _HEAVY folder, a ``cut`` scan),
    and the blocks with an open required port (``ports_only`` too: Aspen runs none of the model
    then). The root \\Data is never read -- its COMPSTATUS goes stale after edits (e.g. an
    auto-created empty Comp-Groups\\MIXED) and would block models the GUI runs."""
    paths = [o["path"] for o in sc["objects"]]
    out = []
    for cont in _SCAN_CONTAINERS:
        pre = cont + "\\"
        kids = [p for p in paths if p.startswith(pre) and "\\" not in p[len(pre):]]
        out.extend(kids or ([cont] if cont in sc["containers"] else []))
    out.extend(p for p in paths if p in _SCAN_SINGLETONS)
    return out


def refusal_names(sc: dict) -> list[str]:
    """refusal_paths, a block with an open required port followed by it: "\\Data\\Blocks\\H2
    (open required port F(IN))" (several: joined by "/")."""
    ports = {o["path"]: o["open_ports"] for o in sc["objects"] if o.get("open_ports")}
    return [p + (f" (open required port{'s' if len(ports[p]) > 1 else ''} {'/'.join(ports[p])})"
                 if p in ports else "") for p in refusal_paths(sc)]


# ----------------------------------------------------------------------------- traps
# Setups whose COMPSTATUS is clear but which the V15 input translator rejects, so the run never
# starts (live V15; the history file's code in brackets).
_ID_OK = ids.OK                                  # _ . @ % ~ rejected (NXTITM.1, BLDITM.9)
_PROCESS = "\\Data\\EO Configuration\\Solve-Options\\Input\\PROCESS"
_PROP_SETS = "\\Data\\Properties\\Prop-Sets\\"


def _values(via, tree, path: str) -> list:
    node = via.find(tree, path)
    if node is None:
        return []
    col = via.elements(node)
    return [via.value(via.item(col, i)) for i in range(via.count(col))]


def _cfg_name(name: str) -> str:
    return name if os.path.splitext(name)[1] else name + ".cfg"


def _cfg_found(name: str, folders, cfg_dir: str = "") -> bool:
    """Whether USER3's configuration file ``name`` is where the engine looks: ``cfg_dir``
    (CFG_DIR_WNT, put in front of the name as it stands: a relative one from the run folder, one
    without its trailing backslash finds nothing), then the run folder and ..\\APINIT beside it
    (V15's own message lists both; live, the run folder is searched even with CFG_DIR_WNT set)."""
    name = _cfg_name(name)
    if os.path.isabs(name):
        return os.path.isfile(name)
    subs = ([cfg_dir + name] if cfg_dir else []) + [name, os.path.join("..\\APINIT", name)]
    return any(os.path.isfile(os.path.join(f, sub)) for f in folders for sub in subs)


def _traps(via, tree, folders) -> list[str]:
    out, process = [], None
    for cont in _TYPED:
        node = via.find(tree, cont)
        if node is None:
            continue
        col = via.elements(node)
        kids = [via.item(col, i) for i in range(via.count(col))]
        bad = [n for n in (via.name(k) for k in kids) if not _ID_OK.fullmatch(n)]
        if bad:
            out.append(f"{cont}: {'/'.join(bad)} -- an ID takes letters, digits and - + # $ only (NXTITM.1)")
        if cont != _BLOCKS:
            continue
        for k in kids:
            name, typ = via.name(k), str(_record_type(via, k) or "").upper()
            path = f"{_BLOCKS}\\{name}"
            if typ == "ANALYZER":
                for ps in _values(via, tree, path + "\\Input\\PSETNAME"):
                    node = via.find(tree, f"{_PROP_SETS}{ps}\\Input\\UNITS") if ps else None
                    n = _kids(via, node) if node is not None else 0
                    if n > 1:
                        out.append(f"{path}: prop-set {ps} holds {n} properties; an Analyzer takes one per "
                                   "prop-set (ZUSPAN.2)")
            elif typ == "USER3" and folders:
                cfg = _node_value(via, tree, path + "\\Input\\CFGNAM")[1]
                cfg = "" if cfg is Ellipsis else str(cfg or "").strip()
                cdir = _node_value(via, tree, path + "\\Input\\CFG_DIR_WNT")[1]
                cdir = "" if cdir is Ellipsis else str(cdir or "").strip()
                if cfg and not _cfg_found(cfg, folders, cdir):
                    out.append(f"{path}: configuration file {_cfg_name(cfg)} not found in "
                               f"{' or '.join(([cdir] if cdir else []) + folders)} (U3ERRR.1)")
            elif typ == "BATCHOP":
                if process is None:
                    v = _node_value(via, tree, _PROCESS)[1]
                    process = "" if v is Ellipsis else str(v or "").upper()
                if process and process != "BATCH":
                    out.append(f"{path}: a BatchOp needs a batch flowsheet; set {_PROCESS} to BATCH (ATLOOK.1)")
    return out


def traps(app, folders=()) -> list[str]:
    """Setups no COMPSTATUS bit flags that the input translator rejects, one sentence each naming
    the object: a block or stream ID with a character other than letters, digits, - + # $; an
    Analyzer whose PSETNAME prop-set holds more than one property; a USER3 whose configuration
    file is neither in its CFG_DIR_WNT nor in ``folders`` (the model's folder: checked only when
    given); a BatchOp while
    the flowsheet's process type is not BATCH. [] when none, or when the tree cannot be read."""
    try:
        return _both(_traps, app, list(folders))
    except Exception:
        logger.debug("inputs_check: traps not read", exc_info=True)
        return []


REFRESH_MS = 3000                                # refresh()'s budget
REFRESH_READS = 30                                # Input values read per block at most


def _child_names(via, tree, path: str, limit: int | None = None) -> list[str]:
    node = via.find(tree, path)
    if node is None:
        return []
    col = via.elements(node)
    n = via.count(col)
    return [via.name(via.item(col, i)) for i in range(n if limit is None else min(n, limit))]


def refresh(app, sc: dict, budget_ms: float = REFRESH_MS, reads: int = REFRESH_READS) -> bool:
    """Read the top-level Input values of each block ``sc`` flags through win32com's late-bound
    attributes (``app.Tree.FindNode(p).Value``), as a GUI form does, each followed by the block's
    own COMPSTATUS read the same way, until that clears (``reads`` at most); True when a
    block cleared (scan again). Live V15: a block placed and connected but never
    written keeps 0x40 -- Aspen counts it as having no input yet -- and the raw Invokes this module
    reads with leave it so; a fresh MIXER, DUPL or CLCHNG cleared after the first read (~3 ms),
    a HEATER with no TEMP/PRES stays flagged after every value is read. Stops once ``budget_ms``
    is spent or on Aspen's internal fault."""
    blocks = [o["path"] for o in sc["objects"]
              if o["path"].startswith(_BLOCKS + "\\") and not o.get("ports_only")]
    deadline = time.perf_counter() + budget_ms / 1000
    tree, cleared = app.Tree, False
    for path in blocks:
        base = path + "\\Input"
        try:
            names = _both(_child_names, app, base, reads)
        except Exception:
            continue
        for name in names[:reads]:
            if time.perf_counter() > deadline:
                return cleared
            try:
                node = tree.FindNode(base + "\\" + name)
                if node is not None:
                    node.Value
                v = tree.FindNode(path).AttributeValue(12)
            except Exception as exc:
                if knowledge_tools.server_fault(exc):
                    return cleared
                continue
            if isinstance(v, int) and not v & INCOMPLETE:
                cleared = True
                break
    return cleared


# ----------------------------------------------------------------------------- deep
_DIAG_EXACT_FIELDS = {"TEMP", "PRES", "DUTY", "VFRAC", "FLOW", "TOTFLOW",
                      "NSTAGE", "BASIS", "VALUE", "CID", "DELP", "POWER", "RR",
                      "PRATIO", "EFF", "MOLE-FLOW", "MASS-FLOW"}


def _diag_rank(label: str) -> int:
    """0 = spec/option selector, 1 = primary spec field, 2 = the rest."""
    head = label.split("\\")[0]
    if "OPT" in head or "SPEC" in head:
        return 0
    if head in _DIAG_EXACT_FIELDS:
        return 1
    return 2


_DIAG_SKIP_PREFIXES = ("PSV", "EO_", "FV", "IV", "SG_", "SC_", "AUTO_", "NEG_",
                       "SPC_", "USER", "GLOBAL", "LOCAL", "INIT_")
_DIAG_SKIP_NAMES = {
    "Unit Set", "User Table", "User Tree", "COORD", "DESCRIPTION", "COMMENT",
    "HEADING", "ADDINPUT", "LINES", "LISTS", "FILE", "EMBEDDED", "ENABLED",
    "SSXML", "HCURVE_DESCR", "IDESCRIPTION", "IDETAILS", "NEWPAGE", "WIDE",
    "FORMSCALE", "SHOWASICON", "INTERACTIVE", "RAMPED", "THRU", "INCR",
    "INDEP_VAR", "REPORT", "INPUT", "RESULTS", "RESTART", "SBWEIGHT", "MEIN",
    "MEOUT", "HIERARCHY", "HIGH_PREC", "ON_SMEO_DIFF", "OPT_RANGE", "UOM",
    "PHYS_QTY", "V_IN", "V_OUT", "NPOINTS", "TEXT", "P_EST", "T_EST",
}


def _prompt(via, node) -> str:
    """The field's GUI prompt text (HAP_PROMPT), cleaned for display."""
    try:
        prompt = str(via.attr(node, 19) or "")
    except Exception:
        return ""
    return prompt.replace("Lets you type the", "").replace(
        "Lets you type", "").strip().rstrip(".")


def _kind(via, node):
    """'value' for a scalar, 'list' for an empty list node (no rows yet), None if unknown."""
    try:
        d = via.dim(node)
    except Exception:
        return None
    return None if not isinstance(d, int) else "value" if d == 0 else "list"


def _plain(v):
    return v if isinstance(v, _PLAIN) else str(v)


def _walk_fields(via, root, cap, deadline, empty, zeros, modes, strvals, filled) -> bool:
    """The object's Input fields, depth <= 2; False when ``deadline`` cut the walk short. A child
    Aspen will not hand over is passed by -- unless it raised Aspen's internal fault
    (knowledge_tools.server_fault: Item(i) on some label-keyed tables, V15), which ends the walk:
    raised, not met again for every row."""
    def walk(node, prefix, depth):
        try:
            col = via.elements(node)
            count = via.count(col)
        except Exception:
            return True
        for i in range(count):
            if len(empty) >= cap:
                return True
            if deadline is not None and time.perf_counter() > deadline:
                return False
            try:
                child = via.item(col, i)
                name = via.name(child)
            except Exception as exc:
                if knowledge_tools.server_fault(exc):
                    raise
                continue
            if name in _DIAG_SKIP_NAMES or any(name.startswith(p) for p in _DIAG_SKIP_PREFIXES):
                continue
            label = f"{prefix}{name}"
            if _kids(via, child) > 0 and depth < 2:
                if not walk(child, label + "\\", depth + 1):
                    return False
                continue
            try:
                val = via.value(child)
            except Exception:
                continue
            if val is None or val == "":
                empty.append((label, child))
                continue
            if isinstance(val, str):
                if len(strvals) < 40:
                    strvals.append(val)
            elif not isinstance(val, bool) and val == 0:
                zeros.append((label, child, val))
            if any(k in name for k in ("OPT", "SPEC", "TYPE", "BASIS")):
                modes.append((label, val))
            elif len(filled) < 10:
                filled.append(child)
        return True

    return walk(root, "", 0)


def _ports(via, tree, path: str):
    """Connections of a top-level block against the port catalog, plus the ports Aspen flags
    as required and open; None for other objects."""
    m = re.fullmatch(r"\\Data\\Blocks\\([^\\]+)", path)
    if not m:
        return None
    block_name = m.group(1)
    conn = via.find(tree, rf"\Data\Blocks\{block_name}\Connections")
    connected = {}                              # port -> every stream on it (two feeds on a Mixer's F(IN))
    if conn is not None:
        col = via.elements(conn)
        for j in range(via.count(col)):
            elem = via.item(col, j)
            connected.setdefault(str(via.value(elem)), []).append(via.name(elem))
    block_type, node = "", None
    try:
        node = via.find(tree, rf"\Data\Blocks\{block_name}")
        block_type = str(via.attr(node, 6) or "")  # RECORDTYPE
    except Exception:
        pass
    all_ports = flowsheet_tools.ports_for(block_type)
    material = [p for p in all_ports if not _NON_MATERIAL.match(p)]
    on = {p.upper() for p in connected}
    return {"type": block_type or None, "catalog": bool(all_ports), "connected": connected,
            "unconnected": [p for p in all_ports if p.upper() not in on],
            "required_open": _open_ports(via, node) if node is not None else [],
            "open_in": [p for p in material if p.upper() not in on and p.upper().endswith("(IN)")],
            "open_out": [p for p in material if p.upper() not in on and p.upper().endswith("(OUT)")],
            "material_only": True}


# Operating specs by block type (upper case): any of ``fields`` holding a value is one; the number
# needed is 2 less one for each of ``ends`` set to NONE (V15's RadFrac catalog: a column takes
# two operating specs in all, and setting the condenser or the reboiler to None uses up one of
# them). No catalog rule names them one by one ("X must be specified"), so without this a
# RadFrac with its setup filled and no spec would show nothing required. The
# items name the GUI's own default pair first (Distillate rate, Reflux ratio; with no condenser
# Bottoms rate, Boilup ratio), then the others in ``fields`` order. T1 and BASIS_RDV (condenser
# temperature, distillate vapor fraction) count when set but are never asked for: a spec not
# known to count leaves the block reported as before, never a spec it does not need.
_SPECS = {
    "RADFRAC": {"fields": ("BASIS_D", "BASIS_RR", "BASIS_B", "BASIS_BR", "BASIS_VN", "BASIS_L1", "D:F", "B:F",
                           "Q1", "QN"),
                "extra": ("T1", "BASIS_RDV"), "ends": ("CONDENSER", "REBOILER"),
                "no_top": ("BASIS_B", "BASIS_BR"), "sheet": "Setup | Configuration sheet",
                "sheet_zh": "Setup | Configuration 頁",
                "gui": {"BASIS_D": "Distillate rate", "BASIS_RR": "Reflux ratio", "BASIS_B": "Bottoms rate",
                        "BASIS_BR": "Boilup ratio", "BASIS_VN": "Boilup rate", "BASIS_L1": "Reflux rate",
                        "D:F": "Distillate to feed ratio", "B:F": "Bottoms to feed ratio", "Q1": "Condenser duty",
                        "QN": "Reboiler duty", "T1": "Condenser temperature",
                        "BASIS_RDV": "Distillate vapor fraction"}},
}
# Nothing required found in these objects: the object itself is the item, with Aspen's place.
# (kind, noun, probe, none defined, still incomplete, and those two in zh-TW)
_OBJECT_ITEMS = {
    "\\Data\\Components\\Specifications": ("components", "Components", "Input\\TYPE",
                                            "No components defined", "Component input incomplete",
                                            "尚未定義成分", "成分輸入不完整"),
    "\\Data\\Properties\\Specifications": ("method", "Property method", "Input\\GBASEOPSET",
                                            "No property method selected", "Property method input incomplete",
                                            "尚未選擇物性方法", "物性方法輸入不完整"),
}
# A port item's own sentence in zh-TW: the direction's noun (inlet, outlet, port).
_PORT_ZH = {"(IN)": "入口", "(OUT)": "出口", None: "埠"}


def _guarded(fn, default):
    """``fn()``; ``default`` when it fails -- but Aspen's internal fault, which ends the look."""
    try:
        return fn()
    except Exception as exc:
        if knowledge_tools.server_fault(exc):
            raise
        logger.debug("inputs_check: %r failed (%r)", fn, exc)
        return default


def _node_value(via, tree, path):
    """(found, value) of one node; (True, Ellipsis) when it is there but unreadable -- Aspen's
    internal fault is raised."""
    node = via.find(tree, path)
    if node is None:
        return False, None
    try:
        return True, via.value(node)
    except Exception as exc:
        if knowledge_tools.server_fault(exc):
            raise
        return True, Ellipsis


def _empty(v) -> bool:
    return v is None or v == ""


def _count(via, node) -> int:
    """How many children, as ``_kids`` -- 0 for a leaf, Aspen raising there (an empty table, live
    V15) -- but Aspen's internal fault is raised."""
    try:
        n = via.count(via.elements(node))
        return n if isinstance(n, int) else 0
    except Exception as exc:
        if knowledge_tools.server_fault(exc):
            raise
        return 0


def _spec_items(via, tree, path: str, typ, unset) -> list[dict]:
    """The operating specs a block is short of (``_SPECS``), as required items (source "spec"):
    one field each, the suggested ones first; [] when it has enough, or when a spec or an end
    could not be read (then nothing is claimed). The count is this project's rule, not a catalog
    one: ``rule_by`` "server", its sentence in ``rule`` (en) and ``rule_zh``."""
    fam = _SPECS.get(str(typ or "").upper())
    if fam is None:
        return []
    base = path + "\\Input\\"
    none = []                                     # the ends set to NONE
    for end in fam["ends"]:
        found, v = _node_value(via, tree, base + end)
        if v is Ellipsis:
            return []
        if found and str(v or "").strip().upper() == "NONE":
            none.append(end)
    have, free = [], []
    for name in fam["fields"] + fam["extra"]:
        found, v = _node_value(via, tree, base + name)
        if v is Ellipsis:
            return []
        if found and not _empty(v):
            have.append(name)
        elif found and name in fam["fields"]:
            free.append(name)
    need = 2 - len(none)
    short = need - len(have)
    if short <= 0:
        return []
    first = list(fam["no_top"] if fam["ends"][0] in none else fam["fields"][:2])
    order = [n for n in first if n in free] + [n for n in free if n not in first]
    prompts = {u["field"]: u["prompt"] for u in unset}
    names = [fam["gui"].get(n, n) for n in have]
    given = f"{len(have)} given: {', '.join(names)}" if have else "none given"
    rule = f"{need} operating specification{'s' if need != 1 else ''} required, {given} ({fam['sheet']})"
    given_zh = f"已指定 {len(have)} 個：{'、'.join(names)}" if have else "目前未指定"
    rule_zh = f"需要 {need} 個操作規格，{given_zh}（{fam['sheet_zh']}）"
    out = []
    for name in order[:short]:
        prompt = prompts.get(name)
        if prompt is None:
            node = via.find(tree, base + name)
            prompt = _prompt(via, node) if node is not None else ""
        out.append({"field": name, "path": base + name, "prompt": prompt, "rank": 0, "kind": "value",
                    "certainty": "required", "source": "spec", "rule": rule, "rule_zh": rule_zh,
                    "rule_by": "server"})
    return out


def _knockout_items(via, tree, path: str, typ) -> list[dict]:
    """An MCompr's knockout streams (on LK(OUT)) with no phase (PROD_PHASE\\<stream>), as required
    items (source "spec"). Live V15: the block keeps 0x40 until each has one, and the
    field walk's GUI rules name FLOW, HEAD, POWER, DUTY instead (the sheet layer does not)."""
    if str(typ or "").upper() != "MCOMPR":
        return []
    conn = via.find(tree, path + "\\Connections")
    if conn is None:
        return []
    col = via.elements(conn)
    lk = [via.name(e) for e in (via.item(col, j) for j in range(via.count(col)))
          if str(via.value(e)).upper() == "LK(OUT)"]
    out = []
    for s in lk:
        field = "PROD_PHASE\\" + s
        found, v = _node_value(via, tree, path + "\\Input\\" + field)
        if found and v is not Ellipsis and _empty(v):
            out.append({"field": field, "path": path + "\\Input\\" + field, "prompt": "", "rank": 0, "kind": "value",
                        "certainty": "required", "source": "spec", "rule_by": "server",
                        "rule": f"knockout stream {s} on LK(OUT) has no phase; set L (with free water, one L1 "
                                "and one W stream per stage)",
                        "rule_zh": f"分液物流 {s}（LK(OUT)）未指定相態；設 L（有游離水時每段一條 L1、一條 W）"})
    return out


def _object_item(via, tree, path: str) -> dict | None:
    """The components' or the property method's object as one required item (``_OBJECT_ITEMS``):
    ``kind`` components | method, ``source`` empty (none defined: no component, no base method)
    or object (defined, still incomplete), ``rule`` saying so with Aspen's place."""
    spec = _OBJECT_ITEMS.get(path)
    if spec is None:
        return None
    kind, noun, probe, none, some, none_zh, some_zh = spec
    node = via.find(tree, path + "\\" + probe)
    if kind == "components":
        empty = node is None or _count(via, node) == 0
    else:
        empty = node is None or _empty(_node_value(via, tree, path + "\\" + probe)[1])
    place = "Components › Specifications" if kind == "components" else "Methods › Specifications"
    return {"field": None, "path": path, "prompt": noun, "rank": 0, "kind": kind, "certainty": "required",
            "source": "empty" if empty else "object", "rule": f"{none if empty else some} ({place})",
            "rule_zh": f"{none_zh if empty else some_zh}（{place}）"}


def _port_items(path, ports) -> list[dict]:
    """Flagged ports as required items, one per direction: Aspen flags every port that would do
    (a heat splitter: P, HS, WS, PS(OUT))."""
    out = []
    flagged = (ports or {}).get("required_open", [])
    for direction, what in (("(IN)", "an inlet"), ("(OUT)", "an outlet"), (None, "a port")):
        group = [p for p in flagged if (p.upper().endswith(direction) if direction
                                        else not p.upper().endswith(("(IN)", "(OUT)")))]
        if group:
            rule = (f"required port {group[0]} is not connected" if len(group) == 1
                    else f"connect {what} to one of: {', '.join(group)}")
            rule_zh = (f"必要的埠 {group[0]} 未連接" if len(group) == 1
                       else f"需連接{_PORT_ZH[direction]}，以下任一即可：{'、'.join(group)}")
            out.append({"field": None, "path": f"{path}\\Ports\\{group[0]}", "prompt": "", "rank": 0,
                        "kind": None, "certainty": "required", "source": "port", "rule": rule,
                        "rule_zh": rule_zh, "port": group[0], "ports": group})
    return out


def _missing(path, unset_all, violated, ports, specs=()) -> list[dict]:
    """Rule- and Aspen-decided items first, then the operating specs a column is short of
    (``_spec_items``), then the empty scalar fields, then the empty lists, each by rank. A rule
    names a top-level node; when that node is a folder (a stream's TEMP), its empty fields
    (TEMP\\MIXED) carry the rule."""
    out, promoted = [], set()
    for v in violated:
        key = v["field"].upper()
        hits = [u for u in unset_all if u["field"].upper() == key and u["field"] not in promoted]
        hits = hits or [u for u in unset_all if u["field"].upper().startswith(key + "\\")
                        and u["field"] not in promoted]
        for u in hits:
            promoted.add(u["field"])
            out.append({**u, "certainty": "required", "source": "rule", "rule": v["rule"]})
        if not hits:
            out.append({"field": v["field"], "path": v["path"], "prompt": "", "rank": _diag_rank(v["field"]),
                        "kind": None, "certainty": "required", "source": "rule", "rule": v["rule"]})
    out += _port_items(path, ports)
    for s in specs:
        if s["field"] not in promoted:
            promoted.add(s["field"])
            out.append(s)
    rest = [u for u in unset_all if u["field"] not in promoted]
    rest.sort(key=lambda u: u["kind"] == "list")          # stable: rank order kept within each
    out.extend({**u, "certainty": "unset", "source": "field", "rule": None} for u in rest)
    return out


def _missing_sheets(path, sheets, ports, specs) -> list[dict]:
    """The sheet layer's items: required ports, the operating specs a column is short of, then
    each incomplete sheet's empty fields (certainty "unset", source "sheet", ``sheet`` where it
    is: empty on the sheet Aspen marks incomplete, not each of them required)."""
    out = _port_items(path, ports) + list(specs)
    have = {s["field"] for s in specs}
    for sh in sheets:
        where = gui_sheets.where(sh)
        for f in sh["fields"]:
            if f["field"] in have:
                continue
            have.add(f["field"])
            it = {"field": f["field"], "path": f["path"], "prompt": f["prompt"], "rank": 0,
                  "kind": "value" if f["kind"] == "value" else "list", "certainty": "unset", "source": "sheet",
                  "rule": None, "sheet": where, "at": {"form": sh["form"], "sheet": sh["sheet"], "ids": sh["ids"]}}
            if f["kind"] == "row":
                it["row"] = f["row"]
            out.append(it)
    return out


def _container(path: str) -> str:
    return path if path in _SCAN_SINGLETONS else gui_sheets.container_of(path)


def _sheet_look(via, tree, path: str, typ, budget_ms, t0: float):
    """gui_sheets.look for one object when the sheet layer applies; None -- the field walk --
    when it does not, the table has no form for the object, or the object is flagged and no
    sheet says why."""
    if not gui_sheets.applies():
        return None
    cont = _container(path)
    if typ is None and cont != _BLOCKS:
        node = via.find(tree, path)
        typ = _record_type(via, node) if node is not None else None
    left = gui_sheets.MS if budget_ms is None else max(1.0, budget_ms - (time.perf_counter() - t0) * 1000)
    lk = _guarded(lambda: gui_sheets.look(via, tree, path, typ, cont, left), None)
    if lk is None:
        return None
    lk["type"] = typ
    if lk["sheets"] or (lk["flagged"] is False and not lk["cut"]):
        return lk
    return None


def sheet_status(app, path: str, typ) -> dict | None:
    """gui_sheets.status of one object (``typ`` its record type): each sheet's state by its CC
    flags; None when the sheet layer does not apply or has no form for it."""
    if not gui_sheets.applies():
        return None
    return _both(lambda via, tree: gui_sheets.status(via, tree, path, typ, _container(path)), app)


def off_fields(app, path: str, typ) -> dict | None:
    """gui_sheets.off_fields of one object: the inputs its current settings turn off; None when
    the sheet layer does not apply or has no form for it."""
    if not gui_sheets.applies():
        return None
    return _both(lambda via, tree: gui_sheets.off_fields(via, tree, path, typ, _container(path)), app)


OBJ_MAX = 40                                     # members of one container model_objects lists
_OBJ_SKIP = ("block", "streams")


def _objects(via, tree, open_) -> list[dict]:
    out = []
    for cont, k in gui_sheets.kinds().items():
        if k.get("g") in _OBJ_SKIP:
            continue
        node = via.find(tree, cont)
        if node is None:
            continue
        c = cont.rsplit("\\", 1)[-1]
        one = {"path": cont, "name": c, "g": k["g"], "c": c}
        if k.get("one"):
            out.append(dict(one, **({"todo": True} if _bit(via, node) else {})))
            continue
        try:
            col = via.elements(node)
            n = via.count(col)
        except Exception:
            continue
        if cont in _HEAVY and cont not in open_:
            if n:
                out.append(dict(one, n=n, folder=True, **({"todo": True} if _bit(via, node) else {})))
            continue
        typed = len(k.get("t") or {}) > 1
        for i in range(min(n, OBJ_MAX)):
            try:
                kid = via.item(col, i)
                o = {"path": cont + "\\" + via.name(kid), "name": via.name(kid), "g": k["g"], "c": c}
                if typed:
                    o["type"] = _record_type(via, kid)
                if _bit(via, kid):
                    o["todo"] = True
            except Exception:
                continue
            out.append(o)
    return out


def model_objects(app, open_=()) -> list[dict]:
    """The model's objects outside the flowsheet (the workbench's model panel): every singleton
    and container member the sheet table's kinds name but the blocks and streams, in the table's
    order -- [{"path", "name", "g" (setup, components, properties, reactions, convergence,
    flowsheeting, analysis), "c" (its container's last name, Design-Spec), "type"? (the record
    type, where a container holds several), "todo"? (Aspen flags it incomplete)}], OBJ_MAX a
    container. A _HEAVY container (its children cost a case load after a run) is one entry with
    "n" (its count) and "folder" until ``open_`` names it."""
    return _both(lambda via, tree: _objects(via, tree, tuple(open_)), app)


def sheet_paths(app, path: str, cls: str, ids=()) -> list[str]:
    """gui_sheets.sheet_paths of one object's sheet: its fields' tree paths (a member's under ``ids``)."""
    return _both(lambda via, tree: gui_sheets.sheet_paths(via, tree, path, cls, ids), app)


def _sheet_view(lk: dict) -> list[dict]:
    return [{"where": gui_sheets.where(sh), "form": sh["form"], "sheet": sh["sheet"],
             "ids": sh["ids"], "flags": sh["flags"][:6], "n_fields": len(sh["fields"]),
             "fields": [{k: f[k] for k in ("field", "kind", "prompt", "row") if k in f}
                        for f in sh["fields"][:KEEP["fields"]]]}
            for sh in lk["sheets"][:KEEP["sheets"]]]


def _deep(via, tree, path: str, cap: int, budget_ms, t0: float, fault=None) -> dict:
    d = {"path": path, "unset": [], "n_unset": 0, "zeros": [], "n_zeros": 0, "modes": [],
         "violated": [], "candidates": [], "rules": "ok", "ports": None, "missing": [], "n_missing": 0,
         "n_required": 0, "n_values": 0, "truncated": False, "layer": "fields", "sheets": [], "n_sheets": 0}
    try:
        ports = None
        try:
            ports = _ports(via, tree, path)
        except Exception:
            logger.debug("port check failed for '%s'", path, exc_info=True)
        specs = (_guarded(lambda: _spec_items(via, tree, path, ports.get("type"), []), [])
                 + _guarded(lambda: _knockout_items(via, tree, path, ports.get("type")), [])) if ports else []
        lk = _sheet_look(via, tree, path, (ports or {}).get("type"), budget_ms, t0)
        if lk is not None:
            missing = _missing_sheets(path, lk["sheets"], ports, specs)
            d.update(layer="sheet", type=lk["type"], sheets=_sheet_view(lk), n_sheets=len(lk["sheets"]),
                     truncated=lk["cut"], ports=ports, reads=lk["reads"])
        else:
            missing = _walk_missing(via, tree, path, cap, budget_ms, t0, d, ports, specs)
        if not any(x["certainty"] == "required" for x in missing) and not (lk is not None and not lk["flagged"]):
            obj = _guarded(lambda: _object_item(via, tree, path), None)
            if obj is not None:
                missing.insert(0, obj)
        d.update(missing=missing[:KEEP["missing"]], n_missing=len(missing),
                 n_required=sum(1 for x in missing if x["certainty"] == "required"),
                 n_values=sum(1 for x in missing if x["certainty"] == "unset" and x["kind"] != "list"))
    except Exception as exc:
        logger.debug("deep diagnosis failed for '%s'", path, exc_info=True)
        d["error"] = str(exc)[:300]
        if knowledge_tools.server_fault(exc):
            d["fault"] = True
            if fault is not None:
                fault(exc)
    return d


def _walk_missing(via, tree, path: str, cap: int, budget_ms, t0: float, d: dict, ports, specs) -> list[dict]:
    """The field walk (where the sheet layer does not apply): the object's empty and zero-valued
    fields and the GUI rules they match, into ``d``; returns the missing items."""
    base = path + "\\Input"
    root = via.find(tree, base)
    if not root:
        root, base = via.find(tree, path), path
    empty, zeros, modes, strvals, filled = [], [], [], [], []
    deadline = None if budget_ms is None else t0 + budget_ms / 1000
    if root is not None:
        d["truncated"] = not _walk_fields(via, root, cap, deadline, empty, zeros, modes, strvals, filled)
    empty.sort(key=lambda t: (_diag_rank(t[0]), t[0]))
    unset = [{"field": label, "path": base + "\\" + label, "prompt": _prompt(via, c),
              "rank": _diag_rank(label), "kind": _kind(via, c)} for label, c in empty]
    zero_l = [{"field": label, "path": base + "\\" + label, "prompt": _prompt(via, c),
               "value": _plain(v)} for label, c, v in zeros]
    violated, candidates = [], []

    def probe(name):
        node = via.find(tree, path + "\\Input\\" + name)
        if node is None:
            return None
        try:
            v = via.value(node)
        except Exception:
            return None
        return "empty" if (v is None or v == "") else "set"

    try:
        unset_fields = [(u["field"], u["prompt"]) for u in unset + zero_l]
        det_prompts = ([p for _, p in unset_fields if p]
                       + [p for p in (_prompt(via, c) for c in filled) if p])
        likely, cands = gui_rules.diagnose(det_prompts, strvals, unset_fields, probe=probe)
        violated = [{"field": f, "path": path + "\\Input\\" + f, "rule": t} for f, t in likely]
        for c in cands:
            s, _, t = c.partition("] ")
            candidates.append({"score": int(s.lstrip("[")), "rule": t, "certainty": "candidate"})
    except Exception:
        logger.debug("rule lookup failed for '%s'", path, exc_info=True)
        violated, candidates = [], []
    try:
        d["rules"] = gui_rules.state()
    except Exception:
        logger.debug("rule catalog state unknown", exc_info=True)
    d.update(unset=unset[:KEEP["unset"]], n_unset=len(unset), zeros=zero_l[:KEEP["zeros"]],
             n_zeros=len(zero_l), modes=[{"field": f, "value": _plain(v)} for f, v in modes[:KEEP["modes"]]],
             violated=violated, candidates=candidates, ports=ports)
    return _missing(path, unset, violated, ports, specs)


def deep(app, path: str, cap: int = EMPTY_CAP, budget_ms: float | None = None, fault=None) -> dict:
    """One flagged object in detail (see the module docstring). ``cap`` empty fields at most
    and, with ``budget_ms``, a walk cut short once that is spent (``truncated``) -- the
    defaults are check_inputs'. A failure leaves ``error`` set and the lists empty, as
    check_inputs then prints the object's path alone; Aspen's internal fault also sets
    ``fault`` and calls ``fault(exc)`` -- the caller flags the session (manager.note_fault)."""
    t0 = time.perf_counter()
    d = _both(_deep, app, path, cap, budget_ms, t0, fault)
    d["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return d


def _next_incomplete(via, tree):
    """The object Aspen's own Next goes to first: IHNode.NextIncomplete() of \\Data, a path
    relative to it ("\\Blocks\\X1"; live V15 it may name what no scan reads, a binary
    parameter set to review); None when it cannot be read."""
    node = via.find(tree, "\\Data")
    if node is None:
        return None
    if via is _Raw:
        try:
            d = _IDS.get("NextIncomplete")
            if d is None:
                d = node.GetIDsOfNames("NextIncomplete")
                d = _IDS["NextIncomplete"] = d[0] if isinstance(d, (tuple, list)) else d
            got = node.Invoke(d, 0, _CALL, True)
        except (AttributeError, TypeError) as exc:
            raise _NoRaw("NextIncomplete") from exc
    else:
        got = node.NextIncomplete()
    p = got[0] if isinstance(got, (tuple, list)) and got else got
    return "\\Data" + p if isinstance(p, str) and p.startswith("\\") else None


def _next_first(app, objects: list) -> list:
    """``objects`` with the one Aspen's Next names (or holds what it names) first, marked ``next``."""
    try:
        nxt = _both(_next_incomplete, app)
    except Exception as exc:
        if knowledge_tools.server_fault(exc):
            raise
        logger.debug("inputs_check: NextIncomplete not read", exc_info=True)
        return objects
    hit = next((o for o in objects if nxt and (nxt == o["path"] or nxt.startswith(o["path"] + "\\"))), None)
    if hit is None:
        return objects
    return [{**hit, "next": True}] + [o for o in objects if o is not hit]


def report(app, paths=None, limit: int | None = None, stop=None, budget_ms: float | None = None,
           cap: int = EMPTY_CAP, deep_budget_ms: float | None = None, fault=None, folders=()) -> dict:
    """scan(ports=True, heavy=True) plus deep() for the flagged objects (only those in ``paths`` when
    given), in scan order but the object Aspen's Next goes to first (``next``). Before each object: at most ``limit`` done, ``stop()`` false, at
    most ``budget_ms`` spent, no object's walk ended in Aspen's internal fault (deep's ``fault``,
    passed on) -- else the rest go to ``pending`` and ``state`` is "partial". ``cap`` /
    ``deep_budget_ms`` bound each object (deep()); the defaults are check_inputs', a panel
    takes ``cap=LIGHT_CAP``. Flagged blocks are refresh()ed and scanned again first, and
    ``traps`` (traps(app, folders)) read, as run_simulation does, so the two agree."""
    t0 = time.perf_counter()
    sc = scan(app, ports=True, heavy=True)
    if refresh(app, sc):
        sc = scan(app, ports=True, heavy=True)
    sc["objects"] = _next_first(app, sc["objects"])
    wanted = None if paths is None else set(paths)
    todo = [o["path"] for o in sc["objects"] if wanted is None or o["path"] in wanted]
    done, pending = {}, []
    for i, p in enumerate(todo):
        if ((limit is not None and len(done) >= limit) or (stop is not None and stop())
                or (budget_ms is not None and (time.perf_counter() - t0) * 1000 >= budget_ms)
                or any(x.get("fault") for x in done.values())):
            pending = todo[i:]
            break
        done[p] = deep(app, p, cap=cap, budget_ms=deep_budget_ms, fault=fault)
    return {**sc, "deep": done, "pending": pending, "state": "partial" if pending else "ok",
            "traps": traps(app, folders), "ms": round((time.perf_counter() - t0) * 1000, 1)}


# ----------------------------------------------------------------------------- text
# In place of the violated / candidate rule lines while gui_rules has no catalog (the rule texts
# are read from the user's Aspen on first use, tools/aspen_strings.py).
_RULES_NOTE = {
    "loading": "      GUI rules: not read yet (being extracted from your Aspen installation; "
               "check_inputs again in a few seconds adds the violated / candidate rules)",
    "unavailable": "      GUI rules: unavailable (they could not be read from your Aspen installation; "
                   "`aspen-mcp --check` says why, `aspen-mcp --extract-strings` retries)",
}


# Under the objects when a sheet line was printed.
_SHEET_NOTE = ("  (A sheet line names the form sheet Aspen marks incomplete -- where its Next would go -- and "
               "the fields empty on it; usually one of them is the gap, not every one is required. "
               "KW[] is an empty list.)")


def _field_list(items, total: int, cap: int) -> str:
    parts, seen_prompts = [], set()
    for label, prompt in items[:cap]:
        if prompt in seen_prompts:
            prompt = ""
        else:
            seen_prompts.add(prompt)
        if len(prompt) > 100:
            prompt = prompt[:100] + "..."
        parts.append(f"{label} ({prompt})" if prompt else label)
    more = f" [+{total - cap} more]" if total > cap else ""
    return ", ".join(parts) + more


def _head(path: str, typ) -> str:
    """How a sheet line names its object: 'RCSTR X1', 'Stream S1', 'Components', 'Calculator C-1'."""
    cont, name = path.rsplit("\\", 1) if "\\" in path else ("", path)
    if path in _SCAN_SINGLETONS:
        return "Components" if "Components" in path else "Methods"
    if cont == _BLOCKS:
        return f"{aspen_labels.type_name(typ) or 'Block'} {name}"
    if cont == "\\Data\\Streams":
        return f"Stream {name}"
    return cont.rsplit("\\", 1)[-1] + " " + name


def _field_word(f: dict) -> str:
    if f.get("row"):
        return f"{f['field']} row {f['row']} has no label"
    return f["field"] + ("[]" if f.get("kind") == "list" else "")


def _sheet_line(head: str, sh: dict) -> str:
    """'RCSTR X1 › Setup › Kinetics: RXN_ID[] is empty (Reaction set ID); also empty on this
    sheet: CRYST_ID[], ACT_VALUE[]'."""
    at = f"{head}{aspen_labels.ARROW}{sh['where']}: "
    fs = sh.get("fields") or []
    if not fs:
        return (at + "Aspen marks this sheet incomplete (" + ", ".join(sh.get("flags") or ()) + "); "
                "no empty field found on it")
    first = fs[0]
    prompt = " ".join(str(first.get("prompt") or "").split()).rstrip(". ")
    lead = _field_word(first) + ("" if first.get("row") else " is empty") + (f" ({prompt[:90]})" if prompt else "")
    rest = [_field_word(f) for f in fs[1:9]]
    more = sh.get("n_fields", len(fs)) - 1 - len(rest)
    if rest:
        lead += "; also empty on this sheet: " + ", ".join(rest) + (f" [+{more} more]" if more > 0 else "")
    return at + lead


def _render_ports(p) -> list[str]:
    out = []
    if p is not None:
        if p["connected"]:
            out.append("      ports connected: " + ", ".join(f"{k}={'+'.join(s)}" for k, s in p["connected"].items()))
        if p["unconnected"]:
            out.append("      ports unconnected: " + ", ".join(p["unconnected"]))
        elif not p["catalog"] and p["type"]:
            out.append(f"      (no port catalog for type '{p['type']}')")
    return out


def _render_deep(d: dict) -> list[str]:
    if d.get("fault"):
        return ["      not read: Aspen reported an internal fault reading it; runs of this session are refused "
                "until the model is closed and reopened"]
    if d.get("error"):
        return []
    out = [f"      required: {m['field']} ({m['rule']})" for m in d.get("missing") or ()
           if m.get("source") == "spec"]
    out[:0] = [f"      required: {m['rule']}" for m in d.get("missing") or ()
               if m.get("kind") in ("components", "method")]
    if d.get("layer") == "sheet":
        head = _head(d["path"], d.get("type"))
        out.extend("      " + _sheet_line(head, sh) for sh in d["sheets"])
        if d.get("n_sheets", 0) > len(d["sheets"]):
            out.append(f"      [+{d['n_sheets'] - len(d['sheets'])} more incomplete sheets]")
        return out + _render_ports(d["ports"])
    if d["n_unset"]:
        out.append("      unset: " + _field_list([(u["field"], u["prompt"]) for u in d["unset"]], d["n_unset"], 12))
    if d["n_zeros"]:
        out.append("      zero-valued: " + _field_list([(z["field"], z["prompt"]) for z in d["zeros"]], d["n_zeros"], 8))
    if d["modes"]:
        out.append("      modes: " + ", ".join(f"{m['field']}={m['value']}" for m in d["modes"][:10]))
    if d["violated"]:
        out.append("      violated (field exists and is empty, rule is unconditional):")
        out.extend(f"        {v['field']}: {v['rule']}" for v in d["violated"])
    if d["candidates"]:
        out.append("      candidate GUI rules (check against the values above; scores are keyword overlap):")
        out.extend(f"        [{c['score']}] {c['rule']}" for c in d["candidates"])
    if d.get("rules", "ok") in _RULES_NOTE and (d["n_unset"] or d["n_zeros"]):
        out.append(_RULES_NOTE[d["rules"]])
    return out + _render_ports(d["ports"])


def render(rep: dict) -> str:
    """check_inputs' text for a report(): the flagged objects, a block with an open required port
    among them, each with its diagnosis when it has one, a flagged container none of whose objects
    is (run_simulation refuses it too: refusal_paths), then the report's ``traps``."""
    objs, traps_ = rep["objects"], rep.get("traps") or []
    listed = {o["path"] for o in objs}
    bare = [p for p in refusal_paths(rep) if p not in listed]
    if not objs and not bare and not traps_:
        return "All required inputs are complete. Ready to run."
    lines, sheets = [], False
    for o in objs:
        lines.append(f"  - {o['path']}" + ("  (Aspen's Next goes here first)" if o.get("next") and len(objs) > 1 else ""))
        if o.get("open_ports"):
            lines.append("      open required port: " + "/".join(o["open_ports"]))
        d = rep.get("deep", {}).get(o["path"])
        if d:
            lines.extend(_render_deep(d))
            sheets |= d.get("layer") == "sheet" and bool(d.get("sheets"))
    lines.extend(f"  - {p}  (Aspen flags the folder itself, none of the objects in it)" for p in bare)
    if sheets:
        lines.append(_SHEET_NOTE)
    out = f"Incomplete inputs ({len(objs) + len(bare)}):\n" + "\n".join(lines) if lines else ""
    if traps_:
        out += ("\n" if out else "") + "Aspen's input translator would reject:\n" + "\n".join(f"  - {t}" for t in traps_)
    return out
