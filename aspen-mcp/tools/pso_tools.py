"""Particle Swarm Optimization — PSO (single objective) and MOPSO (multi-objective).

Single-objective uses pymoo's classical PSO. Multi-objective uses a custom MOPSO
implementation with external archive, crowding-distance leader selection, and
adaptive inertia weight.
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

# Eager-import heavy deps so first call doesn't stall MCP event loop
try:
    import numpy as _np
    from pymoo.algorithms.soo.nonconvex.pso import PSO as _PSO
    from pymoo.core.callback import Callback as _PymooCallback
    from pymoo.core.problem import Problem as _PymooProblem
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
# MOPSO helpers
# ---------------------------------------------------------------------------

def _dominates_min(a: list[float], b: list[float]) -> bool:
    """Return True if *a* dominates *b* under minimization."""
    better = False
    for ai, bi in zip(a, b):
        if ai > bi:
            return False
        if ai < bi:
            better = True
    return better


def _crowding_distance(archive_f: list[list[float]]) -> list[float]:
    """Crowding distance for a set of objective vectors (minimization)."""
    n = len(archive_f)
    if n <= 2:
        return [float("inf")] * n
    M = len(archive_f[0])
    dist = [0.0] * n
    for m in range(M):
        order = sorted(range(n), key=lambda i: archive_f[i][m])
        dist[order[0]] = float("inf")
        dist[order[-1]] = float("inf")
        f_range = archive_f[order[-1]][m] - archive_f[order[0]][m]
        if f_range == 0:
            continue
        for i in range(1, n - 1):
            dist[order[i]] += (
                (archive_f[order[i + 1]][m] - archive_f[order[i - 1]][m]) / f_range
            )
    return dist


def _update_archive(
    archive_x: list, archive_f: list, new_x, new_f: list[float], max_size: int
) -> None:
    """Insert *new_x* into the archive if non-dominated; prune if oversized."""
    to_remove: list[int] = []
    for i, af in enumerate(archive_f):
        if _dominates_min(af, new_f):
            return  # new solution is dominated
        if _dominates_min(new_f, af):
            to_remove.append(i)
    for i in reversed(to_remove):
        archive_x.pop(i)
        archive_f.pop(i)
    archive_x.append(new_x.copy() if hasattr(new_x, "copy") else list(new_x))
    archive_f.append(list(new_f))
    if len(archive_x) > max_size:
        cd = _crowding_distance(archive_f)
        # remove the member with the smallest crowding distance
        worst = min(
            (i for i in range(len(cd)) if cd[i] != float("inf")),
            key=lambda i: cd[i],
            default=0,
        )
        archive_x.pop(worst)
        archive_f.pop(worst)


def _select_leader(archive_f: list[list[float]]) -> int:
    """Binary tournament on crowding distance to pick a leader."""
    n = len(archive_f)
    if n <= 2:
        return random.randint(0, n - 1)
    cd = _crowding_distance(archive_f)
    i, j = random.sample(range(n), 2)
    return i if cd[i] >= cd[j] else j


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def _format_preview(
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    swarm_size: int,
    n_iterations: int,
    w: float,
    c1: float,
    c2: float,
    seed: int | None,
    sampling: str,
    max_retries: int,
    output_dir: str | None,
) -> str:
    var_names = unique_names([v["aspen_path"] for v in variables])
    M = len(objectives)
    backend = "PSO (single-objective)" if M == 1 else f"MOPSO ({M} objectives)"
    # n_iterations = total iterations including init.
    total_evals = swarm_size * n_iterations

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
        ("swarm_size",    str(swarm_size),    "particles per iteration"),
        ("n_iterations",  str(n_iterations),  "number of iterations"),
        ("w",             str(w),             "inertia weight (0.4-0.9 typical)"),
        ("c1",            str(c1),            "cognitive coef (1-2.5)"),
        ("c2",            str(c2),            "social coef (1-2.5)"),
        ("sampling",      sampling,           "random or lhs"),
        ("seed",          str(seed) if seed is not None else "random", "random seed"),
        ("max_retries",   str(max_retries),   "simulation retry count"),
    ]
    for name, val, desc in params:
        lines.append(f"  {name:<16} {val:<16} {desc}")
    lines.append(f"\n  output_dir: {output_dir or 'not saved'}")
    lines.append("\nTo start, call optimize again with dry_run=False.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_pso(
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None = None,
    swarm_size: int = 40,
    n_iterations: int = 30,
    w: float = 0.9,
    c1: float = 2.0,
    c2: float = 2.0,
    seed: int | None = None,
    sampling: str = "random",
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str | None = None,
    ctx: "Context | None" = None,
) -> str:
    """Entry point for ``optimize(algorithm='pso')``."""
    if not variables:
        return "Error: at least one decision variable is required."
    if not objectives:
        return "Error: at least one objective is required."
    if sampling not in ("random", "lhs"):
        return "Error: sampling must be 'random' or 'lhs'."

    if dry_run:
        return _format_preview(
            session_name, variables, objectives, constraints,
            swarm_size, n_iterations, w, c1, c2, seed, sampling,
            max_retries, output_dir,
        )

    result = await _run_pso_core(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        swarm_size=swarm_size, n_iterations=n_iterations,
        w=w, c1=c1, c2=c2, seed=seed, sampling=sampling,
        max_retries=max_retries, output_dir=output_dir, ctx=ctx,
    )
    return result["report"]


# ---------------------------------------------------------------------------
# MOPSO loop
# ---------------------------------------------------------------------------

def _run_mopso_loop(
    *,
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    weights: tuple,
    swarm_size: int,
    n_iterations: int,
    w: float,
    c1: float,
    c2: float,
    lows,          # np.ndarray
    highs,         # np.ndarray
    n_var: int,
    M: int,
    sampling: str,
    max_retries: int,
    debug_log: list[str],
    stats,
    eval_log: list[tuple],
    reporter,
    initial_seeds: list[list[float]] | None,
    np,            # numpy module reference
) -> dict:
    """Run Multi-Objective PSO with external archive and crowding-distance
    leader selection.  Returns dict with pareto, wall_time, aborted, best_objs.
    """
    ARCHIVE_MAX = swarm_size * 3  # archive capacity
    v_range = highs - lows
    v_max = v_range * 0.5  # velocity clamp

    # --- initialise positions ------------------------------------------------
    if initial_seeds:
        positions = np.array(initial_seeds[:swarm_size], dtype=float)
        if len(positions) < swarm_size:
            extra = (lhs_sample(swarm_size - len(positions), variables)
                     if sampling == "lhs"
                     else [[random.uniform(v["lower"], v["upper"]) for v in variables]
                           for _ in range(swarm_size - len(positions))])
            positions = np.vstack([positions, np.array(extra, dtype=float)])
    elif sampling == "lhs":
        positions = np.array(lhs_sample(swarm_size, variables), dtype=float)
    else:
        positions = np.random.uniform(lows, highs, (swarm_size, n_var))

    velocities = np.random.uniform(-v_max, v_max, (swarm_size, n_var))

    # personal bests (minimisation form: multiply by -weight)
    pbest_pos = positions.copy()
    pbest_f_min = np.full((swarm_size, M), 1e10)   # minimisation values
    pbest_f_raw = np.full((swarm_size, M), 1e10)    # original-scale values

    archive_x: list = []
    archive_f_min: list[list[float]] = []   # minimisation form

    best_objs: list[float] | None = None
    aborted = False

    def _eval_particle(idx: int, pos, iteration: int):
        """Evaluate one particle; return (raw_f, min_f, feasible)."""
        nonlocal best_objs, aborted
        if aborted:
            return None, None, False
        if reporter.poll_cancel():
            aborted = True
            return None, None, False
        try:
            f_vals, feasible, _reason = evaluate_x(
                pos.tolist(),
                manager=manager, session_name=session_name,
                variables=variables, objectives=objectives,
                constraints=constraints, weights=weights,
                max_retries=max_retries,
                debug_log=debug_log, stats=stats,
                info=(_info := {}),
            )
        except OptimizationAborted:
            aborted = True
            return None, None, False

        decoded = decode_x(pos.tolist(), variables)
        eval_log.append((iteration, decoded, list(f_vals), feasible,
                         time.time() - start,
                         _info.get("reason", ""), _info.get("detail", "")))

        if feasible:
            if best_objs is None:
                best_objs = list(f_vals)
            else:
                for j, (wt, v, b) in enumerate(zip(weights, f_vals, best_objs)):
                    if (wt > 0 and v > b) or (wt < 0 and v < b):
                        best_objs[j] = v

        # minimisation form for internal use
        min_f = [-wt * fv for fv, wt in zip(f_vals, weights)]
        return list(f_vals), min_f, feasible

    start = time.time()

    try:
        # --- initial evaluation ----------------------------------------------
        for i in range(swarm_size):
            if aborted:
                break
            raw_f, min_f, feasible = _eval_particle(i, positions[i], 0)
            if raw_f is not None and feasible:
                pbest_pos[i] = positions[i].copy()
                pbest_f_min[i] = np.array(min_f)
                pbest_f_raw[i] = np.array(raw_f)
                _update_archive(archive_x, archive_f_min,
                                positions[i], min_f, ARCHIVE_MAX)
            try:
                reporter.update_sync(
                    0, stats.total,
                    f"Iter 0/{n_iterations} eval {stats.total}/{swarm_size}",
                    best_objs,
                )
            except OptimizationCancelled:
                aborted = True

        # --- main loop -------------------------------------------------------
        # n_iterations counts the init pass, so we run (n_iterations - 1) more loops.
        w_start, w_end = w, 0.4  # adaptive inertia
        for iteration in range(1, n_iterations):
            if aborted:
                break
            # linearly decay inertia weight
            w_cur = w_start - (w_start - w_end) * iteration / n_iterations

            for i in range(swarm_size):
                if aborted:
                    break
                # select leader from archive
                if archive_x:
                    leader_idx = _select_leader(archive_f_min)
                    gbest = np.array(archive_x[leader_idx], dtype=float)
                else:
                    gbest = pbest_pos[i]

                r1 = np.random.random(n_var)
                r2 = np.random.random(n_var)

                # velocity update
                velocities[i] = (w_cur * velocities[i]
                                 + c1 * r1 * (pbest_pos[i] - positions[i])
                                 + c2 * r2 * (gbest - positions[i]))
                # clamp velocity
                velocities[i] = np.clip(velocities[i], -v_max, v_max)
                # position update
                positions[i] = positions[i] + velocities[i]
                # clamp position to bounds
                positions[i] = np.clip(positions[i], lows, highs)

                # evaluate
                raw_f, min_f, feasible = _eval_particle(i, positions[i], iteration)
                if raw_f is None or not feasible:
                    continue

                # update personal best (if new dominates old)
                old_min = pbest_f_min[i].tolist()
                if _dominates_min(min_f, old_min) or not _dominates_min(old_min, min_f):
                    # new dominates old, or they are non-dominated → accept new
                    if _dominates_min(min_f, old_min) or random.random() < 0.5:
                        pbest_pos[i] = positions[i].copy()
                        pbest_f_min[i] = np.array(min_f)
                        pbest_f_raw[i] = np.array(raw_f)

                _update_archive(archive_x, archive_f_min,
                                positions[i], min_f, ARCHIVE_MAX)

                try:
                    reporter.update_sync(
                        iteration, stats.total,
                        f"Iter {iteration}/{n_iterations} eval {stats.total}",
                        best_objs,
                    )
                except OptimizationCancelled:
                    aborted = True
    except OptimizationCancelled:
        aborted = True
        logger.info("MOPSO cancelled by user")

    wall_time = time.time() - start

    # --- build pareto list ---------------------------------------------------
    pareto: list[dict] = []
    for ax, af_min in zip(archive_x, archive_f_min):
        # convert back to original scale
        raw_f = [(-wt) * fv for fv, wt in zip(af_min, weights)]
        if is_feasible_values(raw_f):
            pareto.append({"x": decode_x(list(ax), variables), "f": raw_f})
    pareto.sort(key=lambda p: p["f"][0])

    return {
        "pareto": pareto,
        "wall_time": wall_time,
        "aborted": aborted,
        "best_objs": best_objs,
    }


# ---------------------------------------------------------------------------
# Main core
# ---------------------------------------------------------------------------

async def _run_pso_core(
    *,
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    swarm_size: int,
    n_iterations: int,
    w: float,
    c1: float,
    c2: float,
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
            f"PSO requires pymoo and numpy. pip install 'pymoo>=0.6.1'\n{_PYMOO_IMPORT_ERROR}"
        )

    err = validate_session(manager, session_name)
    if err is not None:
        return err

    np = _np
    Callback = _PymooCallback
    Problem = _PymooProblem
    FloatRandomSampling = _FloatRandomSampling
    pymoo_minimize = _pymoo_minimize

    M = len(objectives)
    multi = M >= 2

    weights = tuple(1.0 if o.get("direction", "minimize").lower() == "maximize" else -1.0
                    for o in objectives)
    var_names = unique_names([v["aspen_path"] for v in variables])
    obj_labels = [obj_label(o) for o in objectives]
    obj_dirs = [o.get("direction", "minimize")[:3] for o in objectives]
    algo_name = "PSO" if not multi else "MOPSO"

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    else:
        random.seed()

    debug_log: list[str] = []
    stats = EvalStats()
    eval_log: list[tuple] = []
    best_objs: list[float] | None = None
    aborted = False

    # n_iterations = total iterations (including init). MOPSO runs init + (n_iterations-1)
    # main loops; pymoo single-PSO terminates at ("n_gen", n_iterations).
    total_evals = swarm_size * n_iterations
    owns_reporter = reporter is None
    if reporter is None:
        reporter = ProgressReporter(
            algorithm=algo_name, total_evals=total_evals, n_iterations=n_iterations,
            obj_names=obj_labels, iteration_label="Iteration", mcp_ctx=ctx,
        )
    else:
        reporter.set_algorithm(algo_name, iteration_label="Iteration")

    n_var = len(variables)
    lows = np.array([v["lower"] for v in variables], dtype=float)
    highs = np.array([v["upper"] for v in variables], dtype=float)

    # ---- Branch: multi-objective → MOPSO, single-objective → pymoo PSO ----
    if multi:
        mopso_result = _run_mopso_loop(
            manager=manager, session_name=session_name,
            variables=variables, objectives=objectives,
            constraints=constraints, weights=weights,
            swarm_size=swarm_size, n_iterations=n_iterations,
            w=w, c1=c1, c2=c2,
            lows=lows, highs=highs, n_var=n_var, M=M,
            sampling=sampling, max_retries=max_retries,
            debug_log=debug_log, stats=stats, eval_log=eval_log,
            reporter=reporter, initial_seeds=initial_seeds,
            np=np,
        )
        pareto = mopso_result["pareto"]
        wall_time = mopso_result["wall_time"]
        aborted = mopso_result["aborted"]
        best_objs = mopso_result["best_objs"]
    else:
        # Single-objective: pymoo PSO
        _current_iter = {"g": 0}

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
                        logger.warning("%s aborted: %s", algo_name, exc)
                        continue

                    decoded = decode_x(X[i].tolist(), variables)
                    eval_log.append((_current_iter["g"], decoded, list(f_vals), feasible,
                                     time.time() - start,
                                     _info.get("reason", ""), _info.get("detail", "")))

                    if feasible:
                        if best_objs is None:
                            best_objs = list(f_vals)
                        else:
                            for j, (w_, v, b) in enumerate(zip(weights, f_vals, best_objs)):
                                if (w_ > 0 and v > b) or (w_ < 0 and v < b):
                                    best_objs[j] = v

                    F[i] = np.array([-wt * f for f, wt in zip(f_vals, weights)])
                    if G is not None:
                        G[i, 0] = violation

                    # Per-evaluation progress update
                    try:
                        reporter.update_sync(
                            _current_iter["g"], stats.total,
                            f"Iter {_current_iter['g']}/{n_iterations} eval {stats.total}",
                            best_objs,
                        )
                    except OptimizationCancelled:
                        aborted = True

                out["F"] = F
                if G is not None:
                    out["G"] = G

        class _PymooCB(Callback):
            def notify(self, algorithm):
                nonlocal aborted
                # Academic numbering: pymoo's gen 1 = init (iter 0); pymoo gen N = academic iter N-1
                academic_iter = algorithm.n_gen - 1
                _current_iter["g"] = algorithm.n_gen
                eval_count = algorithm.evaluator.n_eval
                try:
                    reporter.update_sync(
                        academic_iter,
                        eval_count,
                        f"Iteration {academic_iter}/{n_iterations}",
                        best_objs,
                    )
                except OptimizationCancelled:
                    aborted = True
                    algorithm.termination.force_termination = True

        if initial_seeds:
            seed_arr = np.array(initial_seeds[:swarm_size])
            if len(seed_arr) < swarm_size:
                extra = (lhs_sample(swarm_size - len(seed_arr), variables)
                         if sampling == "lhs"
                         else [[random.uniform(v["lower"], v["upper"]) for v in variables]
                               for _ in range(swarm_size - len(seed_arr))])
                seed_arr = np.vstack([seed_arr, np.array(extra)])
            sampling_obj = seed_arr
        elif sampling == "lhs":
            sampling_obj = np.array(lhs_sample(swarm_size, variables))
        else:
            sampling_obj = FloatRandomSampling()

        start = time.time()
        try:
            algo = _PSO(pop_size=swarm_size, w=w, c1=c1, c2=c2, sampling=sampling_obj)
            # n_iterations = total iterations (including init swarm).
            res = pymoo_minimize(
                _AspenProblem(), algo, ("n_gen", n_iterations),
                seed=seed if seed is not None else None,
                callback=_PymooCB(),
                verbose=False,
            )
        except OptimizationCancelled:
            aborted = True
            res = None
            logger.info("%s cancelled by user", algo_name)
        except OptimizationAborted as exc:
            aborted = True
            res = None
            logger.warning("%s aborted at outer level: %s", algo_name, exc)

        wall_time = time.time() - start

        pareto: list[dict] = []
        if res is not None and res.F is not None:
            X = res.X if res.X.ndim == 2 else res.X.reshape(1, -1)
            F = res.F if res.F.ndim == 2 else res.F.reshape(1, -1)
            for x_row, f_row in zip(X, F):
                raw_f = [(-w_) * fv for fv, w_ in zip(f_row, weights)]
                if is_feasible_values(raw_f):
                    pareto.append({"x": decode_x(x_row.tolist(), variables), "f": raw_f})
            pareto.sort(key=lambda p: p["f"][0])

    if owns_reporter:
        reporter.finalize(aborted)

    fitness_matrix = [p["f"] for p in pareto]
    comp_idx = best_compromise(fitness_matrix, weights) if pareto else -1

    def _fmt_point(p):
        xs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, p["x"]))
        fs = ", ".join(f"{n}={v:.4g} ({dr})"
                       for n, v, dr in zip(obj_labels, p["f"], obj_dirs))
        return f"{xs} -> {fs}"

    header = "ABORTED" if aborted else f"{algo_name} complete"
    lines = [f"{header}: {n_iterations} iterations, {swarm_size} particles, "
             f"wall-time {wall_time:.1f}s",
             f"\n{'Pareto Front' if multi else 'Best solution'} ({len(pareto)}):"]
    for idx, p in enumerate(pareto):
        marker = " <<<" if idx == comp_idx else ""
        lines.append(f"  #{idx + 1}: {_fmt_point(p)}{marker}")

    if pareto and comp_idx >= 0 and multi:
        lines.append(f"\nBest compromise: {_fmt_point(pareto[comp_idx])}")

    lines.append("")
    lines.append(stats.format_report())

    if debug_log:
        unique_msgs = list(dict.fromkeys(debug_log[:20]))
        lines.append(f"\nFailure details ({len(debug_log)}):")
        lines += [f"  {m}" for m in unique_msgs]

    log_lines = [f"{algo_name}: {n_iterations} iters, {swarm_size} particles"]

    if output_dir:
        try:
            settings = {
                "Algorithm": algo_name,
                "Swarm size": swarm_size,
                "Iterations": n_iterations,
                "Inertia w": w,
                "c1": c1,
                "c2": c2,
                "Seed": seed if seed is not None else "random",
                "Sampling": sampling,
                "Max retries": max_retries,
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm=algo_name, session_name=session_name,
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


