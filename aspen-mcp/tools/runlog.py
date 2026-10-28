"""What a run changed: the inputs changed since the run before and the results that moved.

    b = runlog.before_run(manager, session, scope)   # just before Aspen runs: None to skip
    ... the run ...
    runlog.after_run(b, manager, fields)             # just after: the run record's fields gain
                                                     # seq, inputs, delta, fp_ms (and its id, t)

A run that ran (status ok | warn | error) gets:
- ``seq``: this model's runs that ran so far, this one included (journal.pending's + 1);
- ``inputs``: what ``journal.pending`` held just before it -- the inputs changed since the last
  run, net per target: {"n", "struct", "since" (the last run's record id), "more", "joint",
  "items": [{"path", "before", "after", "actor", "n"}] (value / attribute ones, at most
  INPUTS_MAX; "more" counts the rest), "objs": [the structure changes, at most OBJS_MAX], "full":
  the journal's table was full}. ``joint``: more than one input changed, so the results below
  cannot be pinned on any one of them (the window offers to test them one at a time);
- ``delta``: a result fingerprint read just before and just after the run, {"n": results that
  moved, "read": results compared, "first": none before (a model's first run), "partial": the
  budget cut the fingerprint short, "reinit": before = the last run's after-read, "error": the
  run ended in errors -- V15 keeps the results of a run "completed with errors" (a column not
  converged, a mass balance off), so they are compared all the same; only when the after-read
  finds no result at all (Aspen cleared them) is there no delta -- "items": the ITEMS_MAX that
  moved most, product streams first, [{"path", "b", "a", "u", "small": within Aspen's
  tolerances (< SMALL), listed last}]}.
A run that did not happen (refused, failed) gets none of these; loop runs are not measured
(their summary record covers them: ``before_run`` returns None in an Aggregate).

The fingerprint (``key_paths``), in this order: the core, read whatever the budget -- product
streams' T / P / F and main components (their COMP_TOP largest mole fractions last read, at most
TOP_MAX in all: a purity is what moves when a product's T / P / F are fixed by specs: in a
column where only the reflux changed, the distillate's main component's fraction moved); the components of a product not read
yet, while those read do not add up to 1 (within SUM_EPS: the rest carry less than that
together), each product until they do -- a composition is found once: a product carries few of
a model's components (live V15: 35 of 5 x 39 in one model, 17 of 4 x 47 in another); the block results
(``configure(outputs=)``: each block type's Output rows in its general docs file), the first row of
every block, then the second...; the products' other non-zero components; the other streams'
T / P / F; last, the components read as zero. The composition tiers take the products in turn.
At most PATHS_MAX compared, read by path every time (tools/nodes.py: a node kept across a run
reads the run before's result); a path Aspen does not have remembered and not looked up again
until the topology changes. Every mole fraction read is remembered (``_State.fr``); one read as
zero before the run is not read again after it. The topology comes from the workbench window's
flowsheet when it is newer than the last structure change in the journal
(``configure(topology=)``, no COM), else from Aspen (0.1-0.7 s on mid-sized models; once a
session, and again after a structure change). Cost (live V15, two mid-sized models,
hidden): ~0.33 ms a path before a run and after it, a block's result right after a run up to
~2 ms, a visible session's often several times that; a stream's mole fractions through
its Elements cost as much as by path (no vector read). The reads of both sides together stay
within BUDGET_MS and RUN_SHARE of the session's last run time -- but for the core, and for
looking into the compositions: at most LOOK_MS a run besides, in a session's first runs
(~80-90 fractions in a mid-sized model, before they add up).
Reinitialize clears Aspen's results: a before-read that finds none uses the last run's
after-read when the journal has no run since it.

``last_delta(session)``: every stream T / P / F that moved in the session's last measured run,
for the window's values layer (``sess.run_delta``); ``peek`` reads a few of the last after-read
values again (an external run changed them) and ``since_last`` measures such a run once
found; ``line(record)`` a run record in one line; ``topology(manager, session)`` the topology
the fingerprint goes by (the external-edit watch set is built from it too).

A prediction's measurement: ``watch(manager, session, paths)`` -- at most WATCH_MAX
results the user's window will compare with their guesses (which never reach the server) --
reads them now (``b``); the session's next measured run, whoever made it, reads them once more
in ``after_run`` (``a``: at most WATCH_MAX lookups a run, none without a watch): ``state`` done,
or failed when the run did not run or ended in errors -- the watch then waits for the next
run that goes well. ``watching(session)`` is it now (gone after WATCH_TTL_S), ``unwatch`` ends it.

An approved proposal's follow: ``follow(session, key, model, paths)`` -- every
measured run of the session that ran keeps its record's id, seq, status, inputs and delta, and one
that went well reads the proposal's watched paths again (at most WATCH_MAX lookups a run, none
without a follow); ``followed`` / ``unfollow``. The workbench builds the result tags from it
(tools/notable.py). ``read(manager, session, paths)`` reads paths now.
Stdlib only; COM only through the manager's apps; nothing raises into the run.
"""
from __future__ import annotations

import copy
import itertools
import logging
import math
import threading
import time

from tools import dispid, journal, nodes, recorder

logger = logging.getLogger(__name__)

_perf = time.perf_counter
BUDGET_MS = 40.0          # a run's fingerprint reads, before and after together, at most this
RUN_SHARE = 0.05          # ... and this share of the session's last run time
PATHS_MAX = 100           # paths one fingerprint compares
CORE_MAX = 30             # product streams' T / P / F paths read whatever the budget (and TOP_MAX components)
COMP_TOP, TOP_MAX = 2, 12  # a product's main components (MOLEFRAC), all products' at most: read with the core
SUM_EPS = 1e-4            # a product's fractions read add up to 1 within this: its other components are not looked for
LOOK_MS = 30.0            # besides the budget, at most this a run spends looking into the products' compositions
ITEMS_MAX = 12            # delta items a run record keeps
INPUTS_MAX, OBJS_MAX = 10, 5
REL_EPS, ABS_EPS, FRAC_EPS = 1e-6, 1e-9, 1e-6   # a smaller change is no change
SMALL = 1e-4              # a smaller relative change is within Aspen's tolerances: listed last, "small"
PEEK_MAX = 12              # results peek reads again, spread over the flowsheet's objects
_TPF = (("t", "RES_TEMP"), ("p", "RES_PRES"), ("f", "TOT_FLOW"))
_STRUCT = ("add", "remove", "connect", "open", "patch")                 # records that change the topology
STATS = {"found": 0, "missing": 0, "skipped": 0, "topology": 0}         # lookup counts (a module attribute, for inspection)

WATCH_MAX = 3             # results one prediction compares
WATCH_TTL_S = 7200.0      # ... and how long it waits for a run
_now = time.time          # the watch's clock (a module attribute so it can be overridden)

_OUTPUTS: dict = {}       # block TYPE -> [Output\... rows]
_TOPOLOGY = None          # fn(session) -> the window's flowsheet (no COM) or None
_S: dict = {}             # session -> _State
_W: dict = {}             # session -> its prediction's watch (watch)
_F: dict = {}             # session -> an approved proposal's follow (follow)
_DIRTY: dict = {}         # model -> time of its latest structure record
_lock = threading.Lock()
_heard = False


class _State:
    """A session's model, topology, paths Aspen does not have, block types, the last run's
    after-read (``last``: {"run", "seq", "vals"}), its time (``secs``), the after/before cost
    ratio of a path, the last delta (``delta``, last_delta's) and the product streams' mole
    fractions last read (``fr``: {path: value}, what the composition tiers go by)."""
    __slots__ = ("model", "topo", "topo_t", "missing", "types", "last", "secs", "ratio", "delta", "fr")

    def __init__(self, model):
        self.model, self.topo, self.topo_t, self.missing, self.types = model, None, 0.0, set(), {}
        self.last, self.secs, self.ratio, self.delta, self.fr = None, None, 2.0, None, {}


class Before:
    """A run about to happen: the session, its model, ``seq`` (runs that ran so far), the
    ``inputs`` snapshot and the fingerprint ``vals`` {path: value} in reading order (the paths
    compared: not a mole fraction read as zero); ``ms`` the before-read, ``cms`` its reads of
    the paths compared, ``lms`` of the components looked for. ``blind``: the before-read is not
    the results just before the run (``since_last``): no delta. ``actor`` / ``via``: who ran it
    (the recording scope's; a prediction says so)."""
    __slots__ = ("session", "model", "seq", "inputs", "vals", "first", "partial", "ms", "cms", "lms", "reused",
                 "budget", "core", "broken", "blind", "actor", "via")

    def __init__(self, session, model, seq, inputs):
        self.session, self.model, self.seq, self.inputs = session, model, seq, inputs
        self.vals, self.first, self.partial, self.reused = {}, True, False, False
        self.ms = self.cms = self.lms = 0.0
        self.budget, self.core, self.broken, self.blind = BUDGET_MS, 0, False, False
        self.actor = self.via = None


def configure(outputs=None, topology=None) -> None:
    """``outputs`` {block type: [Output\\... rows]}; ``topology(session)``: the window's
    flowsheet {"blocks": [{"name", "type"}], "streams": [{"name", "from", "to"}],
    "components", "taken_at", "model"} or None, without COM."""
    global _OUTPUTS, _TOPOLOGY
    if outputs is not None:
        _OUTPUTS = {str(k).upper(): [r for r in v if str(r).startswith("Output")] for k, v in outputs.items()}
    if topology is not None:
        _TOPOLOGY = topology
    _hear()


def _hear() -> None:
    global _heard
    if not _heard:
        _heard = True
        journal.listen(learn)


def learn(model, recs) -> None:
    """journal.listen: a record that changes the topology (an element added or removed, a
    connection, an open, a file patch) makes the model's topology read again."""
    t = None
    for r in recs or ():
        if r.get("kind") == "change" and r.get("op") in _STRUCT and r.get("status") == "changed":
            t = max(t or 0.0, float(r.get("t") or journal.now()))
            tg = r.get("target") if isinstance(r.get("target"), dict) else {}
            if tg.get("kind") == "block" and tg.get("name"):
                with _lock:
                    for st in _S.values():
                        if st.model == model:
                            st.types.pop(tg["name"], None)
    if t is not None:
        with _lock:
            _DIRTY[model] = max(_DIRTY.get(model, 0.0), t)


def _state(session, model) -> _State:
    with _lock:
        st = _S.get(session)
        if st is None or st.model != model:
            st = _S[session] = _State(model)
        return st


# ---------------------------------------------------------------------------- topology
def _kids(node) -> list:
    if node is None:
        return []
    els = node.Elements
    return [x for x in (els.Item(i) for i in range(els.Count)) if x is not None]


def _read_topology(session, app, st) -> dict:
    """Blocks (types read once per block name), which block each stream comes from and goes
    to, and the components -- from Aspen (0.1-0.7 s on a 20-block model)."""
    find = lambda p: nodes.find(session, app, p)  # noqa: E731
    blocks, src, dst = [], {}, {}
    for b in _kids(find(r"\Data\Blocks")):
        name = str(dispid.get(b, "Name"))
        typ = st.types.get(name)
        if typ is None:
            typ = st.types[name] = str(dispid.get(b, "AttributeValue", 6) or "").upper()
        blocks.append((name, typ))
        for c in _kids(find(rf"\Data\Blocks\{name}\Connections")):
            port = str(dispid.get(c, "Value") or "").upper()
            if "(IN)" in port:
                dst[str(dispid.get(c, "Name"))] = name
            elif "(OUT)" in port:
                src[str(dispid.get(c, "Name"))] = name
    streams = [str(dispid.get(s, "Name")) for s in _kids(find(r"\Data\Streams"))]
    comps = [str(dispid.get(c, "Name")) for c in _kids(find(r"\Data\Components\Specifications\Input\TYPE"))]
    STATS["topology"] += 1
    return {"blocks": blocks, "prods": [s for s in streams if s in src and s not in dst],
            "others": [s for s in streams if not (s in src and s not in dst)], "comps": comps,
            "feeds": [s for s in streams if s not in src]}


def _from_flowsheet(fs: dict) -> dict:
    streams = [s for s in fs.get("streams") or [] if isinstance(s, dict) and s.get("name")]
    prods = [s["name"] for s in streams if s.get("from") and not s.get("to")]
    return {"blocks": [(b["name"], str(b.get("type") or "").upper()) for b in fs.get("blocks") or []
                       if isinstance(b, dict) and b.get("name")],
            "prods": prods, "others": [s["name"] for s in streams if s["name"] not in prods],
            "comps": [str(c) for c in fs.get("components") or []],
            "feeds": [s["name"] for s in streams if not s.get("from")]}


def _topology(session, app, st) -> dict:
    dirty = _DIRTY.get(st.model, 0.0)
    if st.topo is not None and st.topo_t > dirty + 0.001:     # a record's time is rounded to the ms
        return st.topo
    fs = None
    if _TOPOLOGY is not None:
        try:
            fs = _TOPOLOGY(session)
        except Exception as exc:
            logger.debug("runlog: no window flowsheet for %s (%r)", session, exc)
    if isinstance(fs, dict) and fs.get("model") == st.model and (fs.get("taken_at") or 0) >= dirty:
        st.topo, st.topo_t = _from_flowsheet(fs), float(fs.get("taken_at") or 0)
    else:
        st.topo, st.topo_t = _read_topology(session, app, st), journal.now()
    st.missing = set()
    return st.topo


def _turns(lists) -> list:
    """The items of ``lists`` taking each list in turn: the first of each, then the second..."""
    return [x for rank in itertools.zip_longest(*lists) for x in rank if x is not None]


def _fracs(st) -> tuple:
    """The product streams' mole-fraction paths in four tiers (each ``_turns`` over the
    products), by the fractions last read (``st.fr``): ``top`` a product's COMP_TOP largest;
    ``look`` its components not read yet while those read do not add up to 1 (within SUM_EPS);
    ``rest`` its other non-zero ones; ``zero`` those read as zero. Those not read of a product
    whose fractions add up to 1 are none of them: the rest of it is less than SUM_EPS together.
    And ``sums`` {product: its fractions read, added up} of the products looked into."""
    fr, tp = st.fr, st.topo
    top, look, rest, zero, sums = [], [], [], [], {}
    for s in tp["prods"]:
        paths = [rf"\Data\Streams\{s}\Output\MOLEFRAC\MIXED\{c}" for c in tp["comps"]]
        known = [p for p in paths if p in fr]
        nz = sorted((p for p in known if abs(fr[p]) >= FRAC_EPS), key=lambda p: -fr[p])
        top.append(nz[:COMP_TOP])
        rest.append(nz[COMP_TOP:])
        zero.append([p for p in known if abs(fr[p]) < FRAC_EPS])
        total = sum(fr[p] for p in known)
        new = [p for p in paths if p not in fr] if total < 1.0 - SUM_EPS else []
        look.append(new)
        if new:
            sums[s] = total
    return _turns(top), _turns(look), _turns(rest), _turns(zero), sums


def _paths(st) -> tuple[list, int, dict]:
    """(the fingerprint's candidate paths in reading order, how many lead as the core -- the
    product streams' T / P / F and main components -- and ``_fracs``'s sums)."""
    tp = st.topo
    top, look, rest, zero, sums = _fracs(st)
    core = [rf"\Data\Streams\{s}\Output\{f}" for s in tp["prods"] for _, f in _TPF][:CORE_MAX] + top[:TOP_MAX]
    out = core + look
    out += _turns([[rf"\Data\Blocks\{name}\{rel}" for rel in _OUTPUTS.get(typ, ())] for name, typ in tp["blocks"]])
    out += rest + top[TOP_MAX:]
    out += [rf"\Data\Streams\{s}\Output\{f}" for s in tp["others"] for _, f in _TPF]
    out += zero
    keep = [p for p in out if p not in st.missing]
    return keep, sum(p not in st.missing for p in core), sums


def topology(manager, session) -> dict | None:
    """The session's topology as the fingerprint takes it -- {"blocks": [(name, TYPE)], "prods",
    "others", "feeds" (streams no block produces), "comps"} -- the window's when current, else read
    from Aspen once (and again after a structure change); None without the session."""
    app = manager.get_app(session)
    if app is None:
        return None
    return _topology(session, app, _state(session, manager.model_id(session)))


def key_paths(manager, session) -> list:
    """The paths a run's fingerprint would read (at most PATHS_MAX; the budget may stop it
    sooner), product streams first; reads the topology from Aspen if it is not known."""
    app = manager.get_app(session)
    if app is None:
        return []
    st = _state(session, manager.model_id(session))
    _topology(session, app, st)
    return _paths(st)[0][:PATHS_MAX]


# ---------------------------------------------------------------------------- the run
def _inputs(p: dict) -> dict:
    items, objs, nval, struct = [], [], 0, 0
    for it in p.get("items") or []:
        if it.get("op") in ("value", "attr"):
            nval += 1
            if len(items) < INPUTS_MAX:
                x = {k: it[k] for k in ("path", "before", "after", "actor", "n") if it.get(k) is not None}
                if it["op"] == "attr":
                    x["op"] = "attr"
                items.append(x)
        else:
            struct += 1
            if len(objs) < OBJS_MAX:
                tg = it.get("target") or {}
                objs.append({"op": it.get("op"), "path": it.get("path"), **{k: tg[k] for k in ("kind", "name", "stream")
                                                                           if tg.get(k)}})
    out = {"n": nval + struct, "struct": struct, "since": p.get("run"), "more": nval - len(items),
           "joint": nval + struct > 1, "items": items}
    if objs:
        out["objs"] = objs
    if p.get("more"):
        out["full"] = True                     # the journal's table was full: at least this many
    return out


def before_run(manager, session, scope=None):
    """Just before a run: the inputs changed since the last run (journal.pending) and the
    fingerprint read now (``broken`` when that failed: no delta then). None -- the run is not
    measured -- outside a recording scope, in a loop's (an Aggregate), with the journal off, or
    without a session, model or app."""
    try:
        if scope is None or not getattr(scope, "on", False) or getattr(scope, "_join", None) is not None \
                or isinstance(scope, recorder.Aggregate) or not session:
            return None
        model, app = manager.model_id(session), manager.get_app(session)
        pend = journal.pending(model) if model else None
        if app is None or pend is None:
            return None
        b = Before(session, model, int(pend.get("seq") or 0), _inputs(pend))
        b.actor, b.via = getattr(scope, "actor", None), getattr(scope, "via", None)
    except Exception as exc:
        logger.warning("runlog: the run of %s not measured (%r)", session, exc)
        return None
    try:
        _fingerprint(b, app, pend.get("run"))
    except Exception as exc:
        logger.warning("runlog: no fingerprint before the run of %s (%r)", session, exc)
        b.vals, b.broken = {}, True
    return b


def _fingerprint(b, app, last_run) -> None:
    """The before-read: candidates in order, the core always, the rest while the budget lasts --
    what is read so far and the after-read of the paths compared (``ratio`` times their reads) --
    but for looking into a product's composition (``look``): at most LOOK_MS besides, each
    product until its fractions read add up to 1."""
    session, st = b.session, _state(b.session, b.model)
    _topology(session, app, st)                  # the window's; after a structure change from Aspen
    t0 = _perf()
    cands, core, sums = _paths(st)
    b.budget = budget = BUDGET_MS if not st.secs else min(BUDGET_MS, max(0.0, RUN_SHARE * st.secs * 1e3))
    limit, cmp_s, look_s = budget / 1e3, 0.0, 0.0
    miss, had, zeros = [], False, 0
    for i, p in enumerate(cands):
        t = _perf()
        if len(b.vals) >= PATHS_MAX or (i >= core and (t - t0 - look_s) + st.ratio * cmp_s > limit):
            b.partial = True
            STATS["skipped"] += len(cands) - i
            break
        frac = "\\MOLEFRAC\\" in p
        prod = p.split("\\")[3] if frac and p not in st.fr else None
        if prod not in sums:
            prod = None                            # not a component looked for
        elif not had or sums[prod] >= 1.0 - SUM_EPS or look_s * 1e3 >= LOOK_MS:
            continue                               # no results to look at; found whole; looked enough
        node = nodes.find(session, app, p)
        if node is None:
            miss.append(p)
            continue
        v = dispid.get(node, "Value")
        had = had or (v is not None and v != "")
        f = None
        if frac:
            f = 0.0 if had and v in (None, "") else _num(v)      # none where the model has results: none of it
            if f is not None:
                st.fr[p] = f
        if prod is not None:
            look_s += _perf() - t
            sums[prod] += f or 0.0
        if f is not None and abs(f) < FRAC_EPS:  # a component the product does not carry: not read after
            zeros += 1
            continue
        b.vals[p] = v
        cmp_s += _perf() - t
    STATS["found"] += len(b.vals) + zeros
    STATS["missing"] += len(miss)
    b.cms, b.lms = cmp_s * 1e3, look_s * 1e3
    if had:
        st.missing.update(miss)                    # with results in the model, a missing path stays missing
    last = st.last
    if not had and last and not last.get("cleared") and last.get("run") == last_run and last.get("seq") == b.seq:
        b.vals = {p: last["vals"][p] for p in b.vals if p in last["vals"]}   # Reinitialize cleared them
        had = b.reused = True
    b.core = sum(p in b.vals for p in cands[:core])
    b.first = not had
    b.ms = (_perf() - t0) * 1e3


def _num(x):
    if isinstance(x, bool) or x is None:
        return None
    try:
        f = float(x) if isinstance(x, (int, float, str)) else None
    except ValueError:
        return None
    return f if f is not None and math.isfinite(f) else None


def _plain(x):
    """A value as a record keeps it: a number as a float."""
    f = _num(x)
    return x if f is None else f


def _moved(path, b, a):
    """How much a result moved (relative; inf from or to nothing, or a text that changed), or
    None: it did not."""
    x, y = _num(b), _num(a)
    if x is None or y is None:
        return None if b == a or (b in (None, "") and a in (None, "")) else math.inf
    d = abs(y - x)
    if d < (FRAC_EPS if "\\MOLEFRAC\\" in path else ABS_EPS) or d <= REL_EPS * max(abs(x), abs(y)):
        return None
    return d / abs(x) if x else math.inf


def after_run(b, manager, fields: dict) -> dict:
    """Just after the run: ``fields`` (its record's) gain seq, inputs, delta and fp_ms, and the
    record's ``t`` and ``id`` (so the session's last delta names it). A run that ended in errors
    is compared too (V15 keeps its results; the delta says ``error``), unless the after-read
    finds no result at all -- Aspen cleared them: no delta, and nothing kept to compare with.
    Nothing when ``b`` is None or the run did not happen. A prediction waiting on the session is
    measured too (``watch``), a run that did not happen included. Returns ``fields``."""
    if b is None:
        return fields
    if fields.get("status") in journal.RAN:
        _compare(b, manager, fields)
    if _W:
        _watched(b, manager, fields)
    if _F:
        _followed(b, manager, fields)
    return fields


def _compare(b, manager, fields: dict) -> None:
    """after_run's compare of a run that ran (``fields`` gain seq, inputs, delta, fp_ms)."""
    try:
        t = journal.now()
        fields.update(t=t, id=journal.new_id("e", t), seq=b.seq + 1, inputs=b.inputs)
        st = _state(b.session, b.model)
        if isinstance(fields.get("secs"), (int, float)) and fields["secs"] > 0:
            st.secs = float(fields["secs"])
        app = manager.get_app(b.session)
        if app is None or b.broken:
            st.last = st.delta = None            # the results not read: no delta
            return
        t0, moved, after = _perf(), [], {}
        limit = t0 + max(0.0, b.budget - b.ms + b.lms) / 1e3     # what the before-read left; the core whatever
        partial = b.partial
        for i, (p, was) in enumerate(b.vals.items()):
            if i >= b.core and _perf() > limit:
                partial = True
                break
            node = nodes.find(b.session, app, p)
            if node is None:
                continue
            v = after[p] = dispid.get(node, "Value")
            if "\\MOLEFRAC\\" in p and _num(v) is not None:
                st.fr[p] = _num(v)
            rel = None if b.first else _moved(p, was, v)
            if rel is not None:
                u = dispid.get(node, "UnitString")
                moved.append((rel, p, was, v, u or None))
        ms = (_perf() - t0) * 1e3
        error = fields["status"] == "error"
        if error and not any(v is not None and v != "" for v in after.values()):
            st.delta = None                      # Aspen cleared the results: no delta; results that
            st.last = {"run": fields["id"], "seq": fields["seq"], "t": fields["t"], "vals": after,
                       "cleared": True}          # appear after it are a run's (peek, since_last)
            return
        if after and b.vals and not b.reused and b.cms > 0:
            r = (ms / len(after)) / (b.cms / len(b.vals))
            st.ratio = min(5.0, max(0.5, 0.5 * st.ratio + 0.5 * r))
        st.last = {"run": fields["id"], "seq": fields["seq"], "t": fields["t"], "vals": after}
        if b.blind:                              # a run found after the fact, with runs between: no delta
            st.delta = None
            return
        prods = tuple(rf"\Data\Streams\{s}\Output" + "\\" for s in (st.topo or {}).get("prods", ()))
        moved.sort(key=lambda m: (m[0] < SMALL, not m[1].startswith(prods), math.isinf(m[0]),
                                  0 if math.isinf(m[0]) else -m[0]))
        fields["delta"] = {"n": len(moved), "read": len(after), "first": b.first, "partial": partial,
                           "items": [_item(p, was, v, u, rel < SMALL) for rel, p, was, v, u in moved[:ITEMS_MAX]]}
        if b.reused:
            fields["delta"]["reinit"] = True     # before = the last run's after-read (Reinitialize cleared them)
        if error:
            fields["delta"]["error"] = True      # the results of a run that ended in errors
        fields["fp_ms"] = round(b.ms + ms, 1)
        st.delta = None if b.first else _streams(fields, b.model, moved)
    except Exception as exc:
        logger.warning("runlog: the run of %s not compared (%r)", b.session, exc)


def _item(p, was, v, u, small=False) -> dict:
    out = {"path": p, "b": _plain(was), "a": _plain(v)}
    if u:
        out["u"] = u
    if small:
        out["small"] = True
    return out


def _streams(fields, model, moved) -> dict:
    """last_delta: {"id", "seq", "t", "model", "s": {stream: {"t"|"p"|"f": [before, after]}},
    "u": {stream: {key: unit}}} of the stream T / P / F that moved."""
    keys = {f: k for k, f in _TPF}
    s, u = {}, {}
    for _, p, was, v, unit in moved:
        parts = p.split("\\")
        if len(parts) == 6 and parts[2] == "Streams" and parts[4] == "Output" and parts[5] in keys:
            s.setdefault(parts[3], {})[keys[parts[5]]] = [_plain(was), _plain(v)]
            if unit:
                u.setdefault(parts[3], {})[keys[parts[5]]] = unit
    return journal.clean({"id": fields["id"], "seq": fields["seq"], "t": fields["t"], "model": model, "s": s, "u": u})


# ---------------------------------------------------------------------------- predictions
def _vu(session, app, path):
    """[value, unit] at ``path`` now (a number as a float); None when Aspen has no such node."""
    node = nodes.find(session, app, path)
    if node is None:
        return None
    return [_plain(dispid.get(node, "Value")), dispid.get(node, "UnitString") or None]


def watch(manager, session, paths, wid=None) -> dict | None:
    """A prediction's results: at most WATCH_MAX of ``paths`` (tree paths), read now --
    ``b`` {path: [value, unit], or None: not in the model} -- and compared at the session's next
    measured run (``after_run``); it replaces the session's earlier one. Returns {"id" (``wid``,
    the window's, else a new one), "t", "model", "paths", "b", "state": "waiting"} (a copy); None,
    and no watch, without paths or the session. Only paths: the guesses stay in the window."""
    paths = list(dict.fromkeys(p for p in paths or () if isinstance(p, str) and p.startswith("\\")))[:WATCH_MAX]
    app = manager.get_app(session) if session and paths else None
    if app is None:
        unwatch(session)
        return None
    try:
        b = {p: _vu(session, app, p) for p in paths}
        model = manager.model_id(session)
    except Exception as exc:
        logger.warning("runlog: the prediction on %s not read (%r)", session, exc)
        return None
    w = {"id": str(wid)[:40] if wid else journal.new_id("p"), "t": round(_now(), 3), "model": model,
         "paths": paths, "b": b, "state": "waiting"}
    with _lock:
        _W[session] = w
        return copy.deepcopy(w)


def watching(session) -> dict | None:
    """The session's prediction watch now (a copy): waiting, failed (the last run did not go well:
    still waiting) or done; None -- none, or older than WATCH_TTL_S (then ended)."""
    with _lock:
        w = _W.get(session)
        if w is not None and _now() - w["t"] > WATCH_TTL_S:
            del _W[session]
            w = None
        return copy.deepcopy(w) if w is not None else None


def unwatch(session=None) -> None:
    """End the session's prediction watch (None: every session's)."""
    with _lock:
        if session is None:
            _W.clear()
        else:
            _W.pop(session, None)


def _watched(b, manager, fields) -> None:
    """after_run's part for a prediction waiting on the run's session and model: a run that went
    well (ok, warn) reads the watched paths again -- ``a`` as ``b``, the run's ``run`` (record id),
    ``seq``, ``status``, ``by`` {actor, via} and ``at`` --, state done; one that did not run or
    ended in errors leaves ``failed`` {run, seq, status, by, at}, state failed, and the watch waits
    for the next run. A done or expired watch, or another model's: nothing read."""
    with _lock:
        w = _W.get(b.session)
    if w is None or w["state"] == "done":
        return
    if w.get("model") != b.model or _now() - w["t"] > WATCH_TTL_S:
        with _lock:
            if _W.get(b.session) is w:
                del _W[b.session]
        return
    status, at = fields.get("status"), round(_now(), 3)
    by = {k: v for k, v in (("actor", b.actor), ("via", b.via)) if v}
    run = {k: v for k, v in (("run", fields.get("id")), ("seq", fields.get("seq")), ("status", status),
                             ("by", by), ("at", at)) if v is not None}
    if status in ("ok", "warn"):
        app = manager.get_app(b.session)
        if app is None:
            return
        try:
            a = {p: _vu(b.session, app, p) for p in w["paths"]}
        except Exception as exc:
            logger.warning("runlog: the prediction on %s not measured (%r)", b.session, exc)
            return
        new = dict(w, a=a, state="done", **run)
    else:
        new = dict(w, state="failed", failed=run)
    with _lock:
        if _W.get(b.session) is w:
            _W[b.session] = new


# ---------------------------------------------------------------------------- a proposal's effects
def read(manager, session, paths) -> dict:
    """{path: [value, unit] | None} of ``paths`` now (at most WATCH_MAX; {} without the session)."""
    app = manager.get_app(session) if session else None
    if app is None:
        return {}
    return {p: _vu(session, app, p) for p in list(paths or ())[:WATCH_MAX]}


def follow(session, key, model, paths=()) -> None:
    """Follow the session's measured runs for an approved proposal (``key``: its id): each run that
    ran keeps its record's id, seq, status, inputs and delta (``run``), and one that went well (ok,
    warn) reads ``paths`` (the proposal's watch, at most WATCH_MAX) again (``a``). Separate from a
    prediction's watch (``watch``); one follow a session, replaced by the next."""
    with _lock:
        _F[session] = {"key": key, "model": model, "paths": list(paths or ())[:WATCH_MAX], "a": None, "run": None,
                       "t": round(_now(), 3)}


def followed(session, key=None) -> dict | None:
    """The session's follow (a copy), or None -- none, or another proposal's (``key``)."""
    with _lock:
        f = _F.get(session)
        return copy.deepcopy(f) if f is not None and (key is None or f.get("key") == key) else None


def unfollow(session, key=None) -> None:
    """End the session's follow (only ``key``'s, when given)."""
    with _lock:
        f = _F.get(session)
        if f is not None and (key is None or f.get("key") == key):
            del _F[session]


def _followed(b, manager, fields) -> None:
    """after_run's part for a proposal followed on the run's session and model: a run that ran keeps
    its record (``run``); one that went well reads the watched paths again (``a``)."""
    with _lock:
        f = _F.get(b.session)
    status = fields.get("status")
    if f is None or f.get("model") != b.model or status not in journal.RAN or not fields.get("id"):
        return
    d = fields.get("delta") if isinstance(fields.get("delta"), dict) else None
    run = {"id": fields.get("id"), "seq": fields.get("seq"), "status": status, "t": fields.get("t"),
           "inputs": copy.deepcopy(fields.get("inputs")), "delta": copy.deepcopy(d)}
    a = None
    if status in ("ok", "warn") and f["paths"]:
        app = manager.get_app(b.session)
        try:
            a = {p: _vu(b.session, app, p) for p in f["paths"]} if app is not None else None
        except Exception as exc:
            logger.warning("runlog: the proposal's results on %s not read (%r)", b.session, exc)
    with _lock:
        if _F.get(b.session) is f:
            _F[b.session] = dict(f, run=run, a=a)


# ---------------------------------------------------------------------------- readers
def last_delta(session, model=None) -> dict | None:
    """The stream T / P / F that moved in the session's last measured run (``_streams``), or
    None: none measured, another model, or a later run the journal has that was not measured."""
    st = _S.get(session)
    d = st.delta if st is not None else None
    if d is None or (model and d.get("model") != model):
        return None
    run = ((journal.summary(d["model"]) or {}).get("run") or {}) if d.get("model") else {}
    if (run.get("seq") or 0) > d["seq"]:
        return None
    return dict(d)


def _spread(paths, k) -> list:
    """At most ``k`` of ``paths`` taking each object's (block's, stream's) in turn -- the first of
    each, then the second -- so an edit anywhere moves some of them (seen live: one
    block's temperature changed and the model run in Aspen: the first product stream's T / P / F
    did not move; 6 of these 12 did)."""
    by: dict = {}
    for p in paths:
        by.setdefault("\\".join(p.split("\\")[:4]), []).append(p)
    out, rank = [], 0
    while len(out) < k and any(len(v) > rank for v in by.values()):
        out += [v[rank] for v in by.values() if len(v) > rank][:k - len(out)]
        rank += 1
    return out


def peek(manager, session) -> dict | None:
    """PEEK_MAX results of the last after-read (``_spread``), read again now: {"paths", "was", "now",
    "changed", and the after-read's run record's "run" (id), "t", "seq"}; None when there is
    none to compare (a run made in Aspen's window). After a run whose results Aspen cleared
    (``cleared``), the paths that had none: results there now are a run's."""
    st = _S.get(session)
    last = st.last if st is not None else None
    app = manager.get_app(session) if last else None
    if app is None or st.model != manager.model_id(session):
        return None
    vals = last["vals"]
    paths = _spread(list(vals) if last.get("cleared") else [p for p, v in vals.items() if _num(v) is not None], PEEK_MAX)
    if not paths:
        return None
    try:
        now = []
        for p in paths:
            node = nodes.find(session, app, p)
            now.append(dispid.get(node, "Value") if node is not None else None)
    except Exception as exc:
        logger.debug("runlog: peek of %s failed (%r)", session, exc)
        return None
    was = [last["vals"][p] for p in paths]
    return {"paths": paths, "was": was, "now": now, "run": last.get("run"), "t": last.get("t"), "seq": last.get("seq"),
            "changed": any(_moved(p, a, b) is not None for p, a, b in zip(paths, was, now))}


def since_last(manager, session):
    """A run found after the fact (one made in Aspen's window) for ``after_run``: the inputs
    changed since the last run (journal.pending now) and, as the before-read, the session's last
    after-read -- ``blind`` (no delta; the after-read is taken all the same) when the journal
    has a run since that one (a loop's, Reinitialize); ``first`` when Aspen had cleared the
    results of that run (the ones found are compared with none). None: no after-read to start
    from."""
    try:
        model = manager.model_id(session)
        st = _S.get(session)
        last = st.last if st is not None and st.model == model else None
        pend = journal.pending(model) if model and last else None
        if pend is None:
            return None
        b = Before(session, model, int(pend.get("seq") or 0), _inputs(pend))
        b.actor, b.via = "external", "aspen"
        b.vals, b.first = dict(last["vals"]), bool(last.get("cleared"))
        b.core = min(len(b.vals), CORE_MAX)
        ran = (journal.summary(model) or {}).get("last_run_t") or 0.0
        b.blind = ran > (last.get("t") or 0.0) + 0.001         # a record's time is rounded to the ms
        return b
    except Exception as exc:
        logger.warning("runlog: the run found in %s not measured (%r)", session, exc)
        return None


def _fmt(v, digits=6) -> str:
    return f"{v:.{digits}g}" if isinstance(v, float) else "(none)" if v is None else str(v)[:40]


def item_text(it: dict) -> str:
    """A delta item as a line: "PRODUCT RES_TEMP 350 → 362 K" (as many digits as it takes to
    tell the two apart, up to 10)."""
    lab = journal.label(it.get("path"))
    owner = lab.get("stream") or lab.get("block") or ""
    u = f" {it['u']}" if it.get("u") else ""
    b, a, n = it.get("b"), it.get("a"), 6
    while n < 10 and _fmt(b, n) == _fmt(a, n):
        n += 1
    return f"{owner} {lab.get('field', '')} {_fmt(b, n)} → {_fmt(a, n)}{u}".strip()


def line(r: dict, top: int = 3) -> str:
    """A run record in one line: "Run #7: warn (2 warnings); 3 inputs changed since the last
    run, together; results moved: PRODUCT RES_TEMP 350 → 362 K, ..."."""
    counts = [f"{r[k]} {k}" for k in ("errors", "warnings") if r.get(k)]
    text = f"Run #{r['seq']}: " if r.get("seq") else "Run: "
    text += str(r.get("status")) + (f" ({', '.join(counts)})" if counts else "")
    inp = r.get("inputs")
    if isinstance(inp, dict):
        n = inp.get("n") or 0
        text += "; no input changed since the last run" if not n else \
            f"; {n} input{'s' * (n != 1)} changed since the last run" + (", together" if inp.get("joint") else "")
    d = r.get("delta")
    if isinstance(d, dict):
        err = " (the results of a run with errors)" if d.get("error") else ""
        if d.get("first"):
            text += "; the model's first results" + err
        elif d.get("items"):
            more = f" (+{d['n'] - top} more)" if (d.get("n") or 0) > top else ""
            text += f"; results moved{err}: " + ", ".join(item_text(i) for i in d["items"][:top]) + more
        else:
            text += f"; none of {d.get('read', 0)} results moved{err}"
    elif r.get("status") == "error":
        text += "; results cleared, not compared"
    return text
