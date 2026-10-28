"""Differential Evolution — DE (single-objective) and GDE3 (multi-objective).

Single-objective uses pymoo's classical DE. Multi-objective uses GDE3
(Generalized Differential Evolution 3) from pymoo's experimental module.
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
    error_result,
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

try:
    import numpy as _np
    from pymoo.algorithms.soo.nonconvex.de import DE as _DE, Variant as _Variant
    from pymoo.core.callback import Callback as _PymooCallback
    from pymoo.core.problem import Problem as _PymooProblem
    from pymoo.operators.sampling.rnd import FloatRandomSampling as _FloatRandomSampling
    from pymoo.optimize import minimize as _pymoo_minimize
    _PYMOO_AVAILABLE = True
    _PYMOO_IMPORT_ERROR = None
except ImportError as _exc:
    _PYMOO_AVAILABLE = False
    _PYMOO_IMPORT_ERROR = str(_exc)

try:
    from pymoo.experimental.algorithms.gde3 import GDE3 as _GDE3
    _GDE3_AVAILABLE = True
    _GDE3_IMPORT_ERROR = None
except ImportError as _exc:
    _GDE3_AVAILABLE = False
    _GDE3_IMPORT_ERROR = str(_exc)

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
    variant: str,
    CR: float,
    F: float,
    dither: str,
    seed: int | None,
    sampling: str,
    max_retries: int,
    output_dir: str | None,
) -> str:
    var_names = unique_names([v["aspen_path"] for v in variables])
    M = len(objectives)
    multi = M >= 2
    backend = f"GDE3 ({M} objectives)" if multi else "DE (single-objective)"
    total_evals = pop_size * n_gen

    lines = [
        f"=== {backend} Settings Preview ===",
        f"\nSession: {session_name}",
        f"Estimated evaluations: {total_evals}",
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
        ("pop_size",    str(pop_size),    "10-200",     "Solutions per generation"),
        ("n_gen",       str(n_gen),       "5-100",      "Number of generations"),
        ("variant",     variant,          "string",     "DE strategy (single-obj only)" if multi
                                                        else "DE strategy: DE/<sel>/<n>/<xover>"),
        ("CR",          str(CR),          "0.0-1.0",    "Crossover probability"),
        ("F",           str(F),           "0.0-2.0",    "Differential weight / scale factor"),
        ("dither",      dither,           "vector/scalar/no",
         "F randomization (single-obj only)" if multi else "F randomization mode"),
        ("sampling",    sampling,         "random/lhs", "Initial population sampling"),
        ("seed",        str(seed) if seed is not None else "random",
                                          "any int",    "Random seed"),
        ("max_retries", str(max_retries), "1-3",        "Simulation retry count"),
    ]
    lines.append(f"{'Parameter':<20} {'Value':<20} {'Range':<16} {'Description'}")
    lines.append(f"{'-'*20} {'-'*20} {'-'*16} {'-'*40}")
    for name, val, rng, desc in params:
        note = " (ignored for GDE3)" if multi and name in ("variant", "dither") else ""
        lines.append(f"  {name:<18} {val:<20} {rng:<16} {desc}{note}")

    lines.append(f"\n  output_dir: {output_dir or 'not saved'}")
    lines.append(f"\nEstimated evaluations: {total_evals}")
    lines.append("\nTo start, call optimize again with dry_run=False.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_de(
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None = None,
    pop_size: int = 50,
    n_gen: int = 30,
    variant: str = "DE/rand/1/bin",
    CR: float = 0.7,
    F: float = 0.5,
    dither: str = "vector",
    seed: int | None = None,
    sampling: str = "random",
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str | None = None,
    ctx: "Context | None" = None,
) -> str:
    """Entry point for ``optimize(algorithm='de')``."""
    if not variables:
        return "Error: at least one decision variable is required."
    if not objectives:
        return "Error: at least one objective is required."
    if sampling not in ("random", "lhs"):
        return "Error: sampling must be 'random' or 'lhs'."
    if dither not in ("vector", "scalar", "no"):
        return "Error: dither must be 'vector', 'scalar', or 'no'."

    if dry_run:
        return _format_preview(
            session_name, variables, objectives, constraints,
            pop_size, n_gen, variant, CR, F, dither,
            seed, sampling, max_retries, output_dir,
        )

    result = await _run_de_core(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        pop_size=pop_size, n_gen=n_gen, variant=variant,
        CR=CR, F=F, dither=dither,
        seed=seed, sampling=sampling, max_retries=max_retries,
        output_dir=output_dir, ctx=ctx,
    )
    return result["report"]


async def _run_de_core(
    *,
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    pop_size: int,
    n_gen: int,
    variant: str,
    CR: float,
    F: float,
    dither: str,
    seed: int | None,
    sampling: str,
    max_retries: int,
    output_dir: str | None,
    ctx: "Context | None",
    reporter: ProgressReporter | None = None,
    initial_seeds: list[list[float]] | None = None,
) -> dict:
    if not _PYMOO_AVAILABLE:
        return error_result(
            f"DE requires pymoo and numpy. "
            f"Install with: pip install 'pymoo>=0.6.1'\n({_PYMOO_IMPORT_ERROR})"
        )

    M = len(objectives)
    multi = M >= 2

    if multi and not _GDE3_AVAILABLE:
        return error_result(
            f"Multi-objective DE (GDE3) requires pymoo experimental module. "
            f"Install with: pip install 'pymoo>=0.6.1'. GDE3 is in pymoo.experimental "
            f"and may not be available in all versions.\n({_GDE3_IMPORT_ERROR})"
        )

    err = validate_session(manager, session_name)
    if err is not None:
        return err

    np = _np
    Callback = _PymooCallback
    Problem = _PymooProblem
    FloatRandomSampling = _FloatRandomSampling
    pymoo_minimize = _pymoo_minimize

    algo_name = "GDE3" if multi else "DE"

    weights = tuple(1.0 if o.get("direction", "minimize").lower() == "maximize" else -1.0
                    for o in objectives)
    var_names = unique_names([v["aspen_path"] for v in variables])
    obj_labels = [obj_label(o) for o in objectives]
    obj_dirs = [o.get("direction", "minimize")[:3] for o in objectives]

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
            algorithm=algo_name, total_evals=total_evals, n_iterations=n_gen,
            obj_names=obj_labels, iteration_label="Generation", mcp_ctx=ctx,
        )
    else:
        reporter.set_algorithm(algo_name, iteration_label="Generation")

    n_var = len(variables)
    lows = np.array([v["lower"] for v in variables], dtype=float)
    highs = np.array([v["upper"] for v in variables], dtype=float)

    aborted = False
    cancelled = False          # the user cancelled (aborted also covers a failure limit)
    _current_gen = {"g": 0}

    n_constr = 1 if constraints else 0

    # --- Problem wrapping evaluate_x --------------------------------------
    class _AspenProblem(Problem):
        def __init__(self):
            super().__init__(n_var=n_var, n_obj=M, n_ieq_constr=n_constr,
                             xl=lows, xu=highs)

        def _evaluate(self, X, out, *args, **kwargs):
            nonlocal best_objs, aborted, cancelled
            F_mat = np.zeros((X.shape[0], M))
            G_mat = np.zeros((X.shape[0], n_constr)) if n_constr else None
            for i in range(X.shape[0]):
                if aborted:
                    F_mat[i] = np.full(M, 1e10)
                    if G_mat is not None:
                        G_mat[i, 0] = INFEASIBLE_VIOLATION
                    continue
                if reporter.poll_cancel():
                    aborted = cancelled = True
                    F_mat[i] = np.full(M, 1e10)
                    if G_mat is not None:
                        G_mat[i, 0] = INFEASIBLE_VIOLATION
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
                    F_mat[i] = np.full(M, 1e10)
                    if G_mat is not None:
                        G_mat[i, 0] = INFEASIBLE_VIOLATION
                    logger.warning("%s aborted: %s", algo_name, exc)
                    continue

                decoded = decode_x(X[i].tolist(), variables)
                eval_log.append((_current_gen["g"], decoded, list(f_vals), feasible,
                                 time.time() - start,
                                 _info.get("reason", ""), _info.get("detail", "")))

                if feasible:
                    if best_objs is None:
                        best_objs = list(f_vals)
                    else:
                        for j, (w_, v, b) in enumerate(zip(weights, f_vals, best_objs)):
                            if (w_ > 0 and v > b) or (w_ < 0 and v < b):
                                best_objs[j] = v

                F_mat[i] = np.array([-w_ * f for f, w_ in zip(f_vals, weights)])
                if G_mat is not None:
                    G_mat[i, 0] = violation

                # Per-evaluation progress update
                try:
                    reporter.update_sync(
                        _current_gen["g"],
                        stats.total,
                        f"Gen {_current_gen['g']}/{n_gen} eval {stats.total}",
                        best_objs,
                    )
                except OptimizationCancelled:
                    aborted = cancelled = True

            out["F"] = F_mat
            if G_mat is not None:
                out["G"] = G_mat

    # --- Progress callback ------------------------------------------------
    class _PymooCB(Callback):
        def notify(self, algorithm):
            nonlocal aborted, cancelled
            # Academic numbering: pymoo's gen 1 = init (gen 0); pymoo gen N = academic gen N-1
            academic_gen = algorithm.n_gen - 1
            _current_gen["g"] = algorithm.n_gen
            eval_count = algorithm.evaluator.n_eval
            try:
                reporter.update_sync(
                    academic_gen,
                    eval_count,
                    f"Generation {academic_gen}/{n_gen}",
                    best_objs,
                )
            except OptimizationCancelled:
                aborted = cancelled = True
                algorithm.termination.force_termination = True

    # --- Initial sampling -------------------------------------------------
    if initial_seeds:
        seed_arr = np.array(initial_seeds[:pop_size])
        if len(seed_arr) < pop_size:
            extra = (lhs_sample(pop_size - len(seed_arr), variables)
                     if sampling == "lhs"
                     else [[random.uniform(v["lower"], v["upper"]) for v in variables]
                           for _ in range(pop_size - len(seed_arr))])
            seed_arr = np.vstack([seed_arr, np.array(extra)])
        sampling_obj = seed_arr
    elif sampling == "lhs":
        sampling_obj = np.array(lhs_sample(pop_size, variables))
    else:
        sampling_obj = FloatRandomSampling()

    # --- Build algorithm --------------------------------------------------
    start = time.time()
    try:
        if multi:
            gde3_variant = _Variant(selection="rand", F=F, CR=CR, crossover="bin")
            algo = _GDE3(variant=gde3_variant, pop_size=pop_size, sampling=sampling_obj)
        else:
            algo = _DE(
                pop_size=pop_size,
                variant=variant,
                CR=CR, F=F, dither=dither,
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
        aborted = cancelled = True
        res = None
        logger.info("%s cancelled by user", algo_name)
    except OptimizationAborted as exc:
        aborted = True
        res = None
        logger.warning("%s aborted at outer level: %s", algo_name, exc)

    wall_time = time.time() - start

    if owns_reporter:
        reporter.finalize(aborted)

    # --- Extract Pareto front / best solution -----------------------------
    pareto: list[dict] = []
    if res is not None and res.F is not None:
        X_res = res.X if res.X.ndim == 2 else res.X.reshape(1, -1)
        F_res = res.F if res.F.ndim == 2 else res.F.reshape(1, -1)
        for x_row, f_row in zip(X_res, F_res):
            raw_f = [(-w_) * fv for fv, w_ in zip(f_row, weights)]
            if is_feasible_values(raw_f):
                pareto.append({"x": decode_x(x_row.tolist(), variables), "f": raw_f})
        pareto.sort(key=lambda p: p["f"][0])

    fitness_matrix = [p["f"] for p in pareto]
    comp_idx = best_compromise(fitness_matrix, weights) if pareto else -1

    # --- Report -----------------------------------------------------------
    def _fmt_point(p):
        xs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, p["x"]))
        fs = ", ".join(f"{n}={v:.4g} ({dr})"
                       for n, v, dr in zip(obj_labels, p["f"], obj_dirs))
        return f"{xs} -> {fs}"

    header = "ABORTED" if aborted else f"{algo_name} complete"
    lines = [f"{header}: {n_gen} generations, {pop_size} population, "
             f"wall-time {wall_time:.1f}s",
             f"\n{'Pareto Front' if multi else 'Best solution'} ({len(pareto)}"
             f"{' solutions' if multi else ''}):",
             ]
    for idx, p in enumerate(pareto):
        marker = " <<<" if idx == comp_idx else ""
        lines.append(f"  #{idx + 1}: {_fmt_point(p)}{marker}")

    if pareto and comp_idx >= 0 and multi:
        lines.append(f"\nBest compromise: {_fmt_point(pareto[comp_idx])}")

    gen_logged = _current_gen["g"]
    if aborted and gen_logged > 0:
        lines.append(f"\n{'CANCELLED by user' if cancelled else 'Stopped'} at gen {gen_logged}, "
                     f"eval {stats.total}")

    lines.append("")
    lines.append(stats.format_report())

    if debug_log:
        unique_msgs = list(dict.fromkeys(debug_log[:20]))
        lines.append(f"\nFailure details ({len(debug_log)}):")
        lines += [f"  {m}" for m in unique_msgs]

    log_lines = [f"{algo_name}: {n_gen} gens, {pop_size} pop"]

    if output_dir:
        try:
            settings = {
                "Algorithm": algo_name,
                "Population": pop_size,
                "Generations": n_gen,
                "Variant": variant if not multi else "GDE3 (rand/bin)",
                "CR": CR,
                "F": F,
                "Dither": dither if not multi else "N/A",
                "Seed": seed if seed is not None else "random",
                "Sampling": sampling,
                "Max retries": max_retries,
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm=algo_name.lower(),
                session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings, pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save %s results: %s", algo_name, e, exc_info=True)
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
