"""Exhaustive grid search over the decision space.

Unlike the optimizers, this tool does NOT try to find an optimum — it sweeps a
regular grid over every decision variable and evaluates Aspen at each node,
recording the objective values, feasibility, and the *reason / detailed Aspen
error* for every point. The result is a ground-truth map of the feasible /
infeasible region (and its failure modes), which is the reference used to
validate boundary-seeking optimizers such as CBO.

Output is written through ``save_results_generic`` so ``evaluations.csv`` has
the same schema as the optimizers (including the ``reason`` and ``error_detail``
columns), making downstream analysis identical.
"""

from __future__ import annotations

import itertools
import logging
import time
from typing import TYPE_CHECKING

from tools._common_eval import (
    EvalStats,
    OptimizationAborted,
    OptimizationCancelled,
    ProgressReporter,
    decode_x,
    evaluate_x,
    obj_label,
    save_results_generic,
    unique_names,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context

# Safety cap: refuse to actually run a grid larger than this unless the caller
# raises max_points explicitly. A full Aspen evaluation can take seconds, so a
# careless 5-variable × 20-point grid (3.2M points) would run for weeks.
DEFAULT_MAX_POINTS = 20000


# ---------------------------------------------------------------------------
# Grid construction
# ---------------------------------------------------------------------------

def _axis_values(var: dict, default_points: int) -> list[float]:
    """Return the evenly-spaced sample values for one decision variable.

    ``var`` may carry an optional ``points`` key to override the global
    ``default_points`` for that axis. Integer variables are rounded and
    de-duplicated so the axis only contains distinct integers.
    """
    n = int(var.get("points", default_points))
    lo, hi = float(var["lower"]), float(var["upper"])
    if n < 1:
        n = 1
    if n == 1:
        vals = [(lo + hi) / 2.0]
    else:
        step = (hi - lo) / (n - 1)
        vals = [lo + i * step for i in range(n)]
    if var.get("type") == "int":
        seen: list[float] = []
        for v in vals:
            iv = float(int(round(v)))
            if iv not in seen:
                seen.append(iv)
        vals = seen
    return vals


def _build_axes(variables: list[dict], default_points: int) -> list[list[float]]:
    return [_axis_values(v, default_points) for v in variables]


def _total_points(axes: list[list[float]]) -> int:
    total = 1
    for ax in axes:
        total *= len(ax)
    return total


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def _format_preview(
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    axes: list[list[float]],
    points_per_dim: int,
    max_points: int,
    output_dir: str | None,
) -> str:
    total = _total_points(axes)
    var_names = unique_names([v["aspen_path"] for v in variables])
    lines = [
        f"GRID SEARCH preview - session '{session_name}'",
        f"\nTotal grid points: {total}",
        f"(safety cap max_points = {max_points})",
        "\nAxes:",
    ]
    for name, v, ax in zip(var_names, variables, axes):
        rng = f"{ax[0]:.4g} .. {ax[-1]:.4g}" if len(ax) > 1 else f"{ax[0]:.4g}"
        lines.append(f"  {name}: {len(ax)} points  [{rng}]"
                     f"{'  (int)' if v.get('type') == 'int' else ''}")
    lines.append("\nObjectives:")
    if objectives:
        for o in objectives:
            lines.append(f"  {obj_label(o)}  ({o.get('direction', 'minimize')})")
    else:
        lines.append("  (none - feasibility-only map)")
    if constraints:
        lines.append("\nConstraints:")
        for c in constraints:
            c_label = obj_label(c) if "aspen_paths" in c else c["aspen_path"]
            lines.append(f"  {c_label}  "
                         f"[{c.get('lower', '-')}, {c.get('upper', '-')}]")
    if total > max_points:
        lines.append(
            f"\n[!] {total} points exceeds max_points ({max_points}). "
            f"Either reduce points_per_dim / bounds, or pass a larger "
            f"max_points to run anyway."
        )
    lines.append("\nEach point runs one full Aspen evaluation; total time ~= "
                 "total_points x per-eval time.")
    lines.append("To start, call optimize again with dry_run=False.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run_gridsearch(
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict] | None = None,
    constraints: list[dict] | None = None,
    points_per_dim: int = 10,
    max_points: int = DEFAULT_MAX_POINTS,
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str | None = None,
    ctx: "Context | None" = None,
) -> str:
    """Entry point for ``optimize(algorithm='grid')``."""
    if not variables:
        return "Error: at least one decision variable is required."
    for v in variables:
        if not all(k in v for k in ("aspen_path", "lower", "upper")):
            return "Error: each variable needs 'aspen_path', 'lower', and 'upper'."
    objectives = objectives or []
    for o in objectives:
        if "aspen_path" not in o and "aspen_paths" not in o:
            return "Error: each objective needs 'aspen_path' or 'aspen_paths'."

    axes = _build_axes(variables, points_per_dim)
    total = _total_points(axes)

    if dry_run:
        return _format_preview(session_name, variables, objectives, constraints,
                               axes, points_per_dim, max_points, output_dir)

    if manager.get_app(session_name) is None:
        return (f"Error: no active Aspen session '{session_name}'. "
                f"Open Aspen first with open_aspen_plus.")
    if total > max_points:
        return (f"Error: grid has {total} points, exceeding max_points "
                f"({max_points}). Reduce points_per_dim/bounds or raise "
                f"max_points to run anyway.")

    weights = tuple(1.0 if o.get("direction", "minimize").lower() == "maximize" else -1.0
                    for o in objectives)
    obj_labels = [obj_label(o) for o in objectives]

    debug_log: list[str] = []
    stats = EvalStats()
    eval_log: list[tuple] = []
    aborted = False
    abort_reason: str | None = None

    reporter = ProgressReporter(
        algorithm="Grid Search",
        total_evals=total,
        n_iterations=1,
        obj_names=obj_labels,
        iteration_label="Point",
        mcp_ctx=ctx,
    )

    start = time.time()
    try:
        for idx, combo in enumerate(itertools.product(*axes)):
            if reporter.poll_cancel():
                aborted = True
                break
            x = list(combo)
            try:
                f_vals, feasible, _ = evaluate_x(
                    x,
                    manager=manager, session_name=session_name,
                    variables=variables, objectives=objectives,
                    constraints=constraints, weights=weights,
                    max_retries=max_retries,
                    debug_log=debug_log, stats=stats,
                    info=(_info := {}),
                )
            except OptimizationAborted as exc:
                aborted = True
                abort_reason = str(exc)
                logger.warning("Grid search aborted: %s", exc)
                break
            decoded = decode_x(x, variables)
            eval_log.append((0, decoded, list(f_vals), feasible,
                             time.time() - start,
                             _info.get("reason", ""), _info.get("detail", "")))
            await reporter.update(0, idx + 1, f"Point {idx + 1}/{total}", None)
    except OptimizationCancelled:
        aborted = True
        abort_reason = "Cancelled by user"

    wall_time = time.time() - start
    reporter.finalize(aborted, abort_reason)

    # Feasibility summary
    n_done = len(eval_log)
    n_feasible = sum(1 for e in eval_log if e[3])
    fr = (n_feasible / n_done) if n_done else 0.0
    log_lines = [
        f"Grid points evaluated: {n_done}/{total}",
        f"Feasible: {n_feasible} ({fr * 100:.1f}%)",
        f"Infeasible: {n_done - n_feasible}",
        f"Wall-time: {wall_time:.1f}s",
    ]
    if aborted:
        log_lines.append(f"ABORTED: {abort_reason}")

    settings = {
        "points_per_dim": points_per_dim,
        "total_grid_points": total,
        "points_evaluated": n_done,
        "feasibility_ratio": f"{fr:.3f}",
        "max_retries": max_retries,
    }

    run_dir = save_results_generic(
        algorithm="GridSearch",
        session_name=session_name,
        variables=variables,
        objectives=objectives,
        constraints=constraints,
        settings=settings,
        pareto=[],
        weights=weights,
        log_lines=log_lines,
        eval_log=eval_log,
        stats=stats,
        output_dir=output_dir or ".",
    )

    report = [
        ("Grid search ABORTED" if aborted else "Grid search complete")
        + f": {n_done}/{total} points, {wall_time:.1f}s",
        f"Feasible: {n_feasible} ({fr * 100:.1f}%) | Infeasible: {n_done - n_feasible}",
    ]
    if stats.by_reason:
        report.append("Failure breakdown: "
                      + ", ".join(f"{k}={v}" for k, v in
                                  sorted(stats.by_reason.items(), key=lambda kv: -kv[1])))
    report.append(f"Results saved to: {run_dir}")
    report.append("evaluations.csv contains per-point feasibility, reason and "
                  "error_detail (the Aspen failure keyword).")
    return "\n".join(report)
