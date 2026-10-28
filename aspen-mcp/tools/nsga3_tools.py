"""NSGA-III multi-objective optimization via pymoo.

Designed for problems with 3+ objectives where NSGA-II's crowding distance
degrades. Uses Das-Dennis reference points to maintain diversity on the
Pareto front.
"""

from __future__ import annotations

import logging
import math
import random
import time
from typing import TYPE_CHECKING

from tools._common_eval import (
    EvalStats,
    INFEASIBLE_VIOLATION,
    OptimizationAborted,
    OptimizationCancelled,
    ProgressReporter,
    best_compromise,
    validate_session,
    decode_x,
    evaluate_x,
    is_feasible_values,
    lhs_sample,
    obj_label,
    save_results_generic,
    short_name,
    unique_names,
)

# Eager-import heavy deps so first call doesn't stall MCP event loop
try:
    import numpy as _np
    from pymoo.algorithms.moo.nsga3 import NSGA3 as _NSGA3
    from pymoo.core.callback import Callback as _PymooCallback
    from pymoo.core.problem import Problem as _PymooProblem
    from pymoo.operators.sampling.rnd import FloatRandomSampling as _FloatRandomSampling
    from pymoo.optimize import minimize as _pymoo_minimize
    from pymoo.util.ref_dirs import get_reference_directions as _get_reference_directions
    _PYMOO_AVAILABLE = True
    _PYMOO_IMPORT_ERROR = None
except ImportError as _exc:
    _PYMOO_AVAILABLE = False
    _PYMOO_IMPORT_ERROR = str(_exc)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def _format_preview(
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    pop_size: int,
    n_gen: int,
    n_partitions: int | None,
    seed: int | None,
    sampling: str,
    max_retries: int,
    output_dir: str | None,
) -> str:
    var_names = unique_names([v["aspen_path"] for v in variables])
    total_evals = pop_size * n_gen
    M = len(objectives)
    H = _ref_dir_count(M, n_partitions) if n_partitions else pop_size

    lines = [
        "=== NSGA-III Settings Preview ===",
        f"\nSession: {session_name}",
        f"Estimated evaluations: {total_evals}",
        f"Reference points: {H} (M={M} objectives, "
        f"p={_auto_partitions(M, pop_size) if not n_partitions else n_partitions})",
        "\n--- Decision Variables ---",
    ]
    for name, v in zip(var_names, variables):
        lines.append(f"  {name}: [{v['lower']}, {v['upper']}] ({v.get('type', 'float')})")
        lines.append(f"    path: {v['aspen_path']}")

    lines.append("\n--- Objectives ---")
    for o in objectives:
        direction = o.get("direction", "minimize")
        if "aspen_paths" in o:
            lines.append(f"  {direction}: {o.get('expression', 'sum')} "
                         f"({', '.join(short_name(p) for p in o['aspen_paths'])})")
        else:
            lines.append(f"  {direction}: {short_name(o['aspen_path'])}")

    if constraints:
        lines.append("\n--- Constraints ---")
        for c in constraints:
            lines.append(f"  {obj_label(c)}: "
                         f"[{c.get('lower', '-inf')}, {c.get('upper', '+inf')}]")

    lines.append("\n--- Adjustable Parameters ---")
    params = [
        ("pop_size",      str(pop_size),     "size of each generation"),
        ("n_gen",         str(n_gen),        "number of generations"),
        ("n_partitions",  str(n_partitions) if n_partitions else "auto",
         "Das-Dennis partitions per objective axis"),
        ("sampling",      sampling,          "random or lhs"),
        ("seed",          str(seed) if seed is not None else "random", "random seed"),
        ("max_retries",   str(max_retries),  "simulation retry count"),
    ]
    for name, val, desc in params:
        lines.append(f"  {name:<16} {val:<16} {desc}")
    lines.append(f"\n  output_dir: {output_dir or 'not saved'}")
    lines.append("\nTo start, call optimize again with dry_run=False.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reference-direction sizing helpers
# ---------------------------------------------------------------------------

def _ref_dir_count(M: int, p: int) -> int:
    """H = C(M + p - 1, p) — the Das-Dennis reference point count."""
    return math.comb(M + p - 1, p)


def _auto_partitions(M: int, target_pop: int) -> int:
    """Find p such that C(M+p-1, p) is close to (but not exceeding) target_pop."""
    p = 1
    while _ref_dir_count(M, p + 1) <= target_pop:
        p += 1
        if p > 30:  # safety
            break
    return max(p, 1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_nsga3(
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None = None,
    pop_size: int = 92,              # 92 = C(3+5-1, 5) good default for 3 obj
    n_gen: int = 30,
    n_partitions: int | None = None,
    seed: int | None = None,
    sampling: str = "random",
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str | None = None,
    ctx: "Context | None" = None,
) -> str:
    """Entry point for ``optimize(algorithm='nsga3')``."""
    if not variables:
        return "Error: at least one decision variable is required."
    if not objectives:
        return "Error: at least one objective is required."
    if len(objectives) < 2:
        return "Error: NSGA-III is designed for 2+ objectives. Use algorithm='nsga2' or 'bo' for single-objective."
    if sampling not in ("random", "lhs"):
        return "Error: sampling must be 'random' or 'lhs'."

    if dry_run:
        return _format_preview(
            session_name, variables, objectives, constraints,
            pop_size, n_gen, n_partitions, seed, sampling,
            max_retries, output_dir,
        )

    result = await _run_nsga3_core(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        pop_size=pop_size, n_gen=n_gen, n_partitions=n_partitions,
        seed=seed, sampling=sampling, max_retries=max_retries,
        output_dir=output_dir, ctx=ctx,
    )
    return result["report"]


async def _run_nsga3_core(
    *,
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    pop_size: int,
    n_gen: int,
    n_partitions: int | None,
    seed: int | None,
    sampling: str,
    max_retries: int,
    output_dir: str | None,
    ctx: "Context | None",
    reporter: ProgressReporter | None = None,
    initial_seeds: list[list[float]] | None = None,
) -> dict:
    if not _PYMOO_AVAILABLE:
        return {
            "report": (f"Error: NSGA-III requires pymoo and numpy. "
                       f"Install with: pip install 'pymoo>=0.6.1'\n({_PYMOO_IMPORT_ERROR})"),
            "pareto": [], "eval_log": [], "stats": None,
            "wall_time": 0.0, "weights": (), "aborted": True,
            "best_compromise_idx": -1,
        }

    err = validate_session(manager, session_name)
    if err is not None:
        return err

    np = _np
    NSGA3 = _NSGA3
    Callback = _PymooCallback
    Problem = _PymooProblem
    FloatRandomSampling = _FloatRandomSampling
    pymoo_minimize = _pymoo_minimize
    get_reference_directions = _get_reference_directions

    weights = tuple(1.0 if o.get("direction", "minimize").lower() == "maximize" else -1.0
                    for o in objectives)
    var_names = unique_names([v["aspen_path"] for v in variables])
    obj_labels = [obj_label(o) for o in objectives]
    obj_dirs = [o.get("direction", "minimize")[:3] for o in objectives]
    M = len(objectives)

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    else:
        random.seed()

    p = n_partitions if n_partitions else _auto_partitions(M, pop_size)
    ref_dirs = get_reference_directions("das-dennis", M, n_partitions=p)

    debug_log: list[str] = []
    stats = EvalStats()
    eval_log: list[tuple] = []
    best_objs: list[float] | None = None

    total_evals = pop_size * n_gen

    owns_reporter = reporter is None
    if reporter is None:
        reporter = ProgressReporter(
            algorithm="NSGA-III", total_evals=total_evals, n_iterations=n_gen,
            obj_names=obj_labels, iteration_label="Generation", mcp_ctx=ctx,
        )
    else:
        reporter.set_algorithm("NSGA-III", iteration_label="Generation")

    # --- Problem wrapping evaluate_x --------------------------------------
    n_var = len(variables)
    lows = np.array([v["lower"] for v in variables])
    highs = np.array([v["upper"] for v in variables])

    aborted = False

    n_constr = 1 if constraints else 0

    class _AspenProblem(Problem):
        def __init__(self):
            super().__init__(n_var=n_var, n_obj=M, n_ieq_constr=n_constr,
                             xl=lows, xu=highs)

        def _evaluate(self, X, out, *args, **kwargs):
            nonlocal best_objs, aborted
            F = np.zeros((X.shape[0], M))
            G = np.zeros((X.shape[0], n_constr)) if n_constr else None
            for i in range(X.shape[0]):
                if aborted:
                    F[i] = np.full(M, 1e10)
                    if G is not None:
                        G[i, 0] = INFEASIBLE_VIOLATION
                    continue
                if reporter.poll_cancel():
                    aborted = True
                    F[i] = np.full(M, 1e10)
                    if G is not None:
                        G[i, 0] = INFEASIBLE_VIOLATION
                    continue
                try:
                    f_vals, feasible, reason, violation = evaluate_x(
                        X[i].tolist(),
                        manager=manager, session_name=session_name,
                        variables=variables, objectives=objectives,
                        constraints=constraints, weights=weights,
                        max_retries=max_retries,
                        debug_log=debug_log, stats=stats,
                        return_violation=True,
                        info=(_info := {}),
                    )
                except OptimizationAborted as exc:
                    aborted = True
                    F[i] = np.full(M, 1e10)
                    if G is not None:
                        G[i, 0] = INFEASIBLE_VIOLATION
                    logger.warning("NSGA-III aborted: %s", exc)
                    continue

                decoded = decode_x(X[i].tolist(), variables)
                eval_log.append((_current_gen["g"], decoded, list(f_vals), feasible,
                                 time.time() - start,
                                 _info.get("reason", ""), _info.get("detail", "")))

                if feasible:
                    if best_objs is None:
                        best_objs = list(f_vals)
                    else:
                        for j, (w, v, b) in enumerate(zip(weights, f_vals, best_objs)):
                            if (w > 0 and v > b) or (w < 0 and v < b):
                                best_objs[j] = v

                # pymoo minimizes → flip maximize objectives
                F[i] = np.array([-w * f for f, w in zip(f_vals, weights)])
                if G is not None:
                    G[i, 0] = violation  # 0 if feasible, >0 if violated, large if sim failed

                # Per-evaluation progress update
                try:
                    reporter.update_sync(
                        _current_gen["g"],
                        stats.total,
                        f"Gen {_current_gen['g']}/{n_gen} eval {stats.total}",
                        best_objs,
                    )
                except OptimizationCancelled:
                    aborted = True

            out["F"] = F
            if G is not None:
                out["G"] = G

    _current_gen = {"g": 0}

    # --- Progress callback -------------------------------------------------
    class _PymooCB(Callback):
        def notify(self, algorithm):
            nonlocal aborted
            # Academic numbering: pymoo's gen 1 = init (gen 0), pymoo gen N = academic gen N-1
            academic_gen = algorithm.n_gen - 1
            _current_gen["g"] = algorithm.n_gen  # next eval batch is in academic gen = pymoo n_gen
            eval_count = algorithm.evaluator.n_eval
            try:
                reporter.update_sync(
                    academic_gen,
                    eval_count,
                    f"Generation {academic_gen}/{n_gen}",
                    best_objs,
                )
            except OptimizationCancelled:
                aborted = True
                algorithm.termination.force_termination = True

    # --- Initial sampling --------------------------------------------------
    if initial_seeds:
        seed_arr = np.array(initial_seeds[:pop_size])
        if len(seed_arr) < pop_size:
            extra = lhs_sample(pop_size - len(seed_arr), variables) if sampling == "lhs" \
                else [[random.uniform(v["lower"], v["upper"]) for v in variables]
                      for _ in range(pop_size - len(seed_arr))]
            seed_arr = np.vstack([seed_arr, np.array(extra)])
        sampling_obj = seed_arr
    elif sampling == "lhs":
        sampling_obj = np.array(lhs_sample(pop_size, variables))
    else:
        sampling_obj = FloatRandomSampling()

    start = time.time()
    try:
        algo = NSGA3(
            pop_size=pop_size,
            ref_dirs=ref_dirs,
            sampling=sampling_obj,
        )
        # n_gen here = total generations (including initial population).
        # pymoo's ("n_gen", N) terminates after evaluating N generations.
        res = pymoo_minimize(
            _AspenProblem(), algo, ("n_gen", n_gen),
            seed=seed if seed is not None else None,
            callback=_PymooCB(),
            verbose=False,
        )
    except OptimizationCancelled:
        aborted = True
        res = None
        logger.info("NSGA-III cancelled by user")
    except OptimizationAborted as exc:
        aborted = True
        res = None
        logger.warning("NSGA-III aborted at outer level: %s", exc)

    wall_time = time.time() - start

    if owns_reporter:
        reporter.finalize(aborted)

    # --- Extract Pareto front ---------------------------------------------
    pareto: list[dict] = []
    if res is not None and res.F is not None:
        # Unflip back to raw objective values
        for x_row, f_row in zip(res.X, res.F):
            raw_f = [(-w) * fv for fv, w in zip(f_row, weights)]
            if is_feasible_values(raw_f):
                pareto.append({"x": decode_x(x_row.tolist(), variables),
                               "f": raw_f})
        pareto.sort(key=lambda p: p["f"][0])

    fitness_matrix = [p["f"] for p in pareto]
    comp_idx = best_compromise(fitness_matrix, weights) if pareto else -1

    # --- Report ------------------------------------------------------------
    def _fmt_point(p):
        xs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, p["x"]))
        fs = ", ".join(f"{n}={v:.4g} ({dr})"
                       for n, v, dr in zip(obj_labels, p["f"], obj_dirs))
        return f"{xs} -> {fs}"

    header = "ABORTED" if aborted else "NSGA-III complete"
    lines = [f"{header}: {n_gen} generations, {pop_size} population, "
             f"{len(ref_dirs)} reference points, wall-time {wall_time:.1f}s",
             f"\nPareto Front ({len(pareto)} solutions):"]
    for idx, p in enumerate(pareto):
        marker = " <<<" if idx == comp_idx else ""
        lines.append(f"  #{idx + 1}: {_fmt_point(p)}{marker}")

    if pareto and comp_idx >= 0:
        lines.append(f"\nBest compromise: {_fmt_point(pareto[comp_idx])}")

    lines.append("")
    lines.append(stats.format_report())

    if debug_log:
        unique_msgs = list(dict.fromkeys(debug_log[:20]))
        lines.append(f"\nFailure details ({len(debug_log)}):")
        lines += [f"  {m}" for m in unique_msgs]

    log_lines = [f"NSGA-III: {n_gen} gens, {pop_size} pop, {len(ref_dirs)} ref-dirs"]

    if output_dir:
        try:
            settings = {
                "Algorithm": "NSGA-III",
                "Population": pop_size,
                "Generations": n_gen,
                "Reference points": len(ref_dirs),
                "Partitions (p)": p,
                "Seed": seed if seed is not None else "random",
                "Sampling": sampling,
                "Max retries": max_retries,
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm="NSGA-III",
                session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings, pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save NSGA-III results: %s", e, exc_info=True)
            lines.append(f"\nWarning: failed to save results: {e}")

    return {
        "report": "\n".join(lines),
        "pareto": pareto,
        "eval_log": eval_log,
        "stats": stats,
        "wall_time": wall_time,
        "weights": weights,
        "aborted": aborted,
        "best_compromise_idx": comp_idx,
    }
