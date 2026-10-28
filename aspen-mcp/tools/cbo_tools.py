"""Constrained Bayesian Optimization for Aspen Plus.

Key differences vs. ``bo_tools.py``:

- **Failed points are NEVER fed to the objective GP.** They only contribute to a
  separate feasibility GP (Gelbart et al. 2014). This avoids the ``1e10`` penalty
  values from corrupting the objective GP's length scales.
- **Feasibility GP classifier**: a SingleTaskGP regressed on ``{0, 1}`` labels
  over *all* evaluated points. Its posterior approximates ``P(feasible | x)``.
- **Single-objective** uses ``ConstrainedExpectedImprovement`` (analytical cEI).
- **Multi-objective** uses ``qLogNoisyExpectedHypervolumeImprovement`` with a
  feasibility constraint callable (``0.5 − Z[..., -1]``) on a combined
  ``ModelListGP(obj_1, ..., obj_M, feas)``.
- Both variants unify on BoTorch (no skopt fallback).
"""

from __future__ import annotations

import asyncio
import csv
import gc
import logging
import os
import random
import time
from datetime import datetime
from typing import TYPE_CHECKING

from tools._common_eval import (
    ACQF_MAXITER,
    EvalStats,
    OptimizationAborted,
    OptimizationCancelled,
    cancellable,
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
    unpack_eval_entry,
    load_resume_records,
    resolve_resume,
    resume_preview,
    safe_file_part,
)

# Eager-import optional deps at module load (same rationale as bo_tools).
try:
    import numpy as _np  # noqa: F401
    # Imported before torch on purpose: _bo_threads sets OMP_NUM_THREADS at
    # module scope, and an OpenMP runtime reads that only once, when torch
    # loads it -- setting it afterwards is a no-op for the BLAS pools.
    from tools._bo_threads import cap_threads as _cap_threads
    import torch as _torch  # noqa: F401
    _cap_threads()
    from botorch.acquisition.analytic import (  # noqa: F401
        LogConstrainedExpectedImprovement as _LogConstrainedEI,
    )
    from botorch.acquisition.multi_objective.logei import (  # noqa: F401
        qLogNoisyExpectedHypervolumeImprovement as _qLogNEHVI,
    )
    from botorch.acquisition.multi_objective.objective import (  # noqa: F401
        IdentityMCMultiOutputObjective as _IdentityMCMO,
    )
    from botorch.fit import fit_gpytorch_mll as _fit_gpytorch_mll  # noqa: F401
    from botorch.models import ModelListGP as _ModelListGP  # noqa: F401
    from botorch.models import SingleTaskGP as _SingleTaskGP  # noqa: F401
    from botorch.models.transforms import Normalize as _BoTNormalize  # noqa: F401
    from botorch.models.transforms import Standardize as _BoTStandardize  # noqa: F401
    from botorch.optim import optimize_acqf as _optimize_acqf  # noqa: F401
    from botorch.sampling.normal import (  # noqa: F401
        SobolQMCNormalSampler as _SobolQMCNormalSampler,
    )
    from botorch.utils.multi_objective.pareto import (  # noqa: F401
        is_non_dominated as _is_non_dominated,
    )
    from gpytorch.mlls import ExactMarginalLogLikelihood as _ExactMLL  # noqa: F401
    from gpytorch.mlls import SumMarginalLogLikelihood as _SumMLL  # noqa: F401
    _BOTORCH_AVAILABLE = True
    _BOTORCH_IMPORT_ERROR = None
except ImportError as _exc:
    _BOTORCH_AVAILABLE = False
    _BOTORCH_IMPORT_ERROR = str(_exc)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context

CHECKPOINT_INTERVAL = 50


def _checkpoint(output_dir: str | None, session_name: str, variables, objectives,
                eval_log: list[tuple], stats: "EvalStats", _run_dir_holder: list):
    if not output_dir:
        return
    var_names = unique_names([v["aspen_path"] for v in variables])
    obj_names = [obj_label(o) for o in objectives]
    if not _run_dir_holder:
        run_dir = os.path.join(
            output_dir,
            f"opt_cbo-checkpoint_{safe_file_part(session_name)}_{datetime.now():%Y%m%d_%H%M%S}",
        )
        os.makedirs(run_dir, exist_ok=True)
        _run_dir_holder.append(run_dir)
    run_dir = _run_dir_holder[0]
    path = os.path.join(run_dir, "evaluations.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["eval", "iter", "time_s"] + var_names + obj_names
                        + ["feasible", "reason", "error_detail"])
        for eval_idx, entry in enumerate(eval_log, start=1):
            it, decoded, obj_vals, feasible, t_s, reason, detail = unpack_eval_entry(entry)
            writer.writerow([eval_idx, it, f"{t_s:.4f}"]
                            + [f"{v:.6g}" for v in decoded]
                            + [f"{v:.6g}" for v in obj_vals]
                            + [int(feasible), reason, detail])
    logger.info("Checkpoint saved: %d evaluations -> %s", len(eval_log), path)


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def _format_preview(
    session_name, variables, objectives, constraints,
    n_initial, n_iterations, q, seed, max_retries, output_dir,
) -> str:
    var_names = unique_names([v["aspen_path"] for v in variables])
    M = len(objectives)
    backend = "BoTorch cEI (single-obj + feasibility GP)" if M == 1 \
        else f"BoTorch constrained qLogNEHVI ({M} objectives + feasibility GP)"
    total_evals = n_initial + n_iterations * (q if M >= 2 else 1)

    lines = [
        f"=== Constrained BO ({backend}) Settings Preview ===",
        f"\nSession: {session_name}",
        f"Estimated evaluations: {total_evals} ({n_initial} initial + {n_iterations} cBO iters)",
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
        ("n_initial",    str(n_initial),    "LHS initial samples before cBO starts"),
        ("n_iterations", str(n_iterations), "cBO iterations after initial"),
        ("q",            str(q),            "batch size (multi-obj only)"),
        ("seed",         str(seed) if seed is not None else "random", "random seed"),
        ("max_retries",  str(max_retries),  "simulation retry count"),
    ]
    for name, val, desc in params:
        lines.append(f"  {name:<14} {val:<14} {desc}")
    lines.append(f"\n  output_dir: {output_dir or 'not saved'}")
    lines.append("\nKey differences vs. BO:")
    lines.append("  - Failed Aspen runs do NOT pollute the objective GP")
    lines.append("  - Separate feasibility GP models P(feasible | x)")
    lines.append("  - Safe to explore near failure boundaries without being trapped")
    lines.append("\nTo start, call optimize again with dry_run=False.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_cbo(
    manager,
    session_name: str,
    variables: list[dict] | None = None,
    objectives: list[dict] | None = None,
    constraints: list[dict] | None = None,
    n_initial: int = 10,
    n_iterations: int = 40,
    q: int = 1,
    seed: int | None = None,
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str | None = None,
    ctx: "Context | None" = None,
    resume_from: str | None = None,
) -> str:
    """Entry point for ``optimize(algorithm='cbo')``."""
    # Resume can point at a prior run folder / evaluations.csv; reload the exact
    # problem from its config.json when variables/objectives aren't re-supplied.
    resume_csv = resume_from
    if resume_from:
        resume_csv, cfg = resolve_resume(resume_from)
        if cfg:
            if not variables:
                variables = cfg.get("variables")
            if not objectives:
                objectives = cfg.get("objectives")
            if constraints is None:
                constraints = cfg.get("constraints") or None
    if not variables:
        return ("Error: at least one decision variable is required "
                "(or pass resume_from pointing to a run folder with config.json).")
    if not objectives:
        return ("Error: at least one objective is required "
                "(or pass resume_from pointing to a run folder with config.json).")
    if n_initial < 2:
        return "Error: n_initial must be >= 2 (GP needs at least 2 points)."

    if dry_run:
        preview = _format_preview(
            session_name, variables, objectives, constraints,
            n_initial, n_iterations, q, seed, max_retries, output_dir,
        )
        if resume_from:
            preview += resume_preview(resume_csv, variables, objectives,
                                      n_initial, n_iterations,
                                      q if len(objectives) >= 2 else 1)
        return preview

    resume_records: list[dict] | None = None
    if resume_from:
        try:
            resume_records = load_resume_records(resume_csv, variables, objectives)
            logger.info("cBO: loaded %d resume records from %s",
                        len(resume_records), resume_csv)
        except (FileNotFoundError, ValueError) as e:
            return f"Error loading resume CSV: {e}"

    result = await _run_cbo_core(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        n_initial=n_initial, n_iterations=n_iterations,
        q=q, seed=seed, max_retries=max_retries,
        output_dir=output_dir, ctx=ctx,
        resume_records=resume_records,
    )
    return result["report"]


async def _run_cbo_core(
    *,
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    n_initial: int,
    n_iterations: int,
    q: int,
    seed: int | None,
    max_retries: int,
    output_dir: str | None,
    ctx: "Context | None",
    reporter: ProgressReporter | None = None,
    initial_seeds: list[list[float]] | None = None,
    resume_records: list[dict] | None = None,
) -> dict:
    err = validate_session(manager, session_name)
    if err is not None:
        return err

    M = len(objectives)
    weights = tuple(1.0 if o.get("direction", "minimize").lower() == "maximize" else -1.0
                    for o in objectives)
    obj_labels = [obj_label(o) for o in objectives]

    total_evals = n_initial + n_iterations * (q if M >= 2 else 1)
    owns_reporter = reporter is None
    algo_name = "cBO (cEI)" if M == 1 else f"cBO (qLogNEHVI, M={M})"
    if reporter is None:
        reporter = ProgressReporter(
            algorithm=algo_name, total_evals=total_evals, n_iterations=n_iterations,
            obj_names=obj_labels, iteration_label="Iteration", mcp_ctx=ctx,
        )
    else:
        reporter.set_algorithm(algo_name, iteration_label="Iteration")

    if not _BOTORCH_AVAILABLE:
        if owns_reporter:
            reporter.abort("BoTorch/torch missing")
        return error_result(
            f"Constrained BO requires BoTorch. "
            f"pip install 'botorch>=0.10' (pulls in torch ~2GB)\n{_BOTORCH_IMPORT_ERROR}"
        )

    if M == 1:
        return await _run_cbo_single(
            manager=manager, session_name=session_name,
            variables=variables, objectives=objectives, constraints=constraints,
            n_initial=n_initial, n_iterations=n_iterations,
            seed=seed, max_retries=max_retries,
            output_dir=output_dir, ctx=ctx,
            reporter=reporter, owns_reporter=owns_reporter,
            weights=weights, obj_labels=obj_labels,
            initial_seeds=initial_seeds,
            resume_records=resume_records,
        )
    return await _run_cbo_multi(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        n_initial=n_initial, n_iterations=n_iterations, q=q,
        seed=seed, max_retries=max_retries,
        output_dir=output_dir, ctx=ctx,
        reporter=reporter, owns_reporter=owns_reporter,
        weights=weights, obj_labels=obj_labels,
        initial_seeds=initial_seeds,
        resume_records=resume_records,
    )


# ---------------------------------------------------------------------------
# Shared GP construction
# ---------------------------------------------------------------------------

def _build_obj_models(X_feas, Y_feas, bounds, M: int):
    """Fit M independent SingleTaskGPs on feasible points only, return ModelListGP."""
    SingleTaskGP = _SingleTaskGP
    ModelListGP = _ModelListGP
    Normalize = _BoTNormalize
    Standardize = _BoTStandardize
    SumMLL = _SumMLL

    models = [
        SingleTaskGP(
            X_feas, Y_feas[:, k : k + 1],
            input_transform=Normalize(d=X_feas.shape[-1], bounds=bounds),
            outcome_transform=Standardize(m=1),
        ) for k in range(M)
    ]
    model = ModelListGP(*models)
    mll = SumMLL(model.likelihood, model)
    _fit_gpytorch_mll(mll)
    return model


def _build_feas_gp(X_all, feas_labels, bounds):
    """Fit SingleTaskGP on {0, 1} feasibility labels over ALL points."""
    SingleTaskGP = _SingleTaskGP
    Normalize = _BoTNormalize
    Standardize = _BoTStandardize
    ExactMLL = _ExactMLL

    model = SingleTaskGP(
        X_all, feas_labels,
        input_transform=Normalize(d=X_all.shape[-1], bounds=bounds),
        outcome_transform=Standardize(m=1),
    )
    mll = ExactMLL(model.likelihood, model)
    _fit_gpytorch_mll(mll)
    return model


# ---------------------------------------------------------------------------
# Single-objective: BoTorch ConstrainedExpectedImprovement
# ---------------------------------------------------------------------------

async def _run_cbo_single(
    *, manager, session_name, variables, objectives, constraints,
    n_initial, n_iterations, seed, max_retries,
    output_dir, ctx, reporter, owns_reporter,
    weights, obj_labels, initial_seeds,
    resume_records=None,
) -> dict:
    np = _np
    torch = _torch
    SingleTaskGP = _SingleTaskGP
    ModelListGP = _ModelListGP
    LogConstrainedEI = _LogConstrainedEI
    optimize_acqf = cancellable(_optimize_acqf)

    w = weights[0]
    obj = objectives[0]
    obj_dir = obj.get("direction", "minimize")[:3]
    var_names = unique_names([v["aspen_path"] for v in variables])

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

    dtype = torch.double
    device = torch.device("cpu")
    lows = torch.tensor([v["lower"] for v in variables], dtype=dtype, device=device)
    highs = torch.tensor([v["upper"] for v in variables], dtype=dtype, device=device)
    bounds = torch.stack([lows, highs])

    debug_log: list[str] = []
    stats = EvalStats()
    eval_log: list[tuple] = []
    aborted = False
    _ckpt_dir: list[str] = []

    X_all: list[list[float]] = []        # every evaluated x (success + failure)
    feas_labels: list[float] = []        # 1.0 if feasible, 0.0 if not
    X_feas: list[list[float]] = []       # only feasible x
    Y_feas_max: list[float] = []         # sign-flipped feasible y (for maximize-internal)

    def _record(x_decoded, f_vals, feasible):
        X_all.append(list(x_decoded))
        feas_labels.append(1.0 if feasible else 0.0)
        if feasible:
            X_feas.append(list(x_decoded))
            Y_feas_max.append(w * f_vals[0])

    start = time.time()

    # ---- Replay resumed records (skip Aspen, populate history only) -----
    if resume_records:
        for rec in resume_records:
            x = rec["x"]; f_vals = rec["f_vals"]; feas = rec["feasible"]
            eval_log.append((0, list(x), list(f_vals), feas, rec["t_s"],
                             rec["reason"], rec["detail"]))
            _record(x, f_vals, feas)
            stats.record(rec["reason"] or ("ok" if feas else "not_converged"))
        n_initial_remaining = max(0, n_initial - len(resume_records))
        logger.info("cBO single: replayed %d records, %d LHS init remain",
                    len(resume_records), n_initial_remaining)
    else:
        n_initial_remaining = n_initial

    n_resumed = len(resume_records) if resume_records else 0
    total_expected = n_resumed + n_initial_remaining + n_iterations
    # Realign the progress window with the true target after resume.
    reporter.set_totals(total_evals=total_expected)

    # Resumed runs keep cumulative wall-clock so CSV time_s does not restart at 0
    # (``start`` still measures THIS run's wall-time only).
    time_offset = max((rec["t_s"] for rec in resume_records), default=0.0) \
        if resume_records else 0.0

    # ---- Initial samples ------------------------------------------------
    if initial_seeds:
        init_pts = [list(s) for s in initial_seeds[:n_initial_remaining]]
        if len(init_pts) < n_initial_remaining:
            init_pts += lhs_sample(n_initial_remaining - len(init_pts), variables)
    else:
        init_pts = lhs_sample(n_initial_remaining, variables) if n_initial_remaining else []

    try:
        for i, x in enumerate(init_pts):
            if reporter.poll_cancel():
                aborted = True
                break
            try:
                f_vals, feasible, _ = evaluate_x(
                    list(x), manager=manager, session_name=session_name,
                    variables=variables, objectives=objectives,
                    constraints=constraints, weights=weights,
                    max_retries=max_retries, debug_log=debug_log, stats=stats,
                    info=(_info := {}),
                )
            except OptimizationAborted as exc:
                aborted = True
                logger.warning("cBO aborted during init: %s", exc)
                break
            decoded = decode_x(list(x), variables)
            eval_log.append((0, decoded, list(f_vals), feasible, time.time() - start + time_offset,
                             _info.get("reason", ""), _info.get("detail", "")))
            _record(decoded, f_vals, feasible)

            if stats.total % CHECKPOINT_INTERVAL == 0:
                _checkpoint(output_dir, session_name, variables, objectives,
                            eval_log, stats, _ckpt_dir)

            best_f_raw = max(Y_feas_max) if Y_feas_max else None
            best_display = w * best_f_raw if best_f_raw is not None else None
            reporter.update_sync(
                0, stats.total, f"Initial LHS {stats.total}/{total_expected}",
                [best_display] if best_display is not None else None,
            )
            if ctx:
                try:
                    await ctx.report_progress(stats.total, total_expected)
                except Exception:
                    logger.debug("ctx.report_progress failed", exc_info=True)
            await asyncio.sleep(0)

        # ---- cBO loop --------------------------------------------------------
        for it in range(n_iterations):
            if aborted or reporter.poll_cancel():
                aborted = True
                break

            # Need at least 2 feasible points for the objective GP
            if len(X_feas) < 2:
                x_next = lhs_sample(1, variables)[0]
                logger.info("cBO iter %d: only %d feasible points, falling back to LHS",
                            it + 1, len(X_feas))
            else:
                try:
                    X_all_t = torch.tensor(X_all, dtype=dtype, device=device)
                    X_feas_t = torch.tensor(X_feas, dtype=dtype, device=device)
                    Y_feas_t = torch.tensor(Y_feas_max, dtype=dtype, device=device).unsqueeze(-1)
                    feas_t = torch.tensor(feas_labels, dtype=dtype, device=device).unsqueeze(-1)

                    obj_list = _build_obj_models(X_feas_t, Y_feas_t, bounds, M=1)
                    obj_gp = obj_list.models[0]

                    feas_gp = _build_feas_gp(X_all_t, feas_t, bounds)

                    combined = ModelListGP(obj_gp, feas_gp)

                    best_feas_y = Y_feas_t.max().item()
                    acqf = LogConstrainedEI(
                        model=combined,
                        best_f=best_feas_y,
                        objective_index=0,
                        constraints={1: (0.5, None)},
                        maximize=True,
                    )

                    candidates, _ = optimize_acqf(
                        acq_function=acqf,
                        bounds=bounds,
                        q=1,
                        num_restarts=10,
                        raw_samples=128,
                        options={"maxiter": ACQF_MAXITER},
                    )
                    x_next = candidates[0].detach().cpu().numpy().tolist()
                    # Release GP / acquisition tensors each iter to curb memory growth.
                    del acqf, combined, obj_list, obj_gp, feas_gp, candidates
                    del X_all_t, X_feas_t, Y_feas_t, feas_t
                except OptimizationCancelled:
                    raise
                except Exception as exc:
                    logger.warning("cBO single-obj acquisition failed at iter %d: %s", it + 1, exc)
                    x_next = lhs_sample(1, variables)[0]

            try:
                f_vals, feasible, _ = evaluate_x(
                    list(x_next), manager=manager, session_name=session_name,
                    variables=variables, objectives=objectives,
                    constraints=constraints, weights=weights,
                    max_retries=max_retries, debug_log=debug_log, stats=stats,
                    info=(_info := {}),
                )
            except OptimizationAborted as exc:
                aborted = True
                logger.warning("cBO aborted: %s", exc)
                break

            decoded = decode_x(list(x_next), variables)
            eval_log.append((it + 1, decoded, list(f_vals), feasible, time.time() - start + time_offset,
                             _info.get("reason", ""), _info.get("detail", "")))
            _record(decoded, f_vals, feasible)

            if stats.total % CHECKPOINT_INTERVAL == 0:
                _checkpoint(output_dir, session_name, variables, objectives,
                            eval_log, stats, _ckpt_dir)

            best_f_raw = max(Y_feas_max) if Y_feas_max else None
            best_display = w * best_f_raw if best_f_raw is not None else None
            reporter.update_sync(
                it + 1, stats.total, f"cBO iter {stats.total}/{total_expected}",
                [best_display] if best_display is not None else None,
            )
            if ctx:
                try:
                    await ctx.report_progress(stats.total, total_expected)
                except Exception:
                    logger.debug("ctx.report_progress failed", exc_info=True)
            await asyncio.sleep(0)
            gc.collect()
    except OptimizationCancelled:
        aborted = True
        logger.info("cBO (cEI) cancelled by user")

    wall_time = time.time() - start
    if owns_reporter:
        reporter.finalize(aborted)

    # Build Pareto (single point = best feasible)
    pareto: list[dict] = []
    best_obj_val: float | None = None
    best_x: list[float] | None = None
    if Y_feas_max:
        best_i = max(range(len(Y_feas_max)), key=lambda i: Y_feas_max[i])
        best_obj_val = w * Y_feas_max[best_i]
        best_x = X_feas[best_i]
        pareto = [{"x": best_x, "f": [best_obj_val]}]

    header = "ABORTED" if aborted else "cBO (cEI) complete"
    lines = [f"{header}: {stats.total} evaluations (n_initial={n_initial}, "
             f"n_iterations={n_iterations}), wall-time {wall_time:.1f}s"]
    lines.append(f"Objective GP trained on {len(X_feas)} feasible points")
    lines.append(f"Feasibility GP trained on {len(X_all)} total points "
                 f"({len(X_feas)} feasible, {len(X_all) - len(X_feas)} infeasible)")
    if best_x is not None:
        xs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, best_x))
        lines.append(f"\nBest: {xs} -> {obj_labels[0]}={best_obj_val:.6g} ({obj_dir})")
    else:
        lines.append("\nNo feasible solution found.")

    lines.append("")
    lines.append(stats.format_report())

    if debug_log:
        unique_msgs = list(dict.fromkeys(debug_log[:20]))
        lines.append(f"\nFailure details ({len(debug_log)}):")
        lines += [f"  {m}" for m in unique_msgs]

    log_lines = [f"cBO (cEI): {stats.total} evals, feasibility GP + cEI"]

    if output_dir:
        try:
            settings = {
                "Algorithm": "cBO (cEI, BoTorch)",
                "n_initial": n_initial,
                "n_iterations": n_iterations,
                "Seed": seed if seed is not None else "random",
                "Max retries": max_retries,
                "Obj GP points": len(X_feas),
                "Feas GP points": len(X_all),
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm="cBO-cEI", session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings, pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save cBO results: %s", e, exc_info=True)
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


# ---------------------------------------------------------------------------
# Multi-objective: BoTorch qLogNEHVI with feasibility constraint
# ---------------------------------------------------------------------------

async def _run_cbo_multi(
    *, manager, session_name, variables, objectives, constraints,
    n_initial, n_iterations, q, seed, max_retries,
    output_dir, ctx, reporter, owns_reporter,
    weights, obj_labels, initial_seeds,
    resume_records=None,
) -> dict:
    np = _np
    torch = _torch
    ModelListGP = _ModelListGP
    qLogNEHVI = _qLogNEHVI
    IdentityMCMO = _IdentityMCMO
    optimize_acqf = cancellable(_optimize_acqf)
    SobolQMCNormalSampler = _SobolQMCNormalSampler
    is_non_dominated = _is_non_dominated

    M = len(objectives)
    var_names = unique_names([v["aspen_path"] for v in variables])
    obj_dirs = [o.get("direction", "minimize")[:3] for o in objectives]

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

    dtype = torch.double
    device = torch.device("cpu")
    lows = torch.tensor([v["lower"] for v in variables], dtype=dtype, device=device)
    highs = torch.tensor([v["upper"] for v in variables], dtype=dtype, device=device)
    bounds = torch.stack([lows, highs])

    debug_log: list[str] = []
    stats = EvalStats()
    eval_log: list[tuple] = []
    aborted = False
    _ckpt_dir: list[str] = []

    X_all: list[list[float]] = []
    feas_labels: list[float] = []
    X_feas: list[list[float]] = []
    Y_feas_max: list[list[float]] = []   # sign-flipped (max-internal)
    time_offset: float = 0.0             # set when resuming, keeps CSV time_s cumulative

    def _record(x_decoded, f_vals, feasible):
        X_all.append(list(x_decoded))
        feas_labels.append(1.0 if feasible else 0.0)
        if feasible:
            X_feas.append(list(x_decoded))
            Y_feas_max.append([w * f for f, w in zip(f_vals, weights)])

    def _best_f_display():
        if not Y_feas_max:
            return None
        best = list(Y_feas_max[0])
        for row in Y_feas_max[1:]:
            for i, v in enumerate(row):
                if v > best[i]:
                    best[i] = v
        # back to raw sign
        return [w * v for w, v in zip(weights, best)]

    def _evaluate(x, it_num):
        nonlocal aborted
        if aborted or reporter.poll_cancel():
            aborted = True
            return
        try:
            f_vals, feasible, _ = evaluate_x(
                x, manager=manager, session_name=session_name,
                variables=variables, objectives=objectives,
                constraints=constraints, weights=weights,
                max_retries=max_retries, debug_log=debug_log, stats=stats,
                info=(_info := {}),
            )
        except OptimizationAborted as exc:
            aborted = True
            logger.warning("cBO aborted: %s", exc)
            return
        decoded = decode_x(x, variables)
        eval_log.append((it_num, decoded, list(f_vals), feasible, time.time() - start + time_offset,
                         _info.get("reason", ""), _info.get("detail", "")))
        _record(decoded, f_vals, feasible)

        if stats.total % CHECKPOINT_INTERVAL == 0:
            _checkpoint(output_dir, session_name, variables, objectives,
                        eval_log, stats, _ckpt_dir)

    start = time.time()

    # ---- Replay resumed records (skip Aspen, populate history only) -----
    if resume_records:
        for rec in resume_records:
            x = rec["x"]; f_vals = rec["f_vals"]; feas = rec["feasible"]
            eval_log.append((0, list(x), list(f_vals), feas, rec["t_s"],
                             rec["reason"], rec["detail"]))
            _record(x, f_vals, feas)
            stats.record(rec["reason"] or ("ok" if feas else "not_converged"))
        n_initial_remaining = max(0, n_initial - len(resume_records))
        logger.info("cBO multi: replayed %d records, %d LHS init remain",
                    len(resume_records), n_initial_remaining)
        # Continue cumulative wall-clock from the resumed run (CSV time_s no reset).
        time_offset = max((rec["t_s"] for rec in resume_records), default=0.0)
    else:
        n_initial_remaining = n_initial

    n_resumed = len(resume_records) if resume_records else 0
    total_expected = n_resumed + n_initial_remaining + n_iterations * q
    # Realign the progress window with the true target after resume — without
    # this the bar was sized for new evals only (e.g. 1/400 instead of 601/1000).
    reporter.set_totals(total_evals=total_expected)

    # ---- Initial samples ------------------------------------------------
    if initial_seeds:
        init_pts = [list(s) for s in initial_seeds[:n_initial_remaining]]
        if len(init_pts) < n_initial_remaining:
            init_pts += lhs_sample(n_initial_remaining - len(init_pts), variables)
    else:
        init_pts = lhs_sample(n_initial_remaining, variables) if n_initial_remaining else []

    try:
        for i, x in enumerate(init_pts):
            _evaluate(list(x), 0)
            reporter.update_sync(
                0, stats.total, f"Initial LHS {stats.total}/{total_expected}", _best_f_display(),
            )
            if ctx:
                try:
                    await ctx.report_progress(stats.total, total_expected)
                except Exception:
                    logger.debug("ctx.report_progress failed", exc_info=True)
            await asyncio.sleep(0)
            if aborted:
                break

        # ---- cBO loop --------------------------------------------------------
        for it in range(n_iterations):
            if aborted or reporter.poll_cancel():
                aborted = True
                break

            if len(X_feas) < 2:
                # Fall back to LHS when not enough feasible points to fit obj GP
                candidates_np = np.array(lhs_sample(q, variables))
                logger.info("cBO iter %d: only %d feasible points, falling back to LHS",
                            it + 1, len(X_feas))
            else:
                try:
                    X_all_t = torch.tensor(X_all, dtype=dtype, device=device)
                    X_feas_t = torch.tensor(X_feas, dtype=dtype, device=device)
                    Y_feas_t = torch.tensor(Y_feas_max, dtype=dtype, device=device)
                    feas_t = torch.tensor(feas_labels, dtype=dtype, device=device).unsqueeze(-1)

                    obj_model = _build_obj_models(X_feas_t, Y_feas_t, bounds, M=M)

                    feas_gp = _build_feas_gp(X_all_t, feas_t, bounds)

                    combined = ModelListGP(*obj_model.models, feas_gp)
                    Y_min = Y_feas_t.min(dim=0).values
                    Y_max = Y_feas_t.max(dim=0).values
                    Y_ref = Y_min - 0.1 * (Y_max - Y_min)
                    mo_objective = IdentityMCMO(outcomes=list(range(M)))

                    def feasibility_constraint(Z):
                        return 0.5 - Z[..., -1]

                    # Shrink X_baseline to the feasible non-dominated set so
                    # qLogNEHVI does not score hypervolume over hundreds of
                    # dominated / failed points each acquisition call.
                    nd_mask = _is_non_dominated(Y_feas_t)
                    X_baseline_t = X_feas_t[nd_mask]
                    if X_baseline_t.shape[0] < 2:
                        X_baseline_t = X_feas_t  # fall back if Pareto too small

                    sampler = SobolQMCNormalSampler(sample_shape=torch.Size([128]))
                    acqf = qLogNEHVI(
                        model=combined,
                        ref_point=Y_ref,
                        X_baseline=X_baseline_t,
                        sampler=sampler,
                        objective=mo_objective,
                        constraints=[feasibility_constraint],
                        prune_baseline=True,
                    )

                    candidates, _ = optimize_acqf(
                        acq_function=acqf,
                        bounds=bounds,
                        q=q,
                        num_restarts=10,
                        raw_samples=128,
                        options={"maxiter": ACQF_MAXITER},
                    )

                    candidates_np = candidates.detach().cpu().numpy()
                    # Release GP / acquisition tensors each iter to curb memory growth.
                    del acqf, combined, obj_model, feas_gp, candidates, sampler
                    del X_all_t, X_feas_t, Y_feas_t, feas_t
                    del Y_min, Y_max, Y_ref, mo_objective
                    del nd_mask, X_baseline_t
                except OptimizationCancelled:
                    raise
                except Exception as exc:
                    logger.warning("cBO multi-obj acquisition failed at iter %d: %s", it + 1, exc)
                    candidates_np = np.array(lhs_sample(q, variables))

            for x_row in candidates_np:
                if aborted:
                    break
                _evaluate(x_row.tolist(), it + 1)
                reporter.update_sync(
                    it + 1, stats.total,
                    f"cBO {stats.total}/{total_expected} (q={q})",
                    _best_f_display(),
                )
                if ctx:
                    try:
                        await ctx.report_progress(stats.total, total_expected)
                    except Exception:
                        logger.debug("ctx.report_progress failed", exc_info=True)
                await asyncio.sleep(0)
            gc.collect()
    except OptimizationCancelled:
        aborted = True
        logger.info("cBO (qLogNEHVI) cancelled by user")

    wall_time = time.time() - start
    if owns_reporter:
        reporter.finalize(aborted)

    # ---- Extract Pareto front from feasible points ----------------------
    pareto: list[dict] = []
    if Y_feas_max:
        Y_t = torch.tensor(Y_feas_max, dtype=dtype, device=device)
        nd_mask = is_non_dominated(Y_t).cpu().numpy().tolist()
        for i, is_nd in enumerate(nd_mask):
            if is_nd:
                pareto.append({
                    "x": X_feas[i],
                    "f": [w * y for y, w in zip(Y_feas_max[i], weights)],
                })
        pareto.sort(key=lambda p: p["f"][0])

    fitness_matrix = [p["f"] for p in pareto]
    comp_idx = best_compromise(fitness_matrix, weights) if pareto else -1

    def _fmt_point(p):
        xs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, p["x"]))
        fs = ", ".join(f"{n}={v:.4g} ({dr})"
                       for n, v, dr in zip(obj_labels, p["f"], obj_dirs))
        return f"{xs} -> {fs}"

    header = "ABORTED" if aborted else "cBO (qLogNEHVI) complete"
    lines = [f"{header}: {stats.total} evals (n_initial={n_initial}, "
             f"n_iterations={n_iterations}, q={q}), wall-time {wall_time:.1f}s"]
    lines.append(f"Objective GPs trained on {len(X_feas)} feasible points")
    lines.append(f"Feasibility GP trained on {len(X_all)} total points "
                 f"({len(X_feas)} feasible, {len(X_all) - len(X_feas)} infeasible)")
    lines.append(f"\nPareto Front ({len(pareto)} solutions):")
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

    log_lines = [f"cBO (qLogNEHVI): {stats.total} evals, q={q}, feasibility GP + constrained HVI"]

    if output_dir:
        try:
            settings = {
                "Algorithm": "cBO (qLogNEHVI, BoTorch)",
                "n_initial": n_initial,
                "n_iterations": n_iterations,
                "Batch q": q,
                "Seed": seed if seed is not None else "random",
                "Max retries": max_retries,
                "Obj GP points": len(X_feas),
                "Feas GP points": len(X_all),
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm="cBO-qLogNEHVI", session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings, pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save cBO results: %s", e, exc_info=True)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

