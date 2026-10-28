"""NSGA-II multi-objective optimization via pymoo.

Mirrors the NSGA-III architecture (``nsga3_tools.py``): wraps ``evaluate_x``
inside a pymoo ``Problem`` and lets ``pymoo_minimize`` drive the GA loop with
SBX crossover and polynomial mutation. A ``Callback`` reports per-generation
progress and handles cancellation / stall-based early stopping.
"""

from __future__ import annotations

import logging
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
    decode_x,
    evaluate_x,
    is_feasible_values,
    lhs_sample,
    obj_label,
    save_results_generic,
    short_name,
    unique_names,
    validate_session,
)

# Eager-import heavy deps so first call doesn't stall MCP event loop
try:
    import numpy as _np
    from pymoo.algorithms.moo.nsga2 import NSGA2 as _NSGA2
    from pymoo.core.callback import Callback as _PymooCallback
    from pymoo.core.problem import Problem as _PymooProblem
    from pymoo.operators.crossover.sbx import SBX as _SBX
    from pymoo.operators.mutation.pm import PolynomialMutation as _PolynomialMutation
    from pymoo.operators.sampling.rnd import FloatRandomSampling as _FloatRandomSampling
    from pymoo.optimize import minimize as _pymoo_minimize
    _PYMOO_AVAILABLE = True
    _PYMOO_IMPORT_ERROR = None
except ImportError as _exc:
    _PYMOO_AVAILABLE = False
    _PYMOO_IMPORT_ERROR = str(_exc)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context


# ---------------------------------------------------------------------------
# Preview (dry_run) formatter
# ---------------------------------------------------------------------------

def _format_preview(
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    pop_size: int,
    n_gen: int,
    crossover_prob: float,
    mutation_prob: float,
    eta_crossover: float,
    eta_mutation: float,
    seed: int | None,
    sampling: str,
    stall_generations: int,
    max_retries: int,
    output_dir: str | None,
) -> str:
    var_names = unique_names([v["aspen_path"] for v in variables])
    # n_gen = total generations (including initial population).
    total_evals = pop_size * n_gen

    lines = [
        "=== Optimization Settings Preview ===",
        f"\nSession: {session_name}",
        f"Estimated evaluations: {total_evals}",
        "\n--- Decision Variables ---",
    ]
    for name, v in zip(var_names, variables):
        vtype = v.get("type", "float")
        lines.append(f"  {name}: [{v['lower']}, {v['upper']}] ({vtype})")
        lines.append(f"    path: {v['aspen_path']}")

    lines.append("\n--- Objectives ---")
    for o in objectives:
        direction = o.get("direction", "minimize")
        if "aspen_paths" in o:
            expr = o.get("expression", "sum")
            paths = ", ".join(short_name(p) for p in o["aspen_paths"])
            lines.append(f"  {direction}: {expr} ({paths})")
        else:
            lines.append(f"  {direction}: {short_name(o['aspen_path'])}")
            lines.append(f"    path: {o['aspen_path']}")

    if constraints:
        lines.append("\n--- Constraints ---")
        for c in constraints:
            lo = c.get("lower", "-inf")
            hi = c.get("upper", "+inf")
            if "aspen_paths" in c:
                label = c.get("expression", "sum") + " (" + ", ".join(short_name(p) for p in c["aspen_paths"]) + ")"
                lines.append(f"  {label}: [{lo}, {hi}]")
            else:
                lines.append(f"  {short_name(c['aspen_path'])}: [{lo}, {hi}]")
                lines.append(f"    path: {c['aspen_path']}")

    lines.append("\n--- Adjustable Parameters ---")
    lines.append(f"{'Parameter':<22} {'Value':<12} {'Range':<14} Description")
    lines.append(f"{'-'*22} {'-'*12} {'-'*14} {'-'*40}")
    params = [
        ("pop_size",           str(pop_size),
         "10-200",       "Solutions per generation; larger=broader search, slower"),
        ("n_gen",              str(n_gen),
         "5-100",        "Max evolution iterations; more=better chance of optimum"),
        ("crossover_prob",     str(crossover_prob),
         "0.5-1.0",      "Probability of combining two parents into offspring"),
        ("mutation_prob",      str(mutation_prob),
         "0.05-0.5",     "Probability of random perturbation; avoids local optima"),
        ("eta_crossover",      str(eta_crossover),
         "5-30",         "Crossover spread; higher=offspring closer to parents"),
        ("eta_mutation",       str(eta_mutation),
         "5-30",         "Mutation spread; higher=smaller changes, more precise"),
        ("sampling",           sampling,
         "random / lhs", "Initial sampling; lhs gives more uniform coverage"),
        ("seed",               str(seed) if seed is not None else "random",
         "any int",      "Random seed; set for reproducible results"),
        ("stall_generations",  str(stall_generations) if stall_generations > 0 else "disabled",
         "0-20",         "Early stop after N gens with no improvement; 0=off"),
        ("max_retries",        str(max_retries),
         "1-3",          "Retry count on simulation failure; 1=no retry"),
    ]
    for name, val, rng, desc in params:
        lines.append(f"  {name:<20} {val:<12} {rng:<14} {desc}")

    lines.append(f"\n  output_dir: {output_dir or 'not saved'}")
    lines.append(f"\nEstimated evaluations: {total_evals}")
    lines.append("\nTo start, call optimize again with dry_run=False.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_optimization(
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None = None,
    pop_size: int = 50,
    n_gen: int = 30,
    crossover_prob: float = 0.8,
    mutation_prob: float = 0.2,
    eta_crossover: float = 20.0,
    eta_mutation: float = 20.0,
    seed: int | None = None,
    sampling: str = "random",
    stall_generations: int = 0,
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str | None = None,
    ctx: "Context | None" = None,
) -> str:
    """Run NSGA-II optimization. Returns formatted Pareto front and best compromise."""
    if not variables:
        return "Error: at least one decision variable is required."
    if not objectives:
        return "Error: at least one objective is required."
    for v in variables:
        if not all(k in v for k in ("aspen_path", "lower", "upper")):
            return "Error: each variable needs 'aspen_path', 'lower', and 'upper'."
    for o in objectives:
        if "aspen_path" not in o and "aspen_paths" not in o:
            return "Error: each objective needs 'aspen_path' or 'aspen_paths'."
    if sampling not in ("random", "lhs"):
        return "Error: sampling must be 'random' or 'lhs'."

    if dry_run:
        return _format_preview(
            session_name, variables, objectives, constraints,
            pop_size, n_gen, crossover_prob, mutation_prob,
            eta_crossover, eta_mutation, seed, sampling,
            stall_generations, max_retries, output_dir,
        )

    result = await _run_nsga2_core(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        pop_size=pop_size, n_gen=n_gen,
        crossover_prob=crossover_prob, mutation_prob=mutation_prob,
        eta_crossover=eta_crossover, eta_mutation=eta_mutation,
        seed=seed, sampling=sampling,
        stall_generations=stall_generations, max_retries=max_retries,
        output_dir=output_dir, ctx=ctx,
    )
    return result["report"]


# ---------------------------------------------------------------------------
# Core runner — pymoo NSGA2
# ---------------------------------------------------------------------------

async def _run_nsga2_core(
    *,
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    pop_size: int,
    n_gen: int,
    crossover_prob: float,
    mutation_prob: float,
    eta_crossover: float,
    eta_mutation: float,
    seed: int | None,
    sampling: str,
    stall_generations: int,
    max_retries: int,
    output_dir: str | None,
    ctx: "Context | None",
    reporter: ProgressReporter | None = None,
    initial_seeds: list[list[float]] | None = None,
) -> dict:
    """Core NSGA-II loop. Returns {report, pareto, eval_log, stats, wall_time, ...}."""
    if not _PYMOO_AVAILABLE:
        return {
            "report": (f"Error: NSGA-II requires pymoo and numpy. "
                       f"Install with: pip install 'pymoo>=0.6.1'\n({_PYMOO_IMPORT_ERROR})"),
            "pareto": [], "eval_log": [], "stats": None,
            "wall_time": 0.0, "weights": (), "aborted": True,
            "best_compromise_idx": -1,
        }

    err = validate_session(manager, session_name)
    if err is not None:
        return err

    np = _np
    NSGA2 = _NSGA2
    Callback = _PymooCallback
    Problem = _PymooProblem
    SBX = _SBX
    PolynomialMutation = _PolynomialMutation
    FloatRandomSampling = _FloatRandomSampling
    pymoo_minimize = _pymoo_minimize

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

    debug_log: list[str] = []
    stats = EvalStats()
    eval_log: list[tuple] = []
    best_objs: list[float] | None = None

    total_evals = pop_size * n_gen

    owns_reporter = reporter is None
    if reporter is None:
        reporter = ProgressReporter(
            algorithm="NSGA-II", total_evals=total_evals, n_iterations=n_gen,
            obj_names=obj_labels, iteration_label="Generation", mcp_ctx=ctx,
        )
    else:
        reporter.set_algorithm("NSGA-II", iteration_label="Generation")

    n_var = len(variables)
    lows = np.array([v["lower"] for v in variables], dtype=float)
    highs = np.array([v["upper"] for v in variables], dtype=float)

    aborted = False
    n_constr = 1 if constraints else 0
    _current_gen = {"g": 0}

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
                    f_vals, feasible, _reason, violation = evaluate_x(
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
                    logger.warning("NSGA-II aborted: %s", exc)
                    continue

                decoded = decode_x(X[i].tolist(), variables)
                eval_log.append((_current_gen["g"], decoded, list(f_vals),
                                 feasible, time.time() - start,
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
                    G[i, 0] = violation

                try:
                    reporter.update_sync(
                        _current_gen["g"], stats.total,
                        f"Gen {_current_gen['g']}/{n_gen} eval {stats.total}",
                        best_objs,
                    )
                except OptimizationCancelled:
                    aborted = True

            out["F"] = F
            if G is not None:
                out["G"] = G

    # --- Progress + stall callback ----------------------------------------
    log_lines: list[str] = []
    stall_state = {"prev": None, "count": 0}

    class _PymooCB(Callback):
        def notify(self, algorithm):
            nonlocal aborted
            # Academic gen numbering: pymoo's gen 1 = our init (gen 0), pymoo gen N = our gen N-1
            academic_gen = algorithm.n_gen - 1
            _current_gen["g"] = algorithm.n_gen  # used as next-gen index for eval_log
            eval_count = algorithm.evaluator.n_eval
            log_lines.append(f"Gen {academic_gen}/{n_gen}: total evals {eval_count}")

            try:
                reporter.update_sync(
                    academic_gen, eval_count,
                    f"Generation {academic_gen}/{n_gen}", best_objs,
                )
            except OptimizationCancelled:
                aborted = True
                algorithm.termination.force_termination = True
                return

            if stall_generations > 0 and best_objs is not None:
                if stall_state["prev"] is not None and best_objs == stall_state["prev"]:
                    stall_state["count"] += 1
                else:
                    stall_state["count"] = 0
                stall_state["prev"] = list(best_objs)
                if stall_state["count"] >= stall_generations:
                    log_lines.append(
                        f"Early stop at gen {algorithm.n_gen}: "
                        f"no improvement for {stall_generations} gens")
                    algorithm.termination.force_termination = True

    # --- Initial sampling --------------------------------------------------
    if initial_seeds:
        seed_arr = np.array(initial_seeds[:pop_size], dtype=float)
        if len(seed_arr) < pop_size:
            extra = (lhs_sample(pop_size - len(seed_arr), variables)
                     if sampling == "lhs"
                     else [[random.uniform(v["lower"], v["upper"]) for v in variables]
                           for _ in range(pop_size - len(seed_arr))])
            seed_arr = np.vstack([seed_arr, np.array(extra, dtype=float)])
        sampling_obj = seed_arr
    elif sampling == "lhs":
        sampling_obj = np.array(lhs_sample(pop_size, variables), dtype=float)
    else:
        sampling_obj = FloatRandomSampling()

    start = time.time()
    res = None
    try:
        algo = NSGA2(
            pop_size=pop_size,
            sampling=sampling_obj,
            crossover=SBX(prob=crossover_prob, eta=eta_crossover),
            mutation=PolynomialMutation(prob=mutation_prob, eta=eta_mutation),
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
        logger.info("NSGA-II cancelled by user")
    except OptimizationAborted as exc:
        aborted = True
        logger.warning("NSGA-II aborted at outer level: %s", exc)

    wall_time = time.time() - start
    actual_gen = max(0, _current_gen["g"] - 1)  # academic numbering: init = 0

    if owns_reporter:
        reporter.finalize(aborted)

    # --- Extract Pareto front ---------------------------------------------
    pareto: list[dict] = []
    if res is not None and res.F is not None:
        X = res.X if res.X.ndim == 2 else res.X.reshape(1, -1)
        F = res.F if res.F.ndim == 2 else res.F.reshape(1, -1)
        for x_row, f_row in zip(X, F):
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

    header = "ABORTED" if aborted else "Optimization complete"
    lines = [f"{header}: {actual_gen} generations, {pop_size} population, "
             f"wall-time {wall_time:.1f}s",
             f"\nPareto Front ({len(pareto)} solutions):"]
    for idx, p in enumerate(pareto):
        marker = " <<<" if idx == comp_idx else ""
        lines.append(f"  #{idx + 1}: {_fmt_point(p)}{marker}")

    if pareto and comp_idx >= 0:
        lines.append(f"\nBest compromise: {_fmt_point(pareto[comp_idx])}")

    if log_lines:
        lines.append("\nGeneration log:")
        lines += [f"  {line}" for line in log_lines]

    lines.append("")
    lines.append(stats.format_report())

    if debug_log:
        unique_msgs = list(dict.fromkeys(debug_log[:20]))
        lines.append(f"\nFailure details ({len(debug_log)}):")
        lines += [f"  {m}" for m in unique_msgs]

    if output_dir:
        try:
            settings = {
                "Algorithm": "NSGA-II",
                "Population": pop_size,
                "Generations": n_gen,
                "Actual generations": actual_gen,
                "Crossover prob": crossover_prob,
                "Mutation prob": mutation_prob,
                "ETA crossover": eta_crossover,
                "ETA mutation": eta_mutation,
                "Seed": seed if seed is not None else "random",
                "Sampling": sampling,
                "Stall generations": stall_generations if stall_generations > 0 else "disabled",
                "Max retries": max_retries,
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm="NSGA-II",
                session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings,
                pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save optimization results: %s", e, exc_info=True)
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
