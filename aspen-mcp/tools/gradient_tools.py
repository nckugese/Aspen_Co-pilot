"""Gradient-based optimization via scipy SLSQP.

Sequential Least Squares Programming — handles variable bounds + linear and
non-linear inequality constraints. Uses numerical finite-differences for
gradient (there's no analytical derivative for Aspen).

Multi-objective problems are reduced via weighted scalarization
(user supplies ``obj_weights`` or equal weights are assumed).
"""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

from tools._common_eval import (
    EvalStats,
    OptimizationAborted,
    OptimizationCancelled,
    PENALTY,
    ProgressReporter,
    error_result,
    validate_session,
    decode_x,
    evaluate_x,
    is_feasible_values,
    obj_label,
    save_results_generic,
    short_name,
    unique_names,
)

# Eager-import scipy so first call doesn't stall MCP event loop
try:
    from scipy.optimize import minimize as _scipy_minimize
    _SCIPY_AVAILABLE = True
    _SCIPY_IMPORT_ERROR = None
except ImportError as _exc:
    _SCIPY_AVAILABLE = False
    _SCIPY_IMPORT_ERROR = str(_exc)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context

# Consecutive-failure abort threshold (separate from COM-error threshold inside evaluate_x)
MAX_CONSECUTIVE_SIM_FAILS = 5


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def _format_preview(
    session_name, variables, objectives, constraints,
    x0, obj_weights, maxiter, ftol, finite_diff_eps,
    max_retries, output_dir,
) -> str:
    var_names = unique_names([v["aspen_path"] for v in variables])
    n_var = len(variables)
    M = len(objectives)
    # SLSQP: each iter does 1 obj eval + n_var constraint evals for finite-diff
    # + constraint evals. Rough estimate.
    est_evals = maxiter * (1 + n_var)

    lines = [
        "=== SLSQP Gradient Settings Preview ===",
        f"\nSession: {session_name}",
        f"Estimated evaluations: ~{est_evals} (maxiter * (1 + n_var))",
        "\n--- Decision Variables ---",
    ]
    for name, v in zip(var_names, variables):
        lines.append(f"  {name}: [{v['lower']}, {v['upper']}] ({v.get('type', 'float')})")
        lines.append(f"    path: {v['aspen_path']}")

    x0_disp = x0 if x0 else "midpoints of variable bounds"
    lines.append(f"\nInitial point x0: {x0_disp}")

    lines.append("\n--- Objectives (weighted scalarization) ---")
    actual_weights = obj_weights if obj_weights else [1.0 / M] * M
    for o, w in zip(objectives, actual_weights):
        direction = o.get("direction", "minimize")
        tag = obj_label(o)
        lines.append(f"  {direction}: {tag}  (weight={w:.4g})")

    if constraints:
        lines.append("\n--- Constraints ---")
        for c in constraints:
            lines.append(f"  {obj_label(c)}: "
                         f"[{c.get('lower', '-inf')}, {c.get('upper', '+inf')}]")

    lines.append("\n--- Adjustable Parameters ---")
    params = [
        ("maxiter",         str(maxiter),        "max SLSQP outer iterations"),
        ("ftol",            str(ftol),           "convergence tolerance on f"),
        ("finite_diff_eps", str(finite_diff_eps), "step size for numerical gradient"),
        ("max_retries",     str(max_retries),    "simulation retry count"),
    ]
    for name, val, desc in params:
        lines.append(f"  {name:<18} {val:<16} {desc}")
    lines.append(f"\n  output_dir: {output_dir or 'not saved'}")
    lines.append(
        "\nNote: SLSQP computes gradient via finite-difference, meaning each "
        "\nouter iteration costs (n_var + 1) Aspen runs. For Aspen simulations "
        "\nwith long runtimes, budget accordingly."
    )
    lines.append("\nTo start, call optimize again with dry_run=False.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_gradient(
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None = None,
    x0: list[float] | None = None,
    obj_weights: list[float] | None = None,
    maxiter: int = 50,
    ftol: float = 1e-6,
    finite_diff_eps: float = 1e-4,
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str | None = None,
    ctx: "Context | None" = None,
    seed: int | None = None,  # accepted for interface consistency; SLSQP is deterministic
) -> str:
    """Entry point for ``optimize(algorithm='gradient')``."""
    if not variables:
        return "Error: at least one decision variable is required."
    if not objectives:
        return "Error: at least one objective is required."
    if x0 is not None and len(x0) != len(variables):
        return f"Error: x0 must have {len(variables)} entries (one per variable)."
    M = len(objectives)
    if obj_weights is not None and len(obj_weights) != M:
        return f"Error: obj_weights must have {M} entries (one per objective)."

    if dry_run:
        return _format_preview(
            session_name, variables, objectives, constraints,
            x0, obj_weights, maxiter, ftol, finite_diff_eps,
            max_retries, output_dir,
        )

    result = await _run_gradient_core(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        x0=x0, obj_weights=obj_weights, maxiter=maxiter,
        ftol=ftol, finite_diff_eps=finite_diff_eps,
        max_retries=max_retries, output_dir=output_dir, ctx=ctx,
    )
    return result["report"]


async def _run_gradient_core(
    *,
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    x0: list[float] | None,
    obj_weights: list[float] | None,
    maxiter: int,
    ftol: float,
    finite_diff_eps: float,
    max_retries: int,
    output_dir: str | None,
    ctx: "Context | None",
    reporter: ProgressReporter | None = None,
    initial_point: list[float] | None = None,
    seed: int | None = None,  # ignored — SLSQP is deterministic
) -> dict:
    if not _SCIPY_AVAILABLE:
        return error_result(
            f"SLSQP requires scipy. pip install 'scipy>=1.11'\n{_SCIPY_IMPORT_ERROR}"
        )

    err = validate_session(manager, session_name)
    if err is not None:
        return err

    scipy_minimize = _scipy_minimize

    M = len(objectives)
    weights = tuple(1.0 if o.get("direction", "minimize").lower() == "maximize" else -1.0
                    for o in objectives)
    var_names = unique_names([v["aspen_path"] for v in variables])
    obj_labels = [obj_label(o) for o in objectives]
    obj_dirs = [o.get("direction", "minimize")[:3] for o in objectives]
    actual_obj_weights = tuple(obj_weights) if obj_weights else tuple(1.0 / M for _ in range(M))

    if not x0:
        if initial_point:
            x0 = list(initial_point)
        else:
            x0 = [(v["lower"] + v["upper"]) / 2.0 for v in variables]

    bounds = [(v["lower"], v["upper"]) for v in variables]
    debug_log: list[str] = []
    stats = EvalStats()
    eval_log: list[tuple] = []
    aborted = False
    abort_reason = ""
    consecutive_fails = 0

    # Per-x cache so SLSQP's internal finite-diff doesn't re-run Aspen
    cache: dict[tuple, dict] = {}

    total_estimate = maxiter * (1 + len(variables))
    owns_reporter = reporter is None
    if reporter is None:
        reporter = ProgressReporter(
            algorithm="SLSQP", total_evals=total_estimate, n_iterations=maxiter,
            obj_names=obj_labels, iteration_label="Iteration", mcp_ctx=ctx,
        )
    else:
        reporter.set_algorithm("SLSQP", iteration_label="Iteration")

    best_scalar: float | None = None
    best_raw_f: list[float] | None = None
    current_iter = {"i": 0}

    def _eval_cached(x):
        nonlocal aborted, abort_reason, consecutive_fails
        nonlocal best_scalar, best_raw_f

        if reporter.poll_cancel():
            aborted = True
            abort_reason = "Cancelled by user"
            return {"scalar": PENALTY, "raw_f": [PENALTY] * M}

        key = tuple(round(float(v), 10) for v in x)
        if key in cache:
            return cache[key]
        if aborted:
            return {"f": [float("nan")] * M, "feasible": False, "scalar": PENALTY,
                    "reason": "aborted", "con": [float("nan")] * len(constraints or [])}

        try:
            # return_violation keeps the real objectives on a constraint violation, so
            # SLSQP sees a smooth f there while the row is still marked infeasible.
            f_vals, feasible, reason, _ = evaluate_x(
                list(x), manager=manager, session_name=session_name,
                variables=variables, objectives=objectives,
                constraints=constraints, weights=weights,
                max_retries=max_retries,
                debug_log=debug_log, stats=stats,
                return_violation=True,
                info=(_info := {}),
            )
        except OptimizationAborted as exc:
            aborted = True
            abort_reason = str(exc)
            logger.warning("SLSQP aborted: %s", exc)
            return {"f": [float("nan")] * M, "feasible": False, "scalar": PENALTY,
                    "reason": "aborted", "con": [float("nan")] * len(constraints or [])}

        # Sim-level failure tracking
        if not feasible and reason in ("run_fail", "com_error", "not_converged",
                                       "set_fail", "obj_read_fail"):
            consecutive_fails += 1
            if consecutive_fails >= MAX_CONSECUTIVE_SIM_FAILS:
                aborted = True
                abort_reason = (
                    f"{MAX_CONSECUTIVE_SIM_FAILS} consecutive Aspen failures — "
                    f"aborting SLSQP. Use aspen-error-troubleshooting to diagnose."
                )
                logger.warning(abort_reason)
        else:
            consecutive_fails = 0

        # Raw constraint values, as evaluate_x read them (NaN where it read none)
        read = _info.get("con_values", {})
        con_vals = [read.get(i, float("nan")) for i in range(len(constraints or []))]

        # Scalarize (always minimize: -w * f, summed with obj_weights)
        if feasible or reason == "constraint":
            scalar = sum(ow * (-wt) * fv
                         for ow, wt, fv in zip(actual_obj_weights, weights, f_vals))
        else:
            scalar = PENALTY  # huge positive — SLSQP minimizes

        decoded = decode_x(list(x), variables)
        eval_log.append((current_iter["i"], decoded, list(f_vals), feasible,
                         time.time() - start,
                         _info.get("reason", ""), _info.get("detail", "")))

        # Track best
        if feasible and (best_scalar is None or scalar < best_scalar):
            best_scalar = scalar
            best_raw_f = list(f_vals)

        result = {"f": list(f_vals), "feasible": feasible,
                  "reason": reason, "con": con_vals, "scalar": scalar}
        cache[key] = result

        reporter.update_sync(
            current_iter["i"],
            stats.total,
            f"Iter {current_iter['i']} ({stats.total} evals; scalar={scalar:.4g})",
            best_raw_f,
        )
        return result

    def _objective(x):
        res = _eval_cached(x)
        return res["scalar"]

    def _make_ineq_lower(idx, lower_bound):
        def fn(x):
            r = _eval_cached(x)
            v = r["con"][idx]
            # NaN → force violation
            return (v - lower_bound) if v == v else -1e6  # (v == v) is False iff NaN
        return fn

    def _make_ineq_upper(idx, upper_bound):
        def fn(x):
            r = _eval_cached(x)
            v = r["con"][idx]
            return (upper_bound - v) if v == v else -1e6
        return fn

    scipy_constraints = []
    for i, c in enumerate(constraints or []):
        if c.get("lower") is not None:
            scipy_constraints.append({"type": "ineq",
                                      "fun": _make_ineq_lower(i, c["lower"])})
        if c.get("upper") is not None:
            scipy_constraints.append({"type": "ineq",
                                      "fun": _make_ineq_upper(i, c["upper"])})

    def _callback(xk):
        current_iter["i"] += 1

    start = time.time()
    try:
        res = scipy_minimize(
            _objective, x0,
            method="SLSQP",
            bounds=bounds,
            constraints=scipy_constraints,
            callback=_callback,
            options={"maxiter": maxiter, "ftol": ftol, "eps": finite_diff_eps,
                     "disp": False},
        )
    except OptimizationCancelled:
        aborted = True
        abort_reason = "Cancelled by user"
        logger.info("SLSQP cancelled by user")
        from types import SimpleNamespace
        res = SimpleNamespace(x=x0, message="Cancelled by user")
    except Exception as exc:
        logger.warning("SLSQP raised exception: %s", exc)
        if owns_reporter:
            reporter.abort(f"SLSQP error: {exc}")
        return error_result(f"SLSQP optimization failed: {exc}")

    wall_time = time.time() - start

    if owns_reporter:
        reporter.finalize(aborted, abort_reason=abort_reason)

    # Extract final point and objectives (from cache if possible)
    if hasattr(res, "x"):
        x_final = res.x.tolist() if hasattr(res.x, "tolist") else list(res.x)
    else:
        x_final = list(x0)
    final_key = tuple(round(float(v), 10) for v in x_final)
    final_data = cache.get(final_key)
    pareto: list[dict] = []
    if final_data and final_data["feasible"] and is_feasible_values(final_data["f"]):
        pareto = [{"x": decode_x(x_final, variables), "f": final_data["f"]}]
    elif best_raw_f is not None:
        # Fall back to best feasible seen along the way
        # Find the x that produced best_raw_f
        for key, d in cache.items():
            if d["feasible"] and d["f"] == best_raw_f:
                pareto = [{"x": decode_x(list(key), variables), "f": d["f"]}]
                break

    def _fmt_point(p):
        xs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, p["x"]))
        fs = ", ".join(f"{n}={v:.4g} ({dr})"
                       for n, v, dr in zip(obj_labels, p["f"], obj_dirs))
        return f"{xs} -> {fs}"

    header = "ABORTED" if aborted else "SLSQP complete"
    convergence_msg = getattr(res, "message", "") if not aborted else abort_reason
    lines = [f"{header}: {stats.total} evaluations, wall-time {wall_time:.1f}s",
             f"Convergence: {convergence_msg}"]
    if pareto:
        lines.append(f"\nBest solution: {_fmt_point(pareto[0])}")
    else:
        lines.append("\nNo feasible solution found.")

    lines.append("")
    lines.append(stats.format_report())

    if debug_log:
        unique_msgs = list(dict.fromkeys(debug_log[:20]))
        lines.append(f"\nFailure details ({len(debug_log)}):")
        lines += [f"  {m}" for m in unique_msgs]

    log_lines = [f"SLSQP: {stats.total} evals, maxiter={maxiter}, ftol={ftol}"]

    if output_dir:
        try:
            settings = {
                "Algorithm": "SLSQP (scipy)",
                "maxiter": maxiter,
                "ftol": ftol,
                "finite_diff_eps": finite_diff_eps,
                "Objective weights": list(actual_obj_weights),
                "x0": list(x0),
                "Max retries": max_retries,
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm="SLSQP", session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings, pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save SLSQP results: %s", e, exc_info=True)
            lines.append(f"\nWarning: failed to save results: {e}")

    return {
        "report": "\n".join(lines),
        "pareto": pareto,
        "eval_log": eval_log,
        "stats": stats,
        "wall_time": wall_time,
        "weights": weights,
        "aborted": aborted,
        "best_compromise_idx": 0 if pareto else -1,
    }


