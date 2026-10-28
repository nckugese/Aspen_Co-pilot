"""What moved enough to tell: the thresholds a result has to pass to show as a
result tag on the flowsheet, and the effects of a run built from what was measured.

    notable.CATALOG                              # catalog.notable: the window reads the same numbers
    notable.kind(path, unit)                     # frac | flow | temp | pres | duty | other
    notable.notable(b, a, kind, unit)            # whether b -> a is worth a tag
    notable.build(run=..., watch=..., delta=..., seg=...)   # tab.run.effects / sess.effects

The thresholds: a temperature by its absolute change (0.5 K, a Fahrenheit or Rankine change scaled),
a pressure by the relative change of the absolute pressure (a gauge unit counts the atmosphere), a
fraction by its absolute change (0.001), anything else by its relative change (0.5 %). A text that
changed is notable; a value that appeared or went away is not compared.

The effects: ``items`` -- the watched results first (``watch[0]`` the goal, always kept
while its value after is a number; a watched result with none before -- an object the proposal
made -- kept with ``b`` None), then the run record's delta items (runlog: product streams
first; "small" ones left out) that are notable, at most ITEMS_MAX; ``more`` the notable ones left
out; ``seg`` {stream: {"f" | "t": [before, after], "u": {key: unit}, "new": true}} -- the streams
whose total flow or temperature moved notably, or that are new; ``changed`` the
objects changed for the run, the earliest first -- where the window's causal paths start. Pure: no
COM, no I/O, no clock.
"""
from __future__ import annotations

import math

TEMP_ABS_K = 0.5          # a temperature change smaller than this (in K) is no change worth a tag
REL = 0.005               # ... a relative change of anything else (a pressure: of its absolute value)
FRAC_ABS = 0.001          # ... the absolute change of a fraction
ITEMS_MAX = 6             # results one run's effects keep
CHANGED_MAX = 12          # objects changed for a run its effects keep (where a path starts)
CATALOG = {"temp_abs_K": TEMP_ABS_K, "rel": REL, "frac_abs": FRAC_ABS}

_F_UNITS = ("F", "R", "DEGF", "DEGR")
_TEMP_UNITS = ("K", "C", "F", "R", "DEGC", "DEGF", "DEGK", "DEGR")
_GAUGE = {"psig": 14.6959, "barg": 1.01325, "kpag": 101.325, "mpag": 0.101325, "atmg": 1.0,
          "kg/sqcmg": 1.03323, "mbarg": 1013.25}
_PRES_UNITS = ("bar", "atm", "pa", "kpa", "mpa", "psi", "psia", "mmhg", "torr", "n/sqm", "kg/sqcm", "mbar",
               "in-hg", "in-water", "mm-water", "lbf/sqft", "gpa") + tuple(_GAUGE)
_DUTY_UNITS = ("w", "kw", "mw", "gw", "cal/sec", "kcal/hr", "mmkcal/hr", "gcal/hr", "btu/hr", "mmbtu/hr",
               "kj/hr", "mj/hr", "gj/hr", "j/sec", "hp")


def _num(x):
    if isinstance(x, bool) or x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def field(path: str) -> str:
    """The field a result path names: the part after ``Output`` (``RES_TEMP``, ``MASSFRAC``), else
    its last part, upper case."""
    parts = [p for p in str(path or "").split("\\") if p]
    up = [p.upper() for p in parts]
    if "OUTPUT" in up and up.index("OUTPUT") + 1 < len(up):
        return up[up.index("OUTPUT") + 1]
    return up[-1] if up else ""


def kind(path: str, unit=None) -> str:
    """frac | flow | temp | pres | duty | other, by the field's name, else its unit."""
    f, u = field(path), str(unit or "").strip()
    if "FRAC" in f:
        return "frac"
    if "TEMP" in f:
        return "temp"
    if "PRES" in f:
        return "pres"
    if "DUTY" in f or f in ("QCALC", "QNET", "NET_DUTY", "HDUTY"):
        return "duty"
    if "FLOW" in f or "FLMX" in f:
        return "flow"
    ul = u.lower()
    if u.upper() in _TEMP_UNITS:
        return "temp"
    if ul in _PRES_UNITS:
        return "pres"
    if ul in _DUTY_UNITS:
        return "duty"
    return "other"


def _abs_pres(v: float, unit) -> float:
    return v + _GAUGE.get(str(unit or "").strip().lower(), 0.0)


def notable(b, a, k: str | None = None, unit=None, path: str | None = None) -> bool:
    """Whether a result that went from ``b`` to ``a`` moved enough to tell (``k``: its kind, else
    taken from ``path`` and ``unit``)."""
    x, y = _num(b), _num(a)
    if x is None or y is None:
        if x is None and y is None:
            return b != a and b not in (None, "") and a not in (None, "")
        return False
    k = k or kind(path or "", unit)
    d = abs(y - x)
    if k == "frac":
        return d >= FRAC_ABS - 1e-12
    if k == "temp":
        scale = 1.8 if str(unit or "").strip().upper() in _F_UNITS else 1.0
        return d / scale >= TEMP_ABS_K - 1e-12
    if k == "pres":
        x, y = _abs_pres(x, unit), _abs_pres(y, unit)
    big = max(abs(x), abs(y))
    return big > 0 and abs(y - x) / big >= REL - 1e-12


def key_of(path: str) -> str | None:
    """The object a result belongs to: "stream:NAME" | "block:NAME", or None."""
    parts = [p for p in str(path or "").split("\\") if p]
    if len(parts) >= 3 and parts[0].lower() == "data":
        kind_ = {"streams": "stream", "blocks": "block"}.get(parts[1].lower())
        if kind_:
            return f"{kind_}:{parts[2].upper()}"
    return None


def _plain(x):
    f = _num(x)
    return x if f is None else f


def seg(values0: dict | None, values1: dict | None) -> dict:
    """The streams whose total flow or temperature moved notably between two of the window's stream
    values ({stream: {"t" | "p" | "f": [value, unit]}}), and the new ones (none before, a flow now):
    {stream: {"f"?: [b, a], "t"?: [b, a], "u": {key: unit}, "new"?: true}}."""
    out = {}
    v0, v1 = values0 or {}, values1 or {}
    for name, now in v1.items():
        if not isinstance(now, dict):
            continue
        was = v0.get(name) if isinstance(v0.get(name), dict) else None
        row, units = {}, {}
        if not was:
            f = now.get("f")
            if isinstance(f, list) and f and _num(f[0]) is not None and _num(f[0]) > 0:
                row = {"f": [None, _num(f[0])], "new": True}
                units["f"] = f[1] if len(f) > 1 else None
        else:
            for k, kk in (("f", "flow"), ("t", "temp")):
                b, a = was.get(k), now.get(k)
                if not (isinstance(b, list) and isinstance(a, list) and b and a):
                    continue
                ub, ua = (b[1] if len(b) > 1 else None), (a[1] if len(a) > 1 else None)
                if ub and ua and ub != ua:
                    continue
                if notable(b[0], a[0], kk, ua or ub):
                    row[k] = [_plain(b[0]), _plain(a[0])]
                    units[k] = ua or ub
        if row:
            u = {k: v for k, v in units.items() if v}
            if u:
                row["u"] = u
            out[name] = row
    return out


def seg_of_delta(d: dict | None) -> dict:
    """``seg`` from the session's run_delta (runlog.last_delta: {"s": {stream: {key: [b, a]}}, "u"}):
    the stream flows and temperatures that moved notably."""
    out = {}
    s, units = (d or {}).get("s") or {}, (d or {}).get("u") or {}
    for name, ks in s.items():
        if not isinstance(ks, dict):
            continue
        row, u = {}, {}
        for k, kk in (("f", "flow"), ("t", "temp")):
            pr = ks.get(k)
            unit = (units.get(name) or {}).get(k)
            if isinstance(pr, list) and len(pr) >= 2 and notable(pr[0], pr[1], kk, unit):
                row[k] = [_plain(pr[0]), _plain(pr[1])]
                if unit:
                    u[k] = unit
        if row:
            if u:
                row["u"] = u
            out[name] = row
    return out


def build(run: str | None, seq, at: float, watch=None, delta: dict | None = None, seg_: dict | None = None,
          joint_outside: bool = False, items_max: int = ITEMS_MAX, changed=None) -> dict:
    """A run's effects (tab.run.effects, sess.effects): ``watch`` [{path, label?, goal, b, a, u}] (b / a
    a value, or [value, unit]), ``delta`` the run record's (runlog), ``seg_`` (seg / seg_of_delta),
    ``changed`` the objects changed for it, the earliest first (where a result's path
    starts; at most CHANGED_MAX). {"run", "seq", "at", "joint_outside", "more", "items": [{key, path, label?,
    b, a, u, kind, goal, src}], "seg", "changed"}."""
    items, seen, more = [], set(), 0

    def val(x):
        return _plain(x[0]) if isinstance(x, list) and x else _plain(x)

    def unit_of(*xs):
        for x in xs:
            if isinstance(x, list) and len(x) > 1 and x[1]:
                return x[1]
        return None

    for w in watch or ():
        if not isinstance(w, dict) or not w.get("path") or w["path"] in seen:
            continue
        b, a = val(w.get("b")), val(w.get("a"))
        if _num(a) is None:
            continue
        if _num(b) is None:                          # (a result of an object the proposal made: its value alone)
            b = None
        u = w.get("u") or unit_of(w.get("a"), w.get("b"))
        k = kind(w["path"], u)
        if not w.get("goal") and b is not None and not notable(b, a, k, u):
            continue
        seen.add(w["path"])
        it = {"key": key_of(w["path"]), "path": w["path"], "b": b, "a": a, "u": u, "kind": k,
              "goal": bool(w.get("goal")), "src": "watch"}
        if w.get("label"):
            it["label"] = w["label"]
        items.append(it)
    for d in (delta or {}).get("items") or ():
        p = d.get("path") if isinstance(d, dict) else None
        if not p or p in seen or d.get("small"):
            continue
        k = kind(p, d.get("u"))
        if not notable(d.get("b"), d.get("a"), k, d.get("u")):
            continue
        seen.add(p)
        if len(items) >= items_max:
            more += 1
            continue
        items.append({"key": key_of(p), "path": p, "b": _plain(d.get("b")), "a": _plain(d.get("a")),
                      "u": d.get("u"), "kind": k, "goal": False, "src": "delta"})
    if len(items) > items_max:                       # (watched results past the cap: the goal stays)
        more += len(items) - items_max
        items = items[:items_max]
    return {"run": run, "seq": seq, "at": round(float(at), 3), "joint_outside": bool(joint_outside), "more": more,
            "items": items, "seg": seg_ or {}, "changed": list(dict.fromkeys(k for k in changed or () if k))[:CHANGED_MAX]}


def changed_of(inputs) -> list[str]:
    """The objects a run record's ``inputs`` changed (runlog: value items by path, structure by its
    target), in their order: "block:NAME" / "stream:NAME"."""
    out = []
    if not isinstance(inputs, dict):
        return out
    for o in inputs.get("objs") or ():
        k = o.get("kind") if isinstance(o, dict) else None
        if k in ("block", "stream") and o.get("name"):
            out.append(f"{k}:{str(o['name']).upper()}")
        elif isinstance(o, dict) and o.get("stream"):
            out.append(f"stream:{str(o['stream']).upper()}")
        elif isinstance(o, dict):
            out.append(key_of(o.get("path")))
    for it in inputs.get("items") or ():
        out.append(key_of(it.get("path")) if isinstance(it, dict) else None)
    return list(dict.fromkeys(k for k in out if k))[:CHANGED_MAX]
