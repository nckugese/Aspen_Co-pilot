"""Undo carried out (values written back, inverses of additions): a plan from
tools/undo.py checked against the live model, then written back -- every write journaled as the
user's, so an undo can itself be undone (a redo).

    c = undo.check(p, manager, session)                     # live: conflicts, already, gone; no write
    r = undo.apply(p, manager, session, on_conflict="skip")
    r = undo.revert(manager, session, group="g...")         # plan + check + apply (dry=True: no write)

check -- each step read live and held against the plan's ``expect`` (what the journal says is
there; the live read has the last word):
  * value / attr: numbers within undo.REL, strings exactly. The target there already: "already";
    anything else than expected: a conflict -- who and when from the plan's view of the journal,
    ``by`` None when the journal has nothing (changed in Aspen's window or by a calculation);
    the node gone: blocked "gone".
  * structure, the ports followed as the plan's own steps change them (a later step on a port
    expects what the earlier ones leave): a block / stream to remove that is gone: "already";
    of another type than recorded: blocked "type_mismatch"; still connected to a stream the plan
    does not take off first: conflict "foreign_connection" (removing it cuts that too), else the
    plan's own (used_since: edited since). A disconnect whose stream is off the port: "already".
    A reconnect: its stream or port gone: blocked; there already: "already"; the stream on
    another port of that direction now (connecting moves it off): conflict
    "displaced_taken" / "changed_since"; an outlet holding a stream the plan did not expect:
    conflict "port_taken" (connect_stream replaces a single outlet's stream).
  * a restore step (undoing a restore) is the ``restore`` hook's; steps after it are checked
    once it is done (their ``expect`` is the restored model's).

apply -- refused, nothing written or journaled, when the model is open in no session, the session
holds another model, or a program / an optimization holds it (activity.holder). While a
conflict stands nothing is written unless ``on_conflict`` says so: "abort" (the default; "ask"
too): status "conflict"; "skip": the other steps run; "force" / "overwrite": all run. Then, in
the plan's order (the newest change first):
  * the new group's restore point first when a structural step will run (intercept.restore_point,
    "before-structure"): redoing a structural undo is restoring that point;
  * value: "clear" writes "" (the field empties, back to its default, attr 11 0); a
    target value the clear does not give back is then written (approx "ue"). "write" writes the
    value, with the unit / basis only where they differ from now (SetValueAndUnit /
    SetValueUnitAndBasis); a unit the unit table does not know: the value alone (approx "unit"
    unless the read-back shows the unit back -- a basis written back brings its unit);
  * attr: the attribute written back;
  * remove_row / remove_element: a row the plan added taken out by its label (remove_row; one a
    list sharing its rows lost with the first: "already"), a subobject removed (remove_element);
  * remove_block / remove_stream / disconnect / reconnect: through the paths the AI's calls take
    (flowsheet_tools.remove_* / connect_stream; a port's Elements.Remove) and measured by the same
    probes (tools/probes.py with intercept.TOOLS' probe column), so they are journaled as the
    same ``remove`` / ``connect`` records;
  * each step read back: a value's value, unit, basis and ue give ``exact``, else ``approx``
    codes (value, unit, unit_roundoff, basis, ue, ue_unknown: its default equals the target, so
    it may have been a default), with the plan's own (unit_unknown, other_end_unknown ...);
  * last, the blocks / streams whose fields were written that were complete (COMPSTATUS without
    0x40) and are not now: ``side`` (a field that came with a change did not come back), their
    steps approximate.
Each step is a recording scope of its own -- actor ``actor`` (user), via ``via`` (window), tool
``revert``, the undo's group (revert_group: journal.GROUPS.revert, ``of`` the plan's group, else
the groups of the records it undoes, ``label`` that group's title; or ``into``, one the caller
names) and one call id --
whose last record carries ``revert_of`` (the plan's record ids of the step), ``exact`` and
``approx`` -- and ``redo`` true when the plan is itself a redo (the AI's brief says "redid"):
undo.plan of those records is the redo (its ``redo`` flag).

Result (JSON-safe): {"status": done | partial | conflict | refused | failed | nothing, "code"
(refused: no_session | wrong_model | edit_busy; conflict: conflicts | plan_changed), "text"
(English, one line), "session", "model", "group", "call", "of", "redo", "checkpoint" (the
restore point made first: {"status", "id", "why", ...} or None), "steps": [{"key", "kind",
"path" | "name" | "block" / "port", "status": done | already | skipped | failed | blocked |
restore, "code", "exact", "approx", "now", "result", "records", "conflict", "checkpoint"}],
"conflicts", "blocked" (the plan's), "restore_before" (the plan's), "side", "n": {done, approx,
already, skipped, failed, blocked}, "refresh": topology | values | None}.

Stdlib only; COM only through the manager's app and the nodes it hands out. Never raises: an
unexpected error ends the undo "failed", with what was done up to it.
"""
from __future__ import annotations

import logging
import math

from tools import activity, dispid, flowsheet_tools, intercept, journal, knowledge_tools, nodes, probes, recorder
from tools import undo as U

logger = logging.getLogger(__name__)

STATUS, DEFAULT = 12, 10            # HAP_COMPSTATUS, HAP_VALUEDEFAULT
INCOMPLETE = 0x40                   # COMPSTATUS: inputs incomplete (tools/inputs_check.py)
ROUNDOFF = 1e-6                     # a value back within this after a unit conversion: unit_roundoff
TOOL = "revert"
LABEL_MAX, LABEL_SCAN = 40, 2000    # an undo group's label (the title of what it takes back); records searched for it
_MODES = {"abort": "abort", "ask": "abort", "skip": "skip", "force": "force", "overwrite": "force"}
_WRITE = frozenset({"value", "attr"})


# ---------------------------------------------------------------------------- small helpers
def _up(x) -> str:
    return U._up(x)


def _ok(res) -> bool:
    """set_node_value / set_node_attribute answered that it wrote."""
    return isinstance(res, str) and res.lstrip().startswith("Set")


def _numeric(v) -> bool:
    return U._num(v) is not None and not isinstance(v, bool)


def _got(now: dict, to: dict) -> bool:
    """``now`` holds the target: every key of ``to`` it read is equal, the value among them."""
    return isinstance(now, dict) and "value" in now and all(
        U._same(now[k], v) for k, v in (to or {}).items() if k in now)


def _agree(now: dict, expect: dict) -> bool:
    """``now`` is what was expected, on the keys both hold."""
    return all(U._same(now[k], v) for k, v in expect.items() if k in now)


def _where(s: dict) -> dict:
    return {k: s[k] for k in ("path", "attr", "name", "block", "port", "why") if s.get(k) is not None}


def _source(p: dict, model) -> tuple:
    """(of, label) of an undo's group header: ``of`` the plan's group, else the groups of the
    records it undoes -- one: its id, several: their ids, the newest first; ``label`` the first
    one's title (an untitled undo's own label: a redo names what was first done), cut to
    LABEL_MAX, from this process's groups or the journal's header; None when untitled."""
    of = p.get("group") or p.get("groups") or None
    if isinstance(of, (list, tuple)):
        of = list(dict.fromkeys(str(g) for g in of if g))
        of = of[0] if len(of) == 1 else of or None
    first = of if isinstance(of, str) else of[0] if of else None
    if not first:
        return of, None
    h = journal.GROUPS.known(first)
    if h is None and model:
        h = journal.find(model, first, scan=LABEL_SCAN)
    if not isinstance(h, dict) or h.get("kind") != "group":
        return of, None
    name = str(h.get("title") or (h.get("label") if h.get("source") == "revert" else "") or "").strip()
    return of, (name if len(name) <= LABEL_MAX else name[:LABEL_MAX - 1] + "…") or None


def revert_group(p: dict, session=None, actor: str = "user", model=None, t=None) -> dict | None:
    """The change group an undo of plan ``p`` journals into: a new journal.GROUPS.revert group,
    its ``of`` and ``label`` from _source (``model``: the plan's, else this one)."""
    of, label = _source(p, p.get("model") or model)
    return journal.GROUPS.revert(of=of, label=label, session=session, actor=actor, t=t)


def _obj_of(path) -> tuple | None:
    """(kind, NAME) of the block or stream a field belongs to."""
    lab = journal.label(path)
    for k in ("block", "stream"):
        if lab.get(k):
            return k, lab[k]
    return None


def _conflict(s: dict, now, code: str, **more) -> dict:
    """A step's conflict: the plan's journal view of who changed it (``by`` None: not in the
    journal -- Aspen's window or a calculation), with what is there now."""
    c = {k: v for k, v in (s.get("conflict") or {}).items() if k != "now"}
    if not s.get("conflict"):
        c["by"] = None
    c["code"] = code if code != "changed_since" or not c.get("code") else c["code"]
    c.update(now=now, expect=s.get("expect"), **more)
    return c


class _Live:
    """The session's model as check() and apply() read it: nodes by path, and the ports as the
    plan's steps leave them (``ports``: (BLOCK, PORT) -> [streams]; read on first use)."""

    def __init__(self, manager, session):
        self.m, self.session = manager, session
        self.app = manager.get_app(session)
        self.ports: dict = {}
        self.removed: set = set()          # BLOCK names the plan's steps so far removed
        self._tree = None

    @property
    def tree(self):
        if self._tree is None:
            self._tree = self.app.Tree
        return self._tree

    def node(self, path):
        return nodes.find(self.session, self.app, path)

    def find(self, path):
        return probes._find(self.tree, path)

    def obj(self, kind, name):
        """(the name as Aspen has it, the node) of a block / stream, else (name, None)."""
        folder = r"\Data\Blocks" if kind == "block" else r"\Data\Streams"
        for n in dict.fromkeys((str(name), str(name).upper())):
            node = self.find(f"{folder}\\{n}")
            if node is not None:
                return n, node
        return str(name), None

    def port(self, block, port):
        """The port's streams as the plan has left them so far; None when it is not there."""
        k = (_up(block), _up(port))
        if k[0] in self.removed:
            return None
        if k not in self.ports:
            _, node = probes._port(self.tree, self.obj("block", block)[0], port)
            self.ports[k] = probes._names(node) if node is not None else None
        return self.ports[k]

    def taken_off(self, block, port, stream) -> bool:
        """The plan's steps so far took ``stream`` off that port (or removed its block)."""
        if _up(block) in self.removed:
            return True
        sim = self.ports.get((_up(block), _up(port)))
        return sim is not None and not U._has(sim, stream)

    def ends(self, stream) -> list | None:
        """[(block, port)] the stream is on now (None: unreadable)."""
        return probes._ends(self.tree, self.obj("stream", stream)[0])[1]

    def compstatus(self, kind, name):
        _, node = self.obj(kind, name)
        if node is None:
            return None
        try:
            v = dispid.get(node, "AttributeValue", STATUS)
            return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        except Exception:
            return None


# ---------------------------------------------------------------------------- check
def _session_of(manager, p: dict, session=None):
    """``session`` when given, else one of the steps' own sessions, else any session holding
    the plan's model (the window's tab says which: pass it)."""
    if session:
        return session
    names = [s.get("session") for s in p.get("steps") or () if s.get("session")]
    try:
        names += list(manager.session_names())
    except Exception:
        pass
    for n in dict.fromkeys(names):
        try:
            if manager.get_app(n) is not None and manager.model_id(n) == p.get("model"):
                return n
        except Exception:
            continue
    return None


def check(p: dict, manager, session=None) -> dict:
    """The plan against the live model, writing nothing: {"session", "model", "steps": [{"key",
    "kind", "state": ok | already | conflict | blocked | restore | pending, "code", "now",
    "conflict"}] in the plan's order, "conflicts" (at most undo.CONFLICTS_MAX; "conflicts_more"),
    "n": {state: count}, "error" (no_session)}. Steps after a restore step are "pending": they
    are checked once it is done. Never raises."""
    session = _session_of(manager, p, session)
    out = {"session": session, "model": p.get("model"), "steps": [], "conflicts": [], "conflicts_more": 0, "n": {}}
    try:
        if session is None or manager.get_app(session) is None:
            out["error"] = "no_session"
            return out
        live = _Live(manager, session)
    except Exception as exc:
        out["error"] = f"no_session: {exc}"
        return out
    pending = False
    for s in p.get("steps") or ():
        c = {"state": "pending"} if pending else _check_step(live, s)
        pending = pending or s.get("kind") == "restore"
        out["steps"].append({"key": s.get("key"), "kind": s.get("kind"), **_where(s), **c})
    _tally(out)
    return out


def _tally(out: dict) -> None:
    conf = [{"key": c["key"], "kind": c["kind"], **_where(c), **c["conflict"]}
            for c in out["steps"] if c.get("state") == "conflict"]
    out["conflicts"] = conf[:U.CONFLICTS_MAX]
    out["conflicts_more"] = max(0, len(conf) - U.CONFLICTS_MAX)
    n = {}
    for c in out["steps"]:
        n[c["state"]] = n.get(c["state"], 0) + 1
    out["n"] = n


def _check_step(live: _Live, s: dict) -> dict:
    try:
        kind = s.get("kind")
        if kind in ("value", "attr"):
            return _check_field(live, s)
        if kind in ("remove_block", "remove_stream"):
            return _check_remove(live, s)
        if kind in ("remove_row", "remove_element"):
            if live.find(s["path"]) is None:
                return {"state": "already", "code": "gone"}
            if s.get("conflict"):
                return {"state": "conflict", "conflict": _conflict(s, None, s["conflict"].get("code"))}
            return {"state": "ok"}
        if kind == "disconnect":
            return _check_disconnect(live, s)
        if kind == "reconnect":
            return _check_reconnect(live, s)
        if kind == "restore":
            return {"state": "restore", "checkpoint": s.get("checkpoint")}
        return {"state": "blocked", "code": "unsupported"}
    except Exception as exc:
        logger.warning("undo: step %s not checked (%r)", s.get("key"), exc)
        if knowledge_tools.server_fault(exc):        # Aspen's internal fault (a Connections row by Item(i)):
            note = getattr(live.m, "note_fault", None)     # the session's runs would never return, so it
            if note is not None:                           # is flagged (aspen_manager.note_fault)
                note(live.session, exc, tool=TOOL)
        return {"state": "blocked", "code": "unreadable", "result": str(exc)[:journal.RESULT_MAX]}


def _read_field(live: _Live, s: dict, node) -> dict:
    if s.get("kind") == "attr":
        v = dispid.get(node, "AttributeValue", s.get("attr"))
        return {"value": None if v == "" else v}
    keys = set(s.get("to") or {}) | set(s.get("expect") or {})
    return recorder.read_state(node, unit="unit" in keys, basis="basis" in keys, ue=True)


def _check_field(live: _Live, s: dict) -> dict:
    node = live.node(s["path"])
    if node is None:
        return {"state": "blocked", "code": "gone"}
    now = _read_field(live, s, node)
    if _got(now, s.get("to") or {}):
        return {"state": "already", "now": now}
    exp = s.get("expect")
    if exp is not None and not _agree(now, exp):
        return {"state": "conflict", "now": now, "conflict": _conflict(s, now, "changed_since")}
    return {"state": "ok", "now": now}


def _check_remove(live: _Live, s: dict) -> dict:
    kind = "block" if s["kind"] == "remove_block" else "stream"
    name, node = live.obj(kind, s.get("name"))
    if node is None:
        return {"state": "already", "code": "gone"}
    typ = probes._type(node)
    if s.get("type") and typ and _up(typ) != _up(s["type"]):
        return {"state": "blocked", "code": "type_mismatch", "now": {"type": typ}}
    foreign = []
    if kind == "block":
        conn = live.find(rf"\Data\Blocks\{name}\Connections")
        els = conn.Elements if conn is not None else None
        for i in range(els.Count if els is not None else 0):
            c = els.Item(i)
            st, port = str(dispid.get(c, "Name")), str(dispid.get(c, "Value") or "")
            if not live.taken_off(name, port, st):
                foreign.append({"stream": st, "port": port})
        live.removed.add(_up(name))                  # its ports go with it
    else:
        for b, port in live.ends(name) or ():
            if not live.taken_off(b, port, name):
                foreign.append({"block": b, "port": port})
        for k, v in live.ports.items():
            if v:
                live.ports[k] = [x for x in v if _up(x) != _up(name)]
    now = {"type": typ, "connections": foreign}
    if foreign:
        return {"state": "conflict", "now": now, "conflict": _conflict(s, now, "foreign_connection", connected=foreign)}
    if s.get("conflict"):
        return {"state": "conflict", "now": now, "conflict": _conflict(s, now, s["conflict"].get("code"))}
    return {"state": "ok", "now": now}


def _check_disconnect(live: _Live, s: dict) -> dict:
    cur = live.port(s["block"], s["port"])
    if cur is None:
        return {"state": "blocked", "code": "gone"}
    now = {"port": list(cur)}
    if not U._has(cur, s["name"]):
        return {"state": "already", "now": now}
    live.ports[(_up(s["block"]), _up(s["port"]))] = [x for x in cur if _up(x) != _up(s["name"])]
    return {"state": "ok", "now": now}


def _check_reconnect(live: _Live, s: dict) -> dict:
    name, block, port = s["name"], s["block"], s["port"]
    if live.obj("stream", name)[1] is None:
        return {"state": "blocked", "code": "gone"}
    cur = live.port(block, port)
    if cur is None:
        return {"state": "blocked", "code": "gone"}
    now = {"port": list(cur)}
    if U._has(cur, name):
        return {"state": "already", "now": now}
    way, here = U._way(port), (_up(block), _up(port))
    others = [{"block": b, "port": p} for b, p in live.ends(name) or ()
              if U._way(p) == way and (_up(b), _up(p)) != here and not live.taken_off(b, p, name)]
    exp = (s.get("expect") or {}).get("port")
    extra = U._minus(cur, exp) if exp is not None else list(cur)
    for o in others:                                 # connecting moves it off there
        o_cur = live.port(o["block"], o["port"])
        if o_cur is not None:
            live.ports[(_up(o["block"]), _up(o["port"]))] = [x for x in o_cur if _up(x) != _up(name)]
    live.ports[here] = list(cur) + [name]
    if others:
        now["on"] = others
        code = "displaced_taken" if s.get("why") == "displaced" else "changed_since"
        return {"state": "conflict", "now": now, "conflict": _conflict(s, now, code, on=others)}
    if way == "out" and extra:
        return {"state": "conflict", "now": now, "conflict": _conflict(s, now, "port_taken", streams=extra)}
    return {"state": "ok", "now": now}


# ---------------------------------------------------------------------------- apply
def apply(p: dict, manager, session=None, *, on_conflict: str = "abort", actor: str = "user",
          via: str | None = "window", checked: dict | None = None, restore=None, into=None) -> dict:
    """Carry out plan ``p`` (see the module docstring). ``checked``: check()'s result when the
    caller has it (fresh: it is what decides); ``restore(step, group, call) -> dict``: carries
    out a restore step (manager.restore's result; None: restore steps are left blocked
    "restore" and the steps after them skipped "after_restore"); ``into``: an existing change
    group (a dict or its id) to journal into instead of a new one -- "restore to before this
    group" undoes the values older than the restore point in the restore's own group. Never
    raises."""
    run = _Run(p, manager, session, _MODES.get(str(on_conflict or "abort").lower(), "abort"), actor, via, restore)
    run.into = into
    try:
        return run.go(checked)
    except Exception as exc:
        logger.error("undo of %s failed: %r", p.get("of"), exc, exc_info=True)
        run.res["error"] = str(exc)[:journal.RESULT_MAX]
        return run.finish("failed")


class _Run:
    def __init__(self, p, manager, session, mode, actor, via, restore):
        self.p, self.m, self.mode, self.actor, self.via, self.restore = p, manager, mode, actor, via, restore
        self.session = _session_of(manager, p, session)
        self.group = self.call = self.into = None
        self.live = None
        self.res = {"status": None, "code": None, "text": "", "session": self.session, "model": p.get("model"),
                    "group": None, "call": None, "of": list(p.get("of") or []), "redo": bool(p.get("redo")),
                    "checkpoint": None, "steps": [], "conflicts": [], "blocked": list(p.get("blocked") or []),
                    "restore_before": p.get("restore_before"), "side": [], "n": {}, "refresh": None}

    # -- gates
    def refused(self, code, text) -> dict:
        self.res.update(code=code, text=text)
        return self.finish("refused")

    def go(self, checked) -> dict:
        m, session = self.m, self.session
        if session is None or m.get_app(session) is None:
            return self.refused("no_session", "The model is not open in any session: open it to undo its changes.")
        if self.p.get("model") and m.model_id(session) != self.p["model"]:
            return self.refused("wrong_model", f"Session '{session}' holds another model than this undo's.")
        held = activity.holder(session)
        if held is not None:
            return self.refused("edit_busy", activity.refusal(held))
        c = checked if checked is not None and len(checked.get("steps") or ()) == len(self.p.get("steps") or ()) \
            else check(self.p, m, session)
        if c.get("error"):
            return self.refused("no_session", "The model is not open in any session: open it to undo its changes.")
        steps, states = list(self.p.get("steps") or ()), list(c["steps"])
        self.res["conflicts"] = list(c.get("conflicts") or ())
        if c.get("conflicts") and self.mode == "abort":
            self.res["steps"] = [self._view(s, st, "skipped" if st["state"] in ("ok", "conflict") else None)
                                 for s, st in zip(steps, states)]
            self.res.update(code="conflicts", text=_conflict_text(c))
            return self.finish("conflict")
        if not any(self._runs(st) or st["state"] == "restore" for st in states):
            self.res["steps"] = [self._view(s, st) for s, st in zip(steps, states)]
            return self.finish()
        self.group = self.into or revert_group(self.p, session, self.actor, m.model_id(session))
        self.call = journal.new_id("c")
        self.res.update(group=self.group.get("id") if isinstance(self.group, dict) else self.group, call=self.call)
        of = self.p.get("group") if self.into else (self.group or {}).get("of")
        act = activity.begin(self.actor, TOOL, session, phase="aspen", call=self.call, via=self.via,
                             target={"n": sum(self._runs(st) for st in states), "of": of or None})
        ended = "error"
        try:
            if any(self._runs(st) and s.get("kind") in U._STRUCT for s, st in zip(steps, states)):
                self._checkpoint()
            self.live = _Live(m, session)
            objs = {o: self.live.compstatus(*o) for o in {_obj_of(s["path"]) for s, st in zip(steps, states)
                                                          if s.get("kind") in _WRITE and self._runs(st)} if o}
            i = 0
            while i < len(steps):
                s, st = steps[i], states[i]
                if st["state"] == "restore":
                    done = self._restore(s, st)
                    rest = steps[i + 1:]
                    if not done:
                        self.res["steps"] += [self._view(x, {"state": "pending"}, "skipped", "after_restore")
                                              for x in rest]
                        break
                    later = check({**self.p, "steps": rest}, m, session)       # the restored model's turn
                    states[i + 1:] = later["steps"]
                    self.res["conflicts"] += later.get("conflicts") or []
                    self.live = _Live(m, session)
                elif self._runs(st):
                    self._step(s, st)
                else:
                    self.res["steps"].append(self._view(s, st))
                i += 1
            self._side(objs)
            ended = "ok"
        finally:
            activity.end(act, ended)
        return self.finish()

    def _runs(self, st) -> bool:
        return st["state"] == "ok" or (st["state"] == "conflict" and self.mode == "force")

    def _view(self, s, st, status=None, code=None) -> dict:
        state = st.get("state")
        status = status or {"already": "already", "blocked": "blocked", "conflict": "skipped", "ok": "skipped",
                            "pending": "skipped", "restore": "blocked"}.get(state, "skipped")
        v = {"key": s.get("key"), "kind": s.get("kind"), **_where(s), "status": status,
             "code": code or st.get("code") or ("conflict" if state == "conflict" else
                                                 "restore" if state == "restore" else None),
             "exact": None, "approx": [], "now": st.get("now"), "of": s.get("of")}
        if state == "conflict":
            v["conflict"] = st.get("conflict")
        if s.get("checkpoint"):
            v["checkpoint"] = s["checkpoint"]
        return {k: val for k, val in v.items() if val is not None or k in ("exact",)}

    # -- a restore point before the first structural step
    def _checkpoint(self) -> None:
        rp = intercept.restore_point(self.m, self.session, "before-structure", group=self.group, dedup=True,
                                     actor=self.actor, via=self.via, tool=TOOL, call=self.call)
        self.res["checkpoint"] = {k: rp[k] for k in ("status", "id", "tier", "state", "why", "est_s", "note")
                                  if rp.get(k) not in (None, "")}

    def _scope(self):
        s = recorder.scope(actor=self.actor, via=self.via, session=self.session, model=self.m.model_id(self.session),
                           group=self.group, call=self.call, tool=TOOL)
        s.manager = self.m
        return s

    # -- one step
    def _step(self, s, st) -> None:
        v = self._view(s, st, "done")
        v.pop("code", None)
        try:
            with self._scope() as sc:
                kind = s.get("kind")
                if kind == "value":
                    self._value(sc, s, st, v)
                elif kind == "attr":
                    self._attr(sc, s, v)
                else:
                    self._struct(sc, s, v)
        except Exception as exc:
            logger.warning("undo: step %s failed (%r)", s.get("key"), exc, exc_info=True)
            v.update(status="failed", code="error", result=str(exc)[:journal.RESULT_MAX], exact=False)
        self.res["steps"].append(v)

    def _flush(self, sc, s, v, last=True) -> None:
        kw = {"revert_of": s.get("of"), "redo": True if self.p.get("redo") else None}
        if last:
            kw.update(exact=bool(v.get("exact")), approx=v.get("approx") or None)
        recs = sc.flush(**kw)
        v.setdefault("records", []).extend(r.get("id") for r in recs if r.get("id"))

    def _value(self, sc, s, st, v) -> None:
        m, session, path, to = self.m, self.session, s["path"], s.get("to") or {}
        approx, now, unit = list(s.get("approx") or []), st.get("now") or {}, None
        want, alone = to.get("value"), False
        if s.get("how") == "clear":
            res = m.set_node_value(session, path, value="")
            if not _ok(res):                         # Aspen will not empty it: only a restore point can
                v.update(status="blocked", code="cannot_clear", result=str(res)[:journal.RESULT_MAX], exact=False)
                self._flush(sc, s, v)
                return
            if want is not None and not U._same(self._now(path, s).get("value"), want):
                self._flush(sc, s, v, last=False)        # the clear, a record of its own (its ue read)
                res = m.set_node_value(session, path, value=want)
                approx.append("ue")
        else:
            basis = None
            if _numeric(want):
                if to.get("unit") and not U._same(now.get("unit"), to["unit"]):
                    unit = to["unit"]
                if to.get("basis") is not None and "basis" in to and not U._same(now.get("basis"), to["basis"]):
                    basis = to["basis"]
            res = m.set_node_value(session, path, value=want, unit=unit, basis=basis)
            if unit and not _ok(res) and "does not fit" in str(res):
                unit, alone = None, True                 # a unit the table does not know: the value alone
                res = m.set_node_value(session, path, value=want, basis=basis)
        v["result"] = str(res)[:journal.RESULT_MAX]
        if not _ok(res):
            v.update(status="failed", code="write", exact=False)
            self._flush(sc, s, v)
            return
        got = self._now(path, s)
        codes = _differences(s, to, got, unit is not None, self._default(path) if "ue_unknown" in (
            s.get("maybe") or ()) and "ue" not in to else None)
        if alone and "unit" not in got:                  # the unit was not written and cannot be read
            approx.append("unit")                        # (read back, _differences says whether it came back)
        v["now"] = got
        v["approx"] = sorted(set(approx) | set(codes))
        v["exact"] = not v["approx"]
        self._flush(sc, s, v)

    def _attr(self, sc, s, v) -> None:
        to = s.get("to") or {}
        res = self.m.set_node_attribute(self.session, s["path"], s.get("attr"), to.get("value"))
        v["result"] = str(res)[:journal.RESULT_MAX]
        if not _ok(res):
            v.update(status="failed", code="write", exact=False)
        else:
            got = self._now(s["path"], s)
            v["now"] = got
            v["approx"] = sorted(set(s.get("approx") or []) | ({"value"} if not U._same(got.get("value"), to.get("value"))
                                                               else set()))
            v["exact"] = not v["approx"]
        self._flush(sc, s, v)

    def _now(self, path, s) -> dict:
        node = nodes.find(self.session, self.m.get_app(self.session), path)
        if node is None:
            return {}
        if s.get("kind") == "attr":
            val = dispid.get(node, "AttributeValue", s.get("attr"))
            return {"value": None if val == "" else val}
        to = s.get("to") or {}
        return recorder.read_state(node, unit="unit" in to, basis="basis" in to, ue=True)

    def _default(self, path):
        try:
            node = nodes.find(self.session, self.m.get_app(self.session), path)
            return None if node is None else dispid.get(node, "AttributeValue", DEFAULT)
        except Exception:
            return None

    # -- structure: the AI's tool paths, measured by the same probes
    def _measured(self, sc, tool, args, fn):
        spec = intercept.TOOLS.get(tool)
        p = probes.Probe(self.m, sc, tool, spec.probe if spec else None, args,
                         describe=lambda a: (intercept.target_of(tool, a), intercept.args_summary(a)))
        p.before()
        res = fn()
        p.done(res)
        return res

    def _struct(self, sc, s, v) -> None:
        live, kind, session = _Live(self.m, self.session), s["kind"], self.session
        if kind in ("remove_row", "remove_element"):     # a row (by its label) or a subobject the plan added
            folder, _, name = s["path"].rpartition("\\")
            names = probes._names(live.find(folder)) or []
            at = next((i for i, n in enumerate(names) if _up(n) == _up(name)), None)
            if at is None:                               # (a list sharing its rows lost it with the first)
                v.update(status="already", exact=True)
                return
            args = {"session_name": session, "aspen_path": folder}
            res = self._measured(sc, kind, dict(args, index=at) if kind == "remove_row" else dict(args, name=name),
                                 lambda: self.m.remove_row(session, folder, at) if kind == "remove_row"
                                 else self.m.remove_element(session, folder, name))
            ok = _Live(self.m, session).find(s["path"]) is None
        elif kind in ("remove_block", "remove_stream"):
            obj = "block" if kind == "remove_block" else "stream"
            name, node = live.obj(obj, s.get("name"))
            if node is None:
                v.update(status="already", exact=True)
                return
            fn = getattr(flowsheet_tools, kind)
            res = self._measured(sc, kind, {"session_name": session, f"{obj}_name": name},
                                 lambda: fn(self.m, session, name))
            ok = _Live(self.m, session).obj(obj, name)[1] is None
        else:
            stream = live.obj("stream", s["name"])[0]
            block = live.obj("block", s["block"])[0]
            port, pnode = probes._port(live.tree, block, s["port"])
            if pnode is None:
                v.update(status="failed", code="gone", exact=False)
                return
            args = {"session_name": session, "block_name": block, "port_name": port, "stream_name": stream}
            if kind == "disconnect":
                cur = probes._names(pnode) or []
                name = next((x for x in cur if _up(x) == _up(stream)), None)
                if name is None:
                    v.update(status="already", exact=True)
                    return
                path = rf"\Data\Blocks\{block}\Ports\{port}"
                res = self._measured(sc, "connect_stream", args, lambda: self.m.remove_element(session, path, name))
            else:
                res = self._measured(sc, "connect_stream", args,
                                     lambda: flowsheet_tools.connect_stream(self.m, session, block, stream, port))
            on = U._has(_Live(self.m, session).port(block, port) or [], stream)
            ok = on if kind == "reconnect" else not on
        v["result"] = str(res)[:journal.RESULT_MAX]
        if not ok:
            v.update(status="failed", code="not_done", exact=False)
        else:
            v["approx"] = sorted(set(s.get("approx") or []))
            v["exact"] = not v["approx"]
        self._flush(sc, s, v)

    # -- a restore step: the caller's
    def _restore(self, s, st) -> bool:
        v = self._view(s, st, "blocked", "restore")
        if self.restore is None:
            self.res["steps"].append(v)
            return False
        try:
            r = self.restore(s, self.group, self.call) or {}
        except Exception as exc:
            r = {"status": "failed", "text": str(exc)}
        v.update(status="done" if r.get("status") == "done" else "failed", result=str(r.get("text") or "")[:300],
                 exact=r.get("status") == "done", code=None if r.get("status") == "done" else r.get("code") or "restore")
        v = {k: val for k, val in v.items() if val is not None or k == "exact"}
        self.res["steps"].append(v)
        return r.get("status") == "done"

    # -- completeness after all
    def _side(self, before: dict) -> None:
        for o, st0 in before.items():
            st1 = self.live.compstatus(*o) if self.live is not None else None
            if isinstance(st0, int) and isinstance(st1, int) and not st0 & INCOMPLETE and st1 & INCOMPLETE:
                self.res["side"].append({"kind": o[0], "name": o[1], "before": st0, "after": st1})
                for v in self.res["steps"]:
                    if v.get("status") == "done" and v.get("path") and _obj_of(v["path"]) == o:
                        v["approx"] = sorted(set(v.get("approx") or []) | {"side"})
                        v["exact"] = False

    # -- the result
    def finish(self, status=None) -> dict:
        n = {"done": 0, "approx": 0, "already": 0, "skipped": 0, "failed": 0, "blocked": len(self.res["blocked"])}
        for v in self.res["steps"]:
            k = v.get("status")
            if k == "restore":
                k = "blocked"
            n[k] = n.get(k, 0) + 1
            n["approx"] += k == "done" and not v.get("exact")
        self.res["n"] = n
        if status is None:
            bad = n["skipped"] + n["failed"] + n["blocked"]
            status = ("done" if not bad else "partial") if n["done"] else "failed" if n["failed"] else "nothing"
        self.res["status"] = status
        kinds = {v.get("kind") for v in self.res["steps"] if v.get("status") == "done"}
        self.res["refresh"] = "topology" if kinds & (U._STRUCT | {"restore"}) else "values" if kinds else None
        if not self.res["text"]:
            self.res["text"] = _text(self.res)
        return journal.clean(self.res)


def _differences(s, to, got, unit_written, default) -> list:
    """What the read-back shows did not come back (approx codes)."""
    codes = []
    if not got:
        return ["value"]
    if not U._same(got.get("value"), to.get("value")):
        x, y = U._num(got.get("value")), U._num(to.get("value"))
        close = x is not None and y is not None and math.isfinite(x) and math.isfinite(y) and \
            math.isclose(x, y, rel_tol=ROUNDOFF)
        codes.append("unit_roundoff" if close and unit_written else "value")
    for k in ("unit", "basis"):
        if k in to and k in got and not U._same(got[k], to[k]):
            codes.append(k)
    if "ue" in to and to["ue"] is not None and "ue" in got and got["ue"] != to["ue"]:
        codes.append("ue")
    elif default is not None and U._same(default, to.get("value")):
        codes.append("ue_unknown")
    return codes


def _conflict_text(c: dict) -> str:
    n = len(c.get("conflicts") or ()) + (c.get("conflicts_more") or 0)
    return f"Nothing undone: {n} field{'s' * (n != 1)} changed since (choose to skip or overwrite)."


def _text(r: dict) -> str:
    n = r.get("n") or {}
    st = r.get("status")
    if st in ("refused", "conflict"):
        return r.get("text") or st
    bits = []
    if n.get("done"):
        bits.append(f"undid {n['done']} change{'s' * (n['done'] != 1)}"
                    + (f" ({n['approx']} approximately)" if n.get("approx") else ""))
    for k, word in (("already", "already as they were"), ("skipped", "skipped"), ("failed", "failed"),
                    ("blocked", "need a restore point")):
        if n.get(k):
            bits.append(f"{n[k]} {word}")
    if r.get("side"):
        bits.append("inputs of " + ", ".join(o["name"] for o in r["side"][:3]) + " are incomplete now")
    s = "; ".join(bits) or "nothing to undo"
    return s[:1].upper() + s[1:] + "."


# ---------------------------------------------------------------------------- one call
def revert(manager, session=None, model=None, ids=None, group=None, *, on_conflict: str = "abort",
           dry: bool = False, seen=None, actor: str = "user", via: str | None = "window", restore=None,
           into=None, after=None) -> dict:
    """Plan (from the journal), check and -- unless ``dry`` -- apply the undo of records ``ids``
    / change group ``group`` of ``model`` (default: the session's). Returns {"plan":
    undo.preview(plan), "check": check()'s, "result": apply()'s or None}. ``seen``: the step
    keys of a preview the user confirmed, or their undo.sig (the preview's ``sig``) -- a plan
    that differs now (the model changed meanwhile) is not applied: result status "conflict",
    code "plan_changed". ``after``: a record id (a restore's) -- only records newer than it
    count as changed since: "restore to before this group" undoes, right after the restore,
    the values the restore point holds, and what the restore took back is no conflict. Never
    raises."""
    try:
        if model is None and session is not None:
            model = manager.model_id(session)
        if after:
            records, later = U.collect(model, ids, group)
            cut = next((U._rk(r) for r in later if r.get("id") == after), None)
            if cut is not None:
                later = [r for r in later if U._rk(r) > cut]
            p = U.plan(model, ids=ids, group=group, records=records, later=later)
        else:
            p = U.plan(model, ids=ids, group=group)
        c = check(p, manager, session)
        out = {"plan": U.preview(p), "check": c, "result": None}
        if dry:
            return out
        if seen is not None and (U.sig(p) != seen if isinstance(seen, str)
                                 else [s.get("key") for s in p.get("steps") or ()] != list(seen)):
            r = _Run(p, manager, session, "abort", actor, via, restore)
            r.res.update(code="plan_changed", text="The model changed since the preview: look at the undo again.",
                         conflicts=c.get("conflicts") or [])
            out["result"] = r.finish("conflict")
            return out
        out["result"] = apply(p, manager, session, on_conflict=on_conflict, actor=actor, via=via, checked=c,
                              restore=restore, into=into)
        return out
    except Exception as exc:
        logger.error("undo: revert of %s / %s failed: %r", ids, group, exc, exc_info=True)
        return {"plan": None, "check": None, "result": {"status": "failed", "text": str(exc)[:journal.RESULT_MAX]}}
