"""Match-suggestion runner — expanded transshipment MILP, run in a subprocess like pinch_runner.py.

Given the same thermal stream table as pinch_runner.py, computes the problem-table
cascade, splits the problem at the pinch(es), and solves the minimum-number-of-matches
MILP (Papoulias & Grossmann, 1983) per subnetwork with scipy's HiGHS. Integer-cut
enumeration then lists ALL alternative optimal match sets (and optionally sets with up
to `extra_units` more matches), so match selection is provably exhaustive — engineering
judgment (which alternative to implement) is applied on a complete menu.

    uv run --python 3.14 --with OpenPinch==0.4.5 --no-project python tools/pinch_matches_runner.py < job.json

Job format (superset of pinch_runner's):
    {
      "streams": [...],                # same schema as pinch_analysis
      "dt_cont_default": 5.0,
      "forbidden_pairs": [["ROUT-COOL", "C1-REB"], ...],   # hot name, cold name
      "weights": {"ROUT-COOL|C1-REB": 3.0, ...},           # implementation difficulty
      "extra_units": 0,                # also enumerate solutions with up to N*+extra matches
      "n_alternatives": 8              # cap per subnetwork
    }
"""
from __future__ import annotations

import json
import sys
import traceback

import numpy as np
from scipy.optimize import LinearConstraint, milp
from scipy.optimize import Bounds

ISO_SPAN_C = 1.0
TOL = 1e-6
HOT_UTIL = "HOT-UTILITY"
COLD_UTIL = "COLD-UTILITY"


def _prep_streams(raw_streams, dt_default):
    """Normalize to (name, kind, t_hi_shifted, t_lo_shifted, cp) in shifted temps."""
    hots, colds = [], []
    for raw in raw_streams:
        name = raw["name"]
        ts, tt = float(raw["t_supply"]), float(raw["t_target"])
        q = abs(float(raw["heat_flow_kw"]))
        dt = float(raw.get("dt_cont", dt_default))
        if ts == tt:
            typ = (raw.get("type") or "").lower()
            if typ == "hot":
                tt = ts - ISO_SPAN_C
            elif typ == "cold":
                tt = ts + ISO_SPAN_C
            else:
                raise ValueError(f"stream '{name}': isothermal needs type='hot'/'cold'")
        if ts > tt:  # hot: shift down
            hi, lo = ts - dt, tt - dt
            hots.append({"name": name, "hi": hi, "lo": lo, "cp": q / (ts - tt)})
        else:        # cold: shift up
            hi, lo = tt + dt, ts + dt
            colds.append({"name": name, "hi": hi, "lo": lo, "cp": q / (tt - ts)})
    return hots, colds


def _intervals(hots, colds):
    temps = sorted({s[k] for s in hots + colds for k in ("hi", "lo")}, reverse=True)
    return [(temps[i], temps[i + 1]) for i in range(len(temps) - 1)]


def _load(stream, thi, tlo):
    """Heat of `stream` inside interval (thi, tlo) in shifted temps."""
    ov = max(0.0, min(stream["hi"], thi) - max(stream["lo"], tlo))
    return stream["cp"] * ov


def _cascade(hots, colds, ivals):
    surplus = []
    for (thi, tlo) in ivals:
        s = sum(_load(h, thi, tlo) for h in hots) - sum(_load(c, thi, tlo) for c in colds)
        surplus.append(s)
    run, r = 0.0, []
    for s in surplus:
        run += s
        r.append(run)
    qh = max(0.0, -min(r)) if r else 0.0
    resid = [qh + x for x in r]            # residual leaving each interval
    qc = resid[-1] if resid else qh
    total = sum(abs(s) for s in surplus) or 1.0
    pinch_after = [k for k, x in enumerate(resid[:-1]) if abs(x) <= TOL * total]
    return qh, qc, resid, pinch_after


def _solve_min_matches(hot_loads, cold_loads, weights, forbidden, extra_units, n_alt):
    """Min-matches MILP on one subnetwork + integer-cut enumeration.

    hot_loads/cold_loads: {name: [q_k per interval]} (kW). Returns list of solutions.
    """
    hn, cn = list(hot_loads), list(cold_loads)
    K = len(next(iter(hot_loads.values()))) if hot_loads else 0
    pairs = [(i, j) for i in hn for j in cn if (i, j) not in forbidden]
    if not pairs or K == 0:
        return {"n_min": 0, "alternatives": []}

    tot_h = {i: sum(hot_loads[i]) for i in hn}
    tot_c = {j: sum(cold_loads[j]) for j in cn}
    # variables: y_ij | q_ijk (j demand>0 intervals) | R_ik (k=0..K-1, R_{i,K-1}=0 enforced)
    y_idx = {p: n for n, p in enumerate(pairs)}
    q_idx, n = {}, len(pairs)
    for (i, j) in pairs:
        for k in range(K):
            if cold_loads[j][k] > TOL:
                q_idx[(i, j, k)] = n
                n += 1
    r_idx = {}
    for i in hn:
        for k in range(K):
            r_idx[(i, k)] = n
            n += 1

    A, lb, ub = [], [], []

    def row():
        return np.zeros(n)

    # hot cascade: R_{i,k} - R_{i,k-1} + sum_j q_ijk = QH_{i,k}
    for i in hn:
        for k in range(K):
            a = row()
            a[r_idx[(i, k)]] = 1.0
            if k > 0:
                a[r_idx[(i, k - 1)]] = -1.0
            for j in cn:
                if (i, j, k) in q_idx:
                    a[q_idx[(i, j, k)]] = 1.0
            A.append(a); lb.append(hot_loads[i][k]); ub.append(hot_loads[i][k])
    # cold balance: sum_i q_ijk = QC_{j,k}
    for j in cn:
        for k in range(K):
            if cold_loads[j][k] > TOL:
                a = row()
                for i in hn:
                    if (i, j, k) in q_idx:
                        a[q_idx[(i, j, k)]] = 1.0
                A.append(a); lb.append(cold_loads[j][k]); ub.append(cold_loads[j][k])
    # linking: sum_k q_ijk - U_ij y_ij <= 0
    for (i, j) in pairs:
        a = row()
        got = False
        for k in range(K):
            if (i, j, k) in q_idx:
                a[q_idx[(i, j, k)]] = 1.0
                got = True
        if not got:
            continue
        a[y_idx[(i, j)]] = -min(tot_h[i], tot_c[j])
        A.append(a); lb.append(-np.inf); ub.append(0.0)
    # closure: R_{i,K-1} = 0
    for i in hn:
        a = row()
        a[r_idx[(i, K - 1)]] = 1.0
        A.append(a); lb.append(0.0); ub.append(0.0)

    c = np.zeros(n)
    for p, idx in y_idx.items():
        c[idx] = float(weights.get(p, 1.0))
    integrality = np.zeros(n)
    v_ub = np.full(n, np.inf)
    for idx in y_idx.values():
        integrality[idx] = 1
        v_ub[idx] = 1.0
    bounds = Bounds(np.zeros(n), v_ub)

    cuts_A, cuts_ub = [], []
    solutions, n_min = [], None
    while len(solutions) < n_alt:
        cons = [LinearConstraint(np.array(A), np.array(lb), np.array(ub))]
        if cuts_A:
            cons.append(LinearConstraint(np.array(cuts_A), -np.inf, np.array(cuts_ub)))
        res = milp(c=c, constraints=cons, integrality=integrality, bounds=bounds)
        if not res.success:
            break
        chosen = [p for p, idx in y_idx.items() if res.x[idx] > 0.5]
        obj = sum(weights.get(p, 1.0) for p in chosen)
        if n_min is None:
            n_min = obj
        if obj > n_min + extra_units + TOL:
            break
        matches = []
        for (i, j) in chosen:
            duty = sum(res.x[q_idx[(i, j, k)]] for k in range(K) if (i, j, k) in q_idx)
            if duty > 1e-4:
                matches.append({
                    "hot": i, "cold": j, "duty_kw": round(duty, 1),
                    "is_utility": i == HOT_UTIL or j == COLD_UTIL,
                })
        solutions.append({"units": len(chosen), "weight": round(obj, 2), "matches": matches})
        cut = np.zeros(n)
        for p in chosen:
            cut[y_idx[p]] = 1.0
        cuts_A.append(cut); cuts_ub.append(len(chosen) - 1)
    return {"n_min": int(round(n_min)) if n_min is not None else None,
            "alternatives": solutions}


def main() -> None:
    job = json.load(sys.stdin)
    dt = float(job.get("dt_cont_default", 5.0))
    hots, colds = _prep_streams(job["streams"], dt)
    ivals = _intervals(hots, colds)
    qh, qc, resid, pinch_after = _cascade(hots, colds, ivals)

    forbidden = {tuple(p) for p in job.get("forbidden_pairs", [])}
    weights = {tuple(k.split("|", 1)): float(v) for k, v in (job.get("weights") or {}).items()}
    extra = int(job.get("extra_units", 0))
    n_alt = int(job.get("n_alternatives", 8))

    # split intervals into subnetworks at pinch boundaries
    bounds_k = [-1] + pinch_after + [len(ivals) - 1]
    regions = [(bounds_k[r] + 1, bounds_k[r + 1]) for r in range(len(bounds_k) - 1)]

    hmap = {h["name"]: h for h in hots}
    cmap = {c["name"]: c for c in colds}

    def _pinch_check(match, r, top, bot, n_regions):
        """CP-rule check for matches touching a pinch boundary of region r.

        The CP rule is a realization condition for a SINGLE unsplit exchanger at the
        pinch, not an energy constraint — violations mean 'needs stream splitting'.
        """
        if match["is_utility"]:
            return None
        h, c = hmap.get(match["hot"]), cmap.get(match["cold"])
        if h is None or c is None:
            return None
        eps = 1e-3
        verdicts = []
        if r < n_regions - 1 and h["lo"] <= bot + eps and c["lo"] <= bot + eps:
            verdicts.append(h["cp"] <= c["cp"] * (1 + 1e-9))   # above that pinch
        if r > 0 and h["hi"] >= top - eps and c["hi"] >= top - eps:
            verdicts.append(h["cp"] >= c["cp"] * (1 - 1e-9))   # below that pinch
        if not verdicts:
            return "not_at_pinch"
        return "ok" if all(verdicts) else "needs_split"

    out_regions = []
    for r, (k0, k1) in enumerate(regions):
        sub = ivals[k0:k1 + 1]
        hot_loads = {h["name"]: [_load(h, thi, tlo) for (thi, tlo) in sub] for h in hots}
        cold_loads = {c["name"]: [_load(c, thi, tlo) for (thi, tlo) in sub] for c in colds}
        hot_loads = {k: v for k, v in hot_loads.items() if sum(v) > TOL}
        cold_loads = {k: v for k, v in cold_loads.items() if sum(v) > TOL}
        if r == 0 and qh > TOL:
            hot_loads[HOT_UTIL] = [qh] + [0.0] * (len(sub) - 1)
        if r == len(regions) - 1 and qc > TOL:
            cold_loads[COLD_UTIL] = [0.0] * (len(sub) - 1) + [qc]
        if not hot_loads or not cold_loads:
            continue
        sol = _solve_min_matches(hot_loads, cold_loads, weights, forbidden, extra, n_alt)
        for alt in sol["alternatives"]:
            for m in alt["matches"]:
                m["pinch_check"] = _pinch_check(m, r, sub[0][0], sub[-1][1], len(regions))
        out_regions.append({
            "region": r + 1,
            "shifted_temp_range_C": [round(sub[0][0], 2), round(sub[-1][1], 2)],
            "above_pinch": r == 0 and len(regions) > 1,
            "hot_streams": sorted(hot_loads), "cold_streams": sorted(cold_loads),
            **sol,
        })

    json.dump({
        "ok": True,
        "Qh_min_kW": round(qh, 1), "Qc_min_kW": round(qc, 1),
        "pinch_shifted_C": [round(ivals[k][1], 2) for k in pinch_after],
        "regions": out_regions,
        "note": ("Minimum-matches transshipment MILP (Papoulias & Grossmann 1983); "
                 "alternatives enumerated via integer cuts — the list per region is "
                 "exhaustive up to n_alternatives/extra_units."),
    }, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        json.dump({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                   "trace": traceback.format_exc(limit=4)}, sys.stdout)
