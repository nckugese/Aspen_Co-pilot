"""Bayesian Optimization for Aspen Plus.

Single-objective problems use scikit-optimize's ``gp_minimize`` (EI/LCB).
Multi-objective problems use BoTorch's ``qLogNoisyExpectedHypervolumeImprovement``
with per-objective SingleTaskGP surrogates. Ideal for expensive Aspen runs
where sample efficiency matters most.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import random
import time
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
    load_resume_records,
    resolve_resume,
    resume_preview,
)

# Eager-import optional deps at module load so the FIRST BO call doesn't stall
# the event loop while scipy/numpy/sklearn/torch initialize. Missing packages
# are reported at call time via friendly error messages.
try:
    from skopt import Optimizer as _SkoptOptimizer  # noqa: F401
    from skopt.space import Integer as _SkoptInteger, Real as _SkoptReal  # noqa: F401
    _SKOPT_AVAILABLE = True
    _SKOPT_IMPORT_ERROR = None
except ImportError as _exc:
    _SKOPT_AVAILABLE = False
    _SKOPT_IMPORT_ERROR = str(_exc)

try:
    import numpy as _np  # noqa: F401
    # Imported before torch on purpose: _bo_threads sets OMP_NUM_THREADS at
    # module scope, and an OpenMP runtime reads that only once, when torch
    # loads it -- setting it afterwards is a no-op for the BLAS pools.
    from tools._bo_threads import cap_threads as _cap_threads
    import torch as _torch  # noqa: F401
    _cap_threads()
    from botorch.acquisition.multi_objective.logei import (  # noqa: F401
        qLogNoisyExpectedHypervolumeImprovement as _qLogNEHVI,
    )
    from botorch.fit import fit_gpytorch_mll as _fit_gpytorch_mll  # noqa: F401
    from botorch.models import SingleTaskGP as _SingleTaskGP  # noqa: F401
    from botorch.models import ModelListGP as _ModelListGP  # noqa: F401
    from botorch.models.transforms import Normalize as _BoTNormalize  # noqa: F401
    from botorch.models.transforms import Standardize as _BoTStandardize  # noqa: F401
    from botorch.optim import optimize_acqf as _optimize_acqf  # noqa: F401
    from botorch.sampling.normal import SobolQMCNormalSampler as _SobolQMCNormalSampler  # noqa: F401
    from botorch.utils.multi_objective.pareto import is_non_dominated as _is_non_dominated  # noqa: F401
    from gpytorch.mlls import SumMarginalLogLikelihood as _SumMarginalLogLikelihood  # noqa: F401
    _BOTORCH_AVAILABLE = True
    _BOTORCH_IMPORT_ERROR = None
except ImportError as _exc:
    _BOTORCH_AVAILABLE = False
    _BOTORCH_IMPORT_ERROR = str(_exc)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def _format_preview(
    session_name, variables, objectives, constraints,
    n_initial, n_iterations, acquisition, q,
    seed, max_retries, output_dir,
) -> str:
    var_names = unique_names([v["aspen_path"] for v in variables])
    M = len(objectives)
    backend = "scikit-optimize (single-obj)" if M == 1 else f"BoTorch qLogNEHVI ({M} objectives)"
    total_evals = n_initial + n_iterations * (q if M >= 2 else 1)

    lines = [
        f"=== BO ({backend}) Settings Preview ===",
        f"\nSession: {session_name}",
        f"Estimated evaluations: {total_evals} ({n_initial} initial + {n_iterations} BO iters)",
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
        ("n_initial",     str(n_initial),     "LHS initial samples before BO starts"),
        ("n_iterations",  str(n_iterations),  "BO iterations after initial"),
        ("acquisition",   acquisition,
         "single-obj: EI / LCB / auto; multi-obj: qLogNEHVI only"),
        ("q",             str(q),             "batch size (multi-obj only)"),
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

async def run_bo(
    manager,
    session_name: str,
    variables: list[dict] | None = None,
    objectives: list[dict] | None = None,
    constraints: list[dict] | None = None,
    n_initial: int = 10,
    n_iterations: int = 40,
    acquisition: str = "auto",
    q: int = 1,
    seed: int | None = None,
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str | None = None,
    ctx: "Context | None" = None,
    resume_from: str | None = None,
) -> str:
    """Entry point for ``optimize(algorithm='bo')``."""
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
            n_initial, n_iterations, acquisition, q,
            seed, max_retries, output_dir,
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
            logger.info("BO: loaded %d resume records from %s",
                        len(resume_records), resume_csv)
        except (FileNotFoundError, ValueError) as e:
            return f"Error loading resume CSV: {e}"

    result = await _run_bo_core(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        n_initial=n_initial, n_iterations=n_iterations,
        acquisition=acquisition, q=q, seed=seed,
        max_retries=max_retries, output_dir=output_dir, ctx=ctx,
        resume_records=resume_records,
    )
    return result["report"]


async def _run_bo_core(
    *,
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    n_initial: int,
    n_iterations: int,
    acquisition: str,
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
    algo_name = "BO (skopt)" if M == 1 else f"BO (qLogNEHVI, M={M})"
    if reporter is None:
        reporter = ProgressReporter(
            algorithm=algo_name, total_evals=total_evals, n_iterations=n_iterations,
            obj_names=obj_labels, iteration_label="Iteration", mcp_ctx=ctx,
        )
    else:
        reporter.set_algorithm(algo_name, iteration_label="Iteration")

    if M == 1:
        return await _run_skopt(
            manager=manager, session_name=session_name,
            variables=variables, objectives=objectives, constraints=constraints,
            n_initial=n_initial, n_iterations=n_iterations,
            acquisition=acquisition, seed=seed,
            max_retries=max_retries, output_dir=output_dir, ctx=ctx,
            reporter=reporter, owns_reporter=owns_reporter,
            weights=weights, obj_labels=obj_labels,
            initial_seeds=initial_seeds,
            resume_records=resume_records,
        )
    return await _run_botorch(
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
# Single-objective: scikit-optimize
# ---------------------------------------------------------------------------

async def _run_skopt(
    *, manager, session_name, variables, objectives, constraints,
    n_initial, n_iterations, acquisition, seed, max_retries,
    output_dir, ctx, reporter, owns_reporter,
    weights, obj_labels, initial_seeds,
    resume_records=None,
) -> dict:
    if not _SKOPT_AVAILABLE:
        if owns_reporter:
            reporter.abort("skopt missing")
        return error_result(
            f"Single-objective BO requires scikit-optimize. "
            f"pip install 'scikit-optimize>=0.10'\n{_SKOPT_IMPORT_ERROR}"
        )
    Optimizer, Integer, Real = _SkoptOptimizer, _SkoptInteger, _SkoptReal

    w = weights[0]
    obj = objectives[0]
    obj_dir = obj.get("direction", "minimize")[:3]
    var_names = unique_names([v["aspen_path"] for v in variables])

    acq = acquisition.upper() if acquisition != "auto" else "EI"
    if acq not in ("EI", "LCB", "PI"):
        acq = "EI"

    space = []
    for v in variables:
        if v.get("type") == "int":
            space.append(Integer(int(v["lower"]), int(v["upper"])))
        else:
            space.append(Real(float(v["lower"]), float(v["upper"])))

    if seed is not None:
        random.seed(seed)
    opt = Optimizer(
        dimensions=space,
        base_estimator="GP",
        acq_func=acq,
        n_initial_points=n_initial,
        initial_point_generator="lhs",
        random_state=seed,
    )

    debug_log: list[str] = []
    stats = EvalStats()
    eval_log: list[tuple] = []
    best_obj_val: float | None = None
    aborted = False

    start = time.time()
    n_resumed = 0

    # ---- Replay resumed records (skip Aspen, feed skopt directly) -------
    if resume_records:
        try:
            for rec in resume_records:
                x = rec["x"]; f_vals = rec["f_vals"]; feas = rec["feasible"]
                eval_log.append((0, list(x), list(f_vals), feas, rec["t_s"],
                                 rec["reason"], rec["detail"]))
                opt.tell(x, -w * f_vals[0])
                stats.record(rec["reason"] or ("ok" if feas else "not_converged"))
                if feas and (best_obj_val is None
                             or (w > 0 and f_vals[0] > best_obj_val)
                             or (w < 0 and f_vals[0] < best_obj_val)):
                    best_obj_val = f_vals[0]
            n_resumed = len(resume_records)
            logger.info("BO skopt: replayed %d resume records", n_resumed)
        except Exception as exc:
            logger.warning("Resume replay failed: %s", exc)
    # Resumed records count toward n_initial only (skopt's tell() does the same);
    # n_iterations are always new, matching _run_botorch and the dispatcher's split.
    total = max(0, n_initial - n_resumed) + n_iterations   # loop count
    total_target = n_resumed + total                         # progress bar denominator
    # Realign the progress window after resume so the bar shows the true target
    # (e.g. 601/1000) instead of the new-evals-only count.
    reporter.set_totals(total_evals=total_target)

    # Resumed runs keep cumulative wall-clock so CSV time_s does not restart at 0.
    time_offset = max((rec["t_s"] for rec in resume_records), default=0.0) \
        if resume_records else 0.0

    # Seed with initial_seeds if provided
    try:
        if initial_seeds:
            for s in initial_seeds[:n_initial]:
                try:
                    f_vals, feasible, _ = evaluate_x(
                        list(s), manager=manager, session_name=session_name,
                        variables=variables, objectives=objectives,
                        constraints=constraints, weights=weights,
                        max_retries=max_retries, debug_log=debug_log, stats=stats,
                        info=(_info := {}),
                    )
                except OptimizationAborted as exc:
                    aborted = True
                    logger.warning("skopt aborted: %s", exc)
                    break
                decoded = decode_x(list(s), variables)
                eval_log.append((0, decoded, list(f_vals), feasible, time.time() - start + time_offset,
                                 _info.get("reason", ""), _info.get("detail", "")))
                opt.tell(decoded, -w * f_vals[0])
                if feasible and (best_obj_val is None
                                 or (w > 0 and f_vals[0] > best_obj_val)
                                 or (w < 0 and f_vals[0] < best_obj_val)):
                    best_obj_val = f_vals[0]
                reporter.update_sync(
                    0, stats.total, f"Seed {stats.total}/{len(initial_seeds[:n_initial])}",
                    [best_obj_val] if best_obj_val is not None else None,
                )
                if ctx:
                    try:
                        await ctx.report_progress(stats.total, total_target)
                    except Exception:
                        logger.debug("ctx.report_progress failed", exc_info=True)
                await asyncio.sleep(0)

        for it in range(total):
            if aborted or reporter.poll_cancel():
                aborted = True
                break
            x = opt.ask()
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
                logger.warning("skopt aborted: %s", exc)
                break

            decoded = decode_x(list(x), variables)
            eval_log.append((it + 1, decoded, list(f_vals), feasible, time.time() - start + time_offset,
                             _info.get("reason", ""), _info.get("detail", "")))
            opt.tell(decoded, -w * f_vals[0])

            if feasible and (best_obj_val is None
                             or (w > 0 and f_vals[0] > best_obj_val)
                             or (w < 0 and f_vals[0] < best_obj_val)):
                best_obj_val = f_vals[0]

            phase = "Initial" if (n_resumed + it + 1) <= n_initial else "BO"
            reporter.update_sync(
                it + 1, stats.total,
                f"{phase} {stats.total}/{total_target}",
                [best_obj_val] if best_obj_val is not None else None,
            )
            if ctx:
                try:
                    await ctx.report_progress(stats.total, total_target)
                except Exception:
                    logger.debug("ctx.report_progress failed", exc_info=True)
            await asyncio.sleep(0)
    except OptimizationCancelled:
        aborted = True
        logger.info("BO (skopt) cancelled by user")

    wall_time = time.time() - start
    if owns_reporter:
        reporter.finalize(aborted)

    # Build Pareto (single point = best feasible)
    pareto: list[dict] = []
    best_x: list[float] | None = None
    if eval_log:
        feasible_entries = [e for e in eval_log if e[3] and is_feasible_values(e[2])]
        if feasible_entries:
            key = (lambda e: -e[2][0]) if w > 0 else (lambda e: e[2][0])
            best_entry = min(feasible_entries, key=key)
            best_x = best_entry[1]
            pareto = [{"x": best_x, "f": best_entry[2]}]

    obj_dirs = [obj_dir]
    header = "ABORTED" if aborted else "BO (skopt) complete"
    lines = [f"{header}: {stats.total} evaluations (n_initial={n_initial}, "
             f"n_iterations={n_iterations}), wall-time {wall_time:.1f}s"]
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

    log_lines = [f"skopt: {total} evals, acq={acq}"]

    if output_dir:
        try:
            settings = {
                "Algorithm": "BO (skopt)",
                "n_initial": n_initial,
                "n_iterations": n_iterations,
                "Acquisition": acq,
                "Seed": seed if seed is not None else "random",
                "Max retries": max_retries,
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm="BO-skopt", session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings, pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save BO results: %s", e, exc_info=True)
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
# Multi-objective: BoTorch qLogNEHVI
# ---------------------------------------------------------------------------

async def _run_botorch(
    *, manager, session_name, variables, objectives, constraints,
    n_initial, n_iterations, q, seed, max_retries,
    output_dir, ctx, reporter, owns_reporter,
    weights, obj_labels, initial_seeds,
    resume_records=None,
) -> dict:
    if not _BOTORCH_AVAILABLE:
        if owns_reporter:
            reporter.abort("BoTorch/torch missing")
        return error_result(
            f"Multi-objective BO requires BoTorch. "
            f"pip install 'botorch>=0.10' (this pulls in torch ~2GB)\n{_BOTORCH_IMPORT_ERROR}"
        )
    np = _np
    torch = _torch
    qLogNoisyExpectedHypervolumeImprovement = _qLogNEHVI
    fit_gpytorch_mll = _fit_gpytorch_mll
    SingleTaskGP = _SingleTaskGP
    ModelListGP = _ModelListGP
    Normalize = _BoTNormalize
    Standardize = _BoTStandardize
    optimize_acqf = cancellable(_optimize_acqf)
    SobolQMCNormalSampler = _SobolQMCNormalSampler
    is_non_dominated = _is_non_dominated
    SumMarginalLogLikelihood = _SumMarginalLogLikelihood

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

    X_train: list[list[float]] = []
    Y_train: list[list[float]] = []  # sign-flipped so qLogNEHVI maximizes all
    time_offset: float = 0.0         # set when resuming, keeps CSV time_s cumulative

    def _evaluate(x: list[float], it_num: int) -> bool:
        nonlocal aborted
        if aborted or reporter.poll_cancel():
            aborted = True
            return False
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
            logger.warning("BoTorch aborted: %s", exc)
            return False
        decoded = decode_x(x, variables)
        eval_log.append((it_num, decoded, list(f_vals), feasible, time.time() - start + time_offset,
                         _info.get("reason", ""), _info.get("detail", "")))
        # qLogNEHVI maximizes — flip objectives so everything is "higher is better"
        y_max = [w * f for f, w in zip(f_vals, weights)]
        X_train.append(decoded)
        Y_train.append(y_max)
        return feasible

    start = time.time()

    # ---- Replay resumed records (skip Aspen, populate X_train/Y_train) --
    if resume_records:
        for rec in resume_records:
            x = rec["x"]; f_vals = rec["f_vals"]; feas = rec["feasible"]
            eval_log.append((0, list(x), list(f_vals), feas, rec["t_s"],
                             rec["reason"], rec["detail"]))
            X_train.append(list(x))
            Y_train.append([w * f for f, w in zip(f_vals, weights)])
            stats.record(rec["reason"] or ("ok" if feas else "not_converged"))
        n_initial_remaining = max(0, n_initial - len(resume_records))
        logger.info("BO botorch: replayed %d records, %d LHS init remain",
                    len(resume_records), n_initial_remaining)
        # Continue cumulative wall-clock from the resumed run (CSV time_s no reset).
        time_offset = max((rec["t_s"] for rec in resume_records), default=0.0)
    else:
        n_initial_remaining = n_initial

    # ---- Initial samples ------------------------------------------------
    if initial_seeds:
        init_pts = [list(s) for s in initial_seeds[:n_initial_remaining]]
        if len(init_pts) < n_initial_remaining:
            init_pts += lhs_sample(n_initial_remaining - len(init_pts), variables)
    else:
        init_pts = lhs_sample(n_initial_remaining, variables) if n_initial_remaining else []

    n_resumed = len(resume_records) if resume_records else 0
    total_expected = n_resumed + n_initial_remaining + n_iterations * q
    # Realign the progress window with the true target after resume.
    reporter.set_totals(total_evals=total_expected)
    try:
        for i, x in enumerate(init_pts):
            _evaluate(list(x), 0)
            reporter.update_sync(
                0, stats.total, f"Initial LHS {stats.total}/{total_expected}", _best_f(Y_train, weights),
            )
            if ctx:
                try:
                    await ctx.report_progress(stats.total, total_expected)
                except Exception:
                    logger.debug("ctx.report_progress failed", exc_info=True)
            await asyncio.sleep(0)
            if aborted:
                break

        # ---- BO loop --------------------------------------------------------
        for it in range(n_iterations):
            if aborted or reporter.poll_cancel():
                aborted = True
                break
            X = torch.tensor(X_train, dtype=dtype, device=device)
            Y = torch.tensor(Y_train, dtype=dtype, device=device)

            try:
                models = [
                    SingleTaskGP(
                        X, Y[:, k : k + 1],
                        input_transform=Normalize(d=X.shape[-1], bounds=bounds),
                        outcome_transform=Standardize(m=1),
                    ) for k in range(M)
                ]
                model = ModelListGP(*models)
                mll = SumMarginalLogLikelihood(model.likelihood, model)
                fit_gpytorch_mll(mll)

                # Reference point from observed Y (penalty rows skipped to avoid
                # extreme refs that wreck hypervolume scaling)
                feas_mask_list = [is_feasible_values(row) for row in Y_train]
                feas_mask_t = torch.tensor(feas_mask_list, dtype=torch.bool, device=device)
                Y_feas = Y[feas_mask_t] if feas_mask_t.any() else Y
                Y_ref = (Y_feas.min(dim=0).values
                         - 0.1 * (Y_feas.max(dim=0).values - Y_feas.min(dim=0).values))

                # X_baseline = feasible non-dominated points only.
                # Penalty rows dominate nothing useful; including them blows up
                # qLogNEHVI cost on large n.
                X_feas = X[feas_mask_t] if feas_mask_t.any() else X
                if X_feas.shape[0] >= 2:
                    nd_mask = is_non_dominated(Y_feas)
                    X_baseline_t = X_feas[nd_mask]
                    if X_baseline_t.shape[0] < 2:
                        X_baseline_t = X_feas
                else:
                    X_baseline_t = X

                sampler = SobolQMCNormalSampler(sample_shape=torch.Size([128]))
                acqf = qLogNoisyExpectedHypervolumeImprovement(
                    model=model,
                    ref_point=Y_ref,
                    X_baseline=X_baseline_t,
                    sampler=sampler,
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
                del acqf, model, models, mll, sampler, candidates, X, Y, Y_ref
                del feas_mask_t, Y_feas, X_feas, X_baseline_t
            except OptimizationCancelled:
                raise
            except Exception as exc:
                logger.warning("BoTorch acquisition failed at iter %d: %s", it + 1, exc)
                candidates_np = np.array(lhs_sample(q, variables))

            for x_row in candidates_np:
                if aborted:
                    break
                _evaluate(x_row.tolist(), it + 1)
                reporter.update_sync(
                    it + 1, stats.total,
                    f"BO {stats.total}/{total_expected} (q={q})",
                    _best_f(Y_train, weights),
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
        logger.info("BO (qLogNEHVI) cancelled by user")

    wall_time = time.time() - start
    if owns_reporter:
        reporter.finalize(aborted)

    # ---- Extract Pareto front from observed points ----------------------
    pareto: list[dict] = []
    if Y_train:
        # Only consider points that aren't massive penalty values
        raw_f = [[w * y for y, w in zip(row, weights)] for row in Y_train]
        feasible_mask = [is_feasible_values(row) for row in raw_f]
        if any(feasible_mask):
            Y_feasible = torch.tensor(
                [row for row, ok in zip(Y_train, feasible_mask) if ok],
                dtype=dtype, device=device,
            )
            X_feasible = [x for x, ok in zip(X_train, feasible_mask) if ok]
            nd_mask = is_non_dominated(Y_feasible).cpu().numpy().tolist()
            for i, is_nd in enumerate(nd_mask):
                if is_nd:
                    pareto.append({
                        "x": X_feasible[i],
                        "f": [w * y for y, w in zip(Y_feasible[i].tolist(), weights)],
                    })
            pareto.sort(key=lambda p: p["f"][0])

    fitness_matrix = [p["f"] for p in pareto]
    comp_idx = best_compromise(fitness_matrix, weights) if pareto else -1

    def _fmt_point(p):
        xs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, p["x"]))
        fs = ", ".join(f"{n}={v:.4g} ({dr})"
                       for n, v, dr in zip(obj_labels, p["f"], obj_dirs))
        return f"{xs} -> {fs}"

    header = "ABORTED" if aborted else "BO (qLogNEHVI) complete"
    lines = [f"{header}: {stats.total} evals (n_initial={n_initial}, "
             f"n_iterations={n_iterations}, q={q}), wall-time {wall_time:.1f}s",
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

    log_lines = [f"BO (qLogNEHVI): {stats.total} evals, q={q}"]

    if output_dir:
        try:
            settings = {
                "Algorithm": "BO (qLogNEHVI, BoTorch)",
                "n_initial": n_initial,
                "n_iterations": n_iterations,
                "Batch q": q,
                "Seed": seed if seed is not None else "random",
                "Max retries": max_retries,
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm="BO-qLogNEHVI", session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings, pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save BO results: %s", e, exc_info=True)
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

def _best_f(Y_train: list[list[float]], weights: tuple[float, ...]) -> list[float] | None:
    """Return best-so-far raw objective values from the sign-flipped Y (max-internal)."""
    if not Y_train:
        return None
    # Y_train stores y_max = w * f, so recover f = w * y_max (since w in {-1, +1})
    raw = [[w * y for y, w in zip(row, weights)] for row in Y_train]
    feasible = [r for r in raw if is_feasible_values(r)]
    if not feasible:
        return None
    best = list(feasible[0])
    for row in feasible[1:]:
        for i, (w, v) in enumerate(zip(weights, row)):
            if (w > 0 and v > best[i]) or (w < 0 and v < best[i]):
                best[i] = v
    return best


