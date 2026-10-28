"""AFM-CBO -- Adaptive Failure-Mode Constrained Bayesian Optimization.

Algorithm key ``afmcbo`` of the ``optimize`` tool. Feasibility is a hybrid:
measurable declared constraints are (to be) handled by continuous regression GPs,
while opaque simulator crashes use the binary "backstop + sharpeners" roster below.

Separate optimizer from ``cbo_tools.py`` (the single lumped feasibility GP).
AFM-CBO differs from CBO in ONE
region: instead of one feasibility GP modelling binary ``P(feasible | x)``, it
trains ONE feasibility GP PER FAILURE MECHANISM and combines them into a single
JOINT-feasibility constraint (product of the per-mechanism P(avoid)) so that a
point is excluded unless P(all mechanisms avoided) >= 0.5.

Mechanisms are the multi-label tags produced by ``main_tools.classify_mechanisms``
from the per-eval ``reason``/``detail`` that ``evaluate_x`` already records
(e.g. ``block:R1:flash``, ``block:COL1:not_in_mass_balance``, ``constraint:PROPYL1``).

Adaptive roster = BACKSTOP + SHARPENERS (see ``_mechanism_labels``): an always-on
lumped ``backstop`` GP over ALL crashes (= CBO's boundary), plus one
``sharpener`` GP per mechanism that has >= ``max(min_count, 2*n_dims)`` crashes of
its OWN (the minority class, so every GP is well-fed). Rare crashes get no GP --
they ride the backstop, instead of being forced into one incoherent ``other`` GP.
A debounced concentration gate keeps ONLY the backstop (= CBO) when one
mechanism owns >= ``DOMINANCE_THRESHOLD`` of crashes, so a concentrated failure set
doesn't pay for decomposition (which would inject excess product uncertainty and
over-drive exploration).

Everything else (objective GPs on feasible points only, qLogNEHVI / cEI, Pareto,
resume from config.json/CSV, checkpointing, memory curbing,
ProgressReporter) mirrors ``cbo_tools.py`` and reuses its helpers.
"""

from __future__ import annotations

import asyncio
import csv
import gc
import logging
import os
import random
import time
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING

from tools import main_tools
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
# Reuse the GP builders from CBO (plain functions; safe to import
# even without torch installed).
from tools.cbo_tools import _build_obj_models, _build_feas_gp

# Eager-import optional deps (mirror cbo_tools; guarded so the module still
# imports without torch, keeping _mechanism_labels unit-testable).
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
        LogExpectedImprovement as _LogEI,
    )
    from botorch.acquisition.multi_objective.logei import (  # noqa: F401
        qLogNoisyExpectedHypervolumeImprovement as _qLogNEHVI,
    )
    from botorch.acquisition.multi_objective.objective import (  # noqa: F401
        IdentityMCMultiOutputObjective as _IdentityMCMO,
    )
    from botorch.models import ModelListGP as _ModelListGP  # noqa: F401
    from botorch.optim import optimize_acqf as _optimize_acqf  # noqa: F401
    from botorch.sampling.normal import (  # noqa: F401
        SobolQMCNormalSampler as _SobolQMCNormalSampler,
    )
    from botorch.utils.multi_objective.pareto import (  # noqa: F401
        is_non_dominated as _is_non_dominated,
    )
    _BOTORCH_AVAILABLE = True
    _BOTORCH_IMPORT_ERROR = None
except ImportError as _exc:
    _BOTORCH_AVAILABLE = False
    _BOTORCH_IMPORT_ERROR = str(_exc)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context

CHECKPOINT_INTERVAL = 50

# --- Adaptive-roster tuning (module-level so they're easy to find / override). ---
# Feasibility for OPAQUE crashes is a "backstop + sharpeners" model: one always-on
# lumped GP over ALL failures (= CBO's single boundary) PLUS one extra
# "sharpener" GP for each failure mechanism that has enough failures of its OWN to
# train a clean boundary. Rare/scattered failures get NO dedicated GP -- they ride
# the backstop, instead of being forced into one incoherent 'other' bucket.
DOMINANCE_THRESHOLD = 0.70     # one mechanism owning >= this share of FAILED points
                               # -> collapse to the backstop alone (= CBO).
DOMINANCE_HYSTERESIS = 0.10    # gate only DISENGAGES below (DOMINANCE_THRESHOLD - this);
                               # debounce so the GP count K can't thrash at the boundary.
MIN_COUNT_DIM_FACTOR = 2       # a mechanism needs >= this * n_dims failures OF ITS OWN
                               # (the minority/0.0 class) to earn its own sharpener GP.
GATE_MIN_FAILURES = 20         # don't let the dominance gate trip on a tiny # of failures.


# ---------------------------------------------------------------------------
# Core: feasibility label groups for OPAQUE failures (PURE, unit-testable)
# ---------------------------------------------------------------------------

def _mechanism_labels(all_tags, min_count, n_dims=0, prev_gate=False):
    """Group opaque-failure points into binary feasibility-GP label vectors.

    Returns ``(active, labels, gate_on)``. ``active`` is the ordered list of group
    names; ``labels[name]`` is a length-N list (1.0 = that group's failure did NOT
    fire here, 0.0 = it fired). ``gate_on`` is the (debounced) concentration-gate
    state, threaded back in next iteration as ``prev_gate``.

    Model = BACKSTOP + SHARPENERS:

    * ``"backstop"`` (present whenever there ARE failures): the CBO-style lumped GP
      -- ANY failure -> 0.0. Well-fed and coherent; the safety floor that coarsely
      covers every failure, including rare ones that get no own GP.
    * one SHARPENER GP per mechanism whose OWN failure count
      >= ``MIN = max(min_count, MIN_COUNT_DIM_FACTOR * n_dims)``. The count is the
      mechanism's own failures (the minority/0.0 class), so every sharpener trains on
      enough failed points to shape its boundary -- no data-starved GPs.
    * rare mechanisms (< MIN) get NO GP; they ride the backstop (no 'other' bucket).
    * concentration gate (debounced): if one mechanism owns >= DOMINANCE_THRESHOLD of
      failures (and >= GATE_MIN_FAILURES total), drop the sharpeners and keep ONLY the
      backstop (= CBO) -- the proven anti-over-exploration behaviour. The gate
      disengages only below DOMINANCE_THRESHOLD - DOMINANCE_HYSTERESIS, so K is stable.

    NOTE: ``all_tags`` should carry ONLY opaque-crash tags. Continuous, measurable
    constraints are handled by their own regression GPs (classify_mechanisms'
    double-count guard) and must NOT appear here, or they'd be modelled twice.
    """
    counts: Counter = Counter(t for tags in all_tags for t in tags)
    if not counts:
        return [], {}, False

    # Backstop label (CBO semantics): ANY failure -> 0.0, clean point -> 1.0.
    backstop = [0.0 if tags else 1.0 for tags in all_tags]
    if not (0.0 in backstop and 1.0 in backstop):
        # all-clean or all-failed: no usable binary contrast -> no GP (LogEI fallback).
        return [], {}, False

    n_failed = sum(1 for tags in all_tags if tags)
    _, top_n = counts.most_common(1)[0]
    ratio = top_n / n_failed

    # (A) Concentration gate with hysteresis (debounce): dominant mechanism -> backstop only.
    eng_thr = (DOMINANCE_THRESHOLD - DOMINANCE_HYSTERESIS) if prev_gate else DOMINANCE_THRESHOLD
    if n_failed >= GATE_MIN_FAILURES and ratio >= eng_thr:
        return ["backstop"], {"backstop": backstop}, True

    # (B) Backstop floor + a sharpener per mechanism with >= MIN failures of its own.
    MIN = max(min_count, MIN_COUNT_DIM_FACTOR * n_dims)
    active: list[str] = ["backstop"]
    labels: dict[str, list[float]] = {"backstop": backstop}
    for t in sorted(t for t, n in counts.items() if n >= MIN):
        vec = [0.0 if t in tags else 1.0 for tags in all_tags]
        if 0.0 in vec and 1.0 in vec:
            active.append(t)
            labels[t] = vec
    return active, labels, False


def _build_mech_feas_gps(X_all_t, all_tags, bounds, min_count, dtype, device,
                         n_dims=0, prev_gate=False):
    """Fit one feasibility SingleTaskGP per active group. Returns (names, gps, gate_on)."""
    torch = _torch
    active, labels, gate_on = _mechanism_labels(all_tags, min_count, n_dims=n_dims,
                                                prev_gate=prev_gate)
    gps = []
    for name in active:
        lab_t = torch.tensor([[v] for v in labels[name]], dtype=dtype, device=device)
        gps.append(_build_feas_gp(X_all_t, lab_t, bounds))
    return active, gps, gate_on


# ---------------------------------------------------------------------------
# Continuous side: regression GPs for measurable declared constraints (hybrid)
# ---------------------------------------------------------------------------

def _build_constraint_reg_gps(X_all, con_raw, constraints, bounds, dtype, device):
    """One regression GP per declared constraint, modelling its RAW value over the
    points that reached the constraint check (``con_raw[i][k]`` is None elsewhere).

    Returns ``(gps, reg_bounds)`` where ``reg_bounds[c] = (lower, upper)`` are the
    c-th built GP's raw-value bounds (aligned with ``gps``). A constraint is skipped
    if it has no bound or < 2 readable values yet. RAW value is fed as Y; Standardize
    (inside ``_build_obj_models``) handles each constraint's scale, and the (lower,
    upper) thresholds are imposed in raw units by the acquisition. This recovers the
    margin gradient that the binary backstop throws away.
    """
    torch = _torch
    gps, reg_bounds = [], []
    for i, con in enumerate(constraints or []):
        lo, hi = con.get("lower"), con.get("upper")
        if lo is None and hi is None:
            continue
        vals = con_raw[i]
        idxs = [k for k, v in enumerate(vals) if v is not None]
        if len(idxs) < 2:
            continue
        Xc = torch.tensor([X_all[k] for k in idxs], dtype=dtype, device=device)
        Yc = torch.tensor([[float(vals[k])] for k in idxs], dtype=dtype, device=device)
        gps.append(_build_obj_models(Xc, Yc, bounds, M=1).models[0])
        reg_bounds.append((lo, hi))
    return gps, reg_bounds


def _single_obj_cons(reg_bounds, n_bin):
    """LogConstrainedEI constraints dict. ModelListGP outputs are packed
    [objective, *regression(C), *binary(K)]: index 0 = objective; 1..C = constraint
    raw values (feasible iff lower <= value <= upper); C+1.. = binary GPs (feasible
    iff P(avoid) >= 0.5). PURE -- unit-testable."""
    cons = {1 + c: (lo, hi) for c, (lo, hi) in enumerate(reg_bounds)}
    base = 1 + len(reg_bounds)
    for j in range(n_bin):
        cons[base + j] = (0.5, None)
    return cons


def _multi_obj_constraints(M, reg_bounds, n_bin):
    """qLogNEHVI constraint callables (callable(Z) <= 0 means feasible). Outputs packed
    [*objectives(M), *regression(C), *binary(K)]. Each continuous constraint adds one
    callable per active bound; the binary GPs add ONE joint-product callable. The index
    math is PURE; the callables need a tensor Z."""
    cons = []
    for c, (lo, hi) in enumerate(reg_bounds):
        idx = M + c
        if lo is not None:
            cons.append(lambda Z, _i=idx, _L=lo: _L - Z[..., _i])   # value >= lower
        if hi is not None:
            cons.append(lambda Z, _i=idx, _U=hi: Z[..., _i] - _U)   # value <= upper
    if n_bin:
        base = M + len(reg_bounds)

        def joint_feas_constraint(Z, _K=n_bin, _b=base):
            p = Z[..., _b].clamp(0.0, 1.0)
            for j in range(1, _K):
                p = p * Z[..., _b + j].clamp(0.0, 1.0)
            return 0.5 - p
        cons.append(joint_feas_constraint)
    return cons


# ---------------------------------------------------------------------------
# Checkpoint (afm-cbo-labelled dir; mirrors cbo_tools._checkpoint)
# ---------------------------------------------------------------------------

def _checkpoint(output_dir, session_name, variables, objectives,
                eval_log, stats, _run_dir_holder):
    if not output_dir:
        return
    var_names = unique_names([v["aspen_path"] for v in variables])
    obj_names = [obj_label(o) for o in objectives]
    if not _run_dir_holder:
        run_dir = os.path.join(
            output_dir,
            f"opt_afm-cbo-checkpoint_{safe_file_part(session_name)}_{datetime.now():%Y%m%d_%H%M%S}",
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
    n_initial, n_iterations, q, seed, max_retries, min_count, output_dir,
) -> str:
    var_names = unique_names([v["aspen_path"] for v in variables])
    M = len(objectives)
    backend = "BoTorch cEI (single-obj + per-mechanism feasibility GPs)" if M == 1 \
        else f"BoTorch constrained qLogNEHVI ({M} objectives + per-mechanism feasibility GPs)"
    total_evals = n_initial + n_iterations * (q if M >= 2 else 1)

    lines = [
        f"=== AFM-CBO (Adaptive Failure-Mode CBO) ({backend}) Settings Preview ===",
        f"\nSession: {session_name}",
        f"Estimated evaluations: {total_evals} ({n_initial} initial + {n_iterations} AFM-CBO iters)",
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
        ("n_initial",    str(n_initial),    "LHS initial samples before AFM-CBO starts"),
        ("n_iterations", str(n_iterations), "AFM-CBO iterations after initial"),
        ("q",            str(q),            "batch size (multi-obj only)"),
        ("min_count",    str(min_count),    "min crashes floor for a sharpener GP (effective = max(this, 2*n_dims))"),
        ("seed",         str(seed) if seed is not None else "random", "random seed"),
        ("max_retries",  str(max_retries),  "simulation retry count"),
    ]
    for name, val, desc in params:
        lines.append(f"  {name:<14} {val:<14} {desc}")
    lines.append(f"\n  output_dir: {output_dir or 'not saved'}")
    n_dims = len(variables)
    eff_min = max(min_count, MIN_COUNT_DIM_FACTOR * n_dims)
    lines.append("\nKey differences vs. CBO (opaque-crash feasibility):")
    lines.append("  - 'backstop' GP (always on) over ALL crashes = CBO's boundary")
    lines.append(f"  - + one 'sharpener' GP per mechanism with >= max(min_count, "
                 f"{MIN_COUNT_DIM_FACTOR}*n_dims) = {eff_min} crashes of its own")
    lines.append("  - rare crashes ride the backstop (no own GP, no incoherent 'other')")
    lines.append("  - GPs combined as ONE joint-feasibility constraint (product >= 0.5)")
    lines.append(f"  - debounced gate: one mechanism >= "
                 f"{int(DOMINANCE_THRESHOLD * 100)}% of crashes -> backstop only (= CBO)")
    lines.append("\nTo start, call optimize again with dry_run=False.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_afm_cbo(
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
    min_count: int = 3,
    dry_run: bool = True,
    output_dir: str | None = None,
    ctx: "Context | None" = None,
    resume_from: str | None = None,
) -> str:
    """Entry point for ``optimize(algorithm='afmcbo')``."""
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
    if min_count < 1:
        return "Error: min_count must be >= 1."

    if dry_run:
        preview = _format_preview(
            session_name, variables, objectives, constraints,
            n_initial, n_iterations, q, seed, max_retries, min_count, output_dir,
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
            logger.info("AFM-CBO: loaded %d resume records from %s",
                        len(resume_records), resume_csv)
        except (FileNotFoundError, ValueError) as e:
            return f"Error loading resume CSV: {e}"

    result = await _run_afm_cbo_core(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        n_initial=n_initial, n_iterations=n_iterations,
        q=q, seed=seed, max_retries=max_retries, min_count=min_count,
        output_dir=output_dir, ctx=ctx,
        resume_records=resume_records,
    )
    return result["report"]


async def _run_afm_cbo_core(
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
    min_count: int = 3,
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
    algo_name = "AFM-CBO (cEI)" if M == 1 else f"AFM-CBO (qLogNEHVI, M={M})"
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
            f"AFM-CBO requires BoTorch. "
            f"pip install 'botorch>=0.10' (pulls in torch ~2GB)\n{_BOTORCH_IMPORT_ERROR}"
        )

    if M == 1:
        return await _run_afm_cbo_single(
            manager=manager, session_name=session_name,
            variables=variables, objectives=objectives, constraints=constraints,
            n_initial=n_initial, n_iterations=n_iterations,
            seed=seed, max_retries=max_retries, min_count=min_count,
            output_dir=output_dir, ctx=ctx,
            reporter=reporter, owns_reporter=owns_reporter,
            weights=weights, obj_labels=obj_labels,
            initial_seeds=initial_seeds, resume_records=resume_records,
        )
    return await _run_afm_cbo_multi(
        manager=manager, session_name=session_name,
        variables=variables, objectives=objectives, constraints=constraints,
        n_initial=n_initial, n_iterations=n_iterations, q=q,
        seed=seed, max_retries=max_retries, min_count=min_count,
        output_dir=output_dir, ctx=ctx,
        reporter=reporter, owns_reporter=owns_reporter,
        weights=weights, obj_labels=obj_labels,
        initial_seeds=initial_seeds, resume_records=resume_records,
    )


# ---------------------------------------------------------------------------
# Single-objective: BoTorch cEI with per-mechanism feasibility constraints
# ---------------------------------------------------------------------------

async def _run_afm_cbo_single(
    *, manager, session_name, variables, objectives, constraints,
    n_initial, n_iterations, seed, max_retries, min_count,
    output_dir, ctx, reporter, owns_reporter,
    weights, obj_labels, initial_seeds, resume_records=None,
) -> dict:
    np = _np
    torch = _torch
    ModelListGP = _ModelListGP
    LogConstrainedEI = _LogConstrainedEI
    LogEI = _LogEI
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
    _gate_state = [False]   # debounced concentration-gate state, threaded across iters

    X_all: list[list[float]] = []
    all_tags: list[list[str]] = []       # multi-label tags per point, parallel to X_all
    con_raw: list[list] = [[] for _ in (constraints or [])]  # raw constraint values // X_all
    X_feas: list[list[float]] = []
    Y_feas_max: list[float] = []

    def _record(x_decoded, f_vals, feasible, tags, reason="", con_values=None):
        X_all.append(list(x_decoded))
        # Declared constraints are handled by continuous regression GPs, so
        # classify_mechanisms(..., constraints) gives a point infeasible ONLY via such a
        # constraint NO opaque-crash tag (its (in)feasibility is carried by the
        # regression GP); it must not pollute the backstop. Only genuine opaque crashes
        # (reason not in ok/constraint) that left no tag fall back to 'unclassified'.
        if not feasible and not tags and reason not in ("ok", "constraint"):
            tags.append("unclassified")
        all_tags.append(tags)
        for _i in range(len(con_raw)):
            con_raw[_i].append(con_values.get(_i) if con_values else None)
        if feasible:
            X_feas.append(list(x_decoded))
            Y_feas_max.append(w * f_vals[0])

    start = time.time()

    if resume_records:
        for rec in resume_records:
            x = rec["x"]; f_vals = rec["f_vals"]; feas = rec["feasible"]
            eval_log.append((0, list(x), list(f_vals), feas, rec["t_s"],
                             rec["reason"], rec["detail"]))
            _record(x, f_vals, feas,
                    main_tools.classify_mechanisms(rec["reason"], rec["detail"], constraints),
                    reason=rec["reason"])
            stats.record(rec["reason"] or ("ok" if feas else "not_converged"))
        n_initial_remaining = max(0, n_initial - len(resume_records))
    else:
        n_initial_remaining = n_initial

    n_resumed = len(resume_records) if resume_records else 0
    total_expected = n_resumed + n_initial_remaining + n_iterations
    reporter.set_totals(total_evals=total_expected)
    time_offset = max((rec["t_s"] for rec in resume_records), default=0.0) \
        if resume_records else 0.0

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
                logger.warning("AFM-CBO aborted during init: %s", exc)
                break
            decoded = decode_x(list(x), variables)
            eval_log.append((0, decoded, list(f_vals), feasible, time.time() - start + time_offset,
                             _info.get("reason", ""), _info.get("detail", "")))
            _record(decoded, f_vals, feasible,
                    main_tools.classify_mechanisms(_info.get("reason", ""), _info.get("detail", ""), constraints),
                    reason=_info.get("reason", ""), con_values=_info.get("con_values"))

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

        for it in range(n_iterations):
            if aborted or reporter.poll_cancel():
                aborted = True
                break

            x_next = None
            if len(X_feas) >= 2:
                try:
                    X_all_t = torch.tensor(X_all, dtype=dtype, device=device)
                    X_feas_t = torch.tensor(X_feas, dtype=dtype, device=device)
                    Y_feas_t = torch.tensor(Y_feas_max, dtype=dtype, device=device).unsqueeze(-1)

                    obj_list = _build_obj_models(X_feas_t, Y_feas_t, bounds, M=1)
                    obj_gp = obj_list.models[0]

                    # Continuous side: regression GP per measurable constraint.
                    reg_gps, reg_bounds = _build_constraint_reg_gps(
                        X_all, con_raw, constraints, bounds, dtype, device)
                    # Opaque side: backstop + sharpeners.
                    active, feas_gps, _gate_state[0] = _build_mech_feas_gps(
                        X_all_t, all_tags, bounds, min_count, dtype, device,
                        n_dims=len(variables), prev_gate=_gate_state[0])

                    if reg_gps or feas_gps:
                        # Pack outputs [objective, *regression, *binary]; cons indexes them.
                        combined = ModelListGP(obj_gp, *reg_gps, *feas_gps)
                        cons = _single_obj_cons(reg_bounds, len(feas_gps))
                        acqf = LogConstrainedEI(
                            model=combined, best_f=Y_feas_t.max().item(),
                            objective_index=0, constraints=cons, maximize=True,
                        )
                    else:
                        # No constraints/mechanisms yet (K=0): plain unconstrained EI on
                        # the objective GP -- matches the multi-obj K=0 path and CBO,
                        # instead of wasting the GP on random LHS.
                        combined = None
                        acqf = LogEI(model=obj_gp, best_f=Y_feas_t.max().item(),
                                     maximize=True)
                    candidates, _ = optimize_acqf(
                        acq_function=acqf, bounds=bounds, q=1,
                        num_restarts=10, raw_samples=128,
                        options={"maxiter": ACQF_MAXITER},
                    )
                    x_next = candidates[0].detach().cpu().numpy().tolist()
                    del acqf, candidates
                    if combined is not None:
                        del combined
                    del obj_list, obj_gp, feas_gps, reg_gps
                    del X_all_t, X_feas_t, Y_feas_t
                except OptimizationCancelled:
                    raise
                except Exception as exc:
                    logger.warning("AFM-CBO single-obj acquisition failed at iter %d: %s", it + 1, exc)
                    x_next = None
            if x_next is None:
                x_next = lhs_sample(1, variables)[0]
                if len(X_feas) < 2:
                    logger.info("AFM-CBO iter %d: only %d feasible points, LHS fallback",
                                it + 1, len(X_feas))

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
                logger.warning("AFM-CBO aborted: %s", exc)
                break

            decoded = decode_x(list(x_next), variables)
            eval_log.append((it + 1, decoded, list(f_vals), feasible, time.time() - start + time_offset,
                             _info.get("reason", ""), _info.get("detail", "")))
            _record(decoded, f_vals, feasible,
                    main_tools.classify_mechanisms(_info.get("reason", ""), _info.get("detail", ""), constraints),
                    reason=_info.get("reason", ""), con_values=_info.get("con_values"))

            if stats.total % CHECKPOINT_INTERVAL == 0:
                _checkpoint(output_dir, session_name, variables, objectives,
                            eval_log, stats, _ckpt_dir)

            best_f_raw = max(Y_feas_max) if Y_feas_max else None
            best_display = w * best_f_raw if best_f_raw is not None else None
            reporter.update_sync(
                it + 1, stats.total, f"AFM-CBO iter {stats.total}/{total_expected}",
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
        logger.info("AFM-CBO (cEI) cancelled by user")

    wall_time = time.time() - start
    if owns_reporter:
        reporter.finalize(aborted)

    pareto: list[dict] = []
    best_obj_val: float | None = None
    best_x: list[float] | None = None
    if Y_feas_max:
        best_i = max(range(len(Y_feas_max)), key=lambda i: Y_feas_max[i])
        best_obj_val = w * Y_feas_max[best_i]
        best_x = X_feas[best_i]
        pareto = [{"x": best_x, "f": [best_obj_val]}]

    active_final, _, _ = _mechanism_labels(all_tags, min_count, n_dims=len(variables),
                                            prev_gate=_gate_state[0])
    mech_tally = Counter(t for tags in all_tags for t in tags)

    header = "ABORTED" if aborted else "AFM-CBO (cEI) complete"
    lines = [f"{header}: {stats.total} evaluations (n_initial={n_initial}, "
             f"n_iterations={n_iterations}), wall-time {wall_time:.1f}s"]
    lines.append(f"Objective GP trained on {len(X_feas)} feasible points")
    lines.append(f"Per-mechanism feasibility GPs ({len(active_final)}): "
                 f"{', '.join(active_final) if active_final else 'none yet'}")
    if best_x is not None:
        xs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, best_x))
        lines.append(f"\nBest: {xs} -> {obj_labels[0]}={best_obj_val:.6g} ({obj_dir})")
    else:
        lines.append("\nNo feasible solution found.")

    lines.append("")
    lines.append(stats.format_report())
    if mech_tally:
        lines.append("- Failure mechanisms (multi-label):")
        for tag, n in sorted(mech_tally.items(), key=lambda kv: -kv[1]):
            lines.append(f"  - {tag}: {n}")

    if debug_log:
        unique_msgs = list(dict.fromkeys(debug_log[:20]))
        lines.append(f"\nFailure details ({len(debug_log)}):")
        lines += [f"  {m}" for m in unique_msgs]

    log_lines = [f"AFM-CBO (cEI): {stats.total} evals, per-mechanism feasibility GPs + cEI"]

    if output_dir:
        try:
            settings = {
                "Algorithm": "AFM-CBO (cEI, BoTorch)",
                "Feasibility mode": "decomposed (per-mechanism)",
                "n_initial": n_initial,
                "n_iterations": n_iterations,
                "min_count": min_count,
                "Seed": seed if seed is not None else "random",
                "Max retries": max_retries,
                "Obj GP points": len(X_feas),
                "Mechanism GPs": len(active_final),
                "Mechanisms": ", ".join(active_final) if active_final else "none",
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm="AFM-CBO-cEI", session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings, pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save AFM-CBO results: %s", e, exc_info=True)
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
# Multi-objective: BoTorch qLogNEHVI with per-mechanism feasibility constraints
# ---------------------------------------------------------------------------

async def _run_afm_cbo_multi(
    *, manager, session_name, variables, objectives, constraints,
    n_initial, n_iterations, q, seed, max_retries, min_count,
    output_dir, ctx, reporter, owns_reporter,
    weights, obj_labels, initial_seeds, resume_records=None,
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
    _gate_state = [False]   # debounced concentration-gate state, threaded across iters

    X_all: list[list[float]] = []
    all_tags: list[list[str]] = []       # multi-label tags per point, parallel to X_all
    con_raw: list[list] = [[] for _ in (constraints or [])]  # raw constraint values // X_all
    X_feas: list[list[float]] = []
    Y_feas_max: list[list[float]] = []
    time_offset: float = 0.0

    def _record(x_decoded, f_vals, feasible, tags, reason="", con_values=None):
        X_all.append(list(x_decoded))
        # Declared constraints are handled by continuous regression GPs, so
        # classify_mechanisms(..., constraints) gives a point infeasible ONLY via such a
        # constraint NO opaque-crash tag (its (in)feasibility is carried by the
        # regression GP); it must not pollute the backstop. Only genuine opaque crashes
        # (reason not in ok/constraint) that left no tag fall back to 'unclassified'.
        if not feasible and not tags and reason not in ("ok", "constraint"):
            tags.append("unclassified")
        all_tags.append(tags)
        for _i in range(len(con_raw)):
            con_raw[_i].append(con_values.get(_i) if con_values else None)
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
            logger.warning("AFM-CBO aborted: %s", exc)
            return
        decoded = decode_x(x, variables)
        eval_log.append((it_num, decoded, list(f_vals), feasible, time.time() - start + time_offset,
                         _info.get("reason", ""), _info.get("detail", "")))
        _record(decoded, f_vals, feasible,
                main_tools.classify_mechanisms(_info.get("reason", ""), _info.get("detail", ""), constraints),
                reason=_info.get("reason", ""), con_values=_info.get("con_values"))

        if stats.total % CHECKPOINT_INTERVAL == 0:
            _checkpoint(output_dir, session_name, variables, objectives,
                        eval_log, stats, _ckpt_dir)

    start = time.time()

    if resume_records:
        for rec in resume_records:
            x = rec["x"]; f_vals = rec["f_vals"]; feas = rec["feasible"]
            eval_log.append((0, list(x), list(f_vals), feas, rec["t_s"],
                             rec["reason"], rec["detail"]))
            _record(x, f_vals, feas,
                    main_tools.classify_mechanisms(rec["reason"], rec["detail"], constraints),
                    reason=rec["reason"])
            stats.record(rec["reason"] or ("ok" if feas else "not_converged"))
        n_initial_remaining = max(0, n_initial - len(resume_records))
        time_offset = max((rec["t_s"] for rec in resume_records), default=0.0)
    else:
        n_initial_remaining = n_initial

    n_resumed = len(resume_records) if resume_records else 0
    total_expected = n_resumed + n_initial_remaining + n_iterations * q
    reporter.set_totals(total_evals=total_expected)

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

        for it in range(n_iterations):
            if aborted or reporter.poll_cancel():
                aborted = True
                break

            if len(X_feas) < 2:
                candidates_np = np.array(lhs_sample(q, variables))
                logger.info("AFM-CBO iter %d: only %d feasible points, falling back to LHS",
                            it + 1, len(X_feas))
            else:
                try:
                    X_all_t = torch.tensor(X_all, dtype=dtype, device=device)
                    X_feas_t = torch.tensor(X_feas, dtype=dtype, device=device)
                    Y_feas_t = torch.tensor(Y_feas_max, dtype=dtype, device=device)

                    obj_model = _build_obj_models(X_feas_t, Y_feas_t, bounds, M=M)

                    reg_gps, reg_bounds = _build_constraint_reg_gps(
                        X_all, con_raw, constraints, bounds, dtype, device)

                    active, feas_gps, _gate_state[0] = _build_mech_feas_gps(
                        X_all_t, all_tags, bounds, min_count, dtype, device,
                        n_dims=len(variables), prev_gate=_gate_state[0])

                    combined = ModelListGP(*obj_model.models, *reg_gps, *feas_gps)
                    Y_min = Y_feas_t.min(dim=0).values
                    Y_max = Y_feas_t.max(dim=0).values
                    Y_ref = Y_min - 0.1 * (Y_max - Y_min)
                    mo_objective = IdentityMCMO(outcomes=list(range(M)))

                    # Feasibility constraints, in output-packing order obj -> reg -> binary:
                    #  * one outcome constraint per measurable-constraint bound (value in
                    #    [lower, upper]) -- the continuous regression GPs;
                    #  * ONE joint-product constraint over the binary backstop+sharpeners
                    #    (feasible <=> P(all avoided) >= 0.5). The product (not per-GP AND)
                    #    stops knife-edge points that fail via *alternating* mechanisms from
                    #    clearing every individual >=0.5 filter and being re-probed forever.
                    mech_constraints = _multi_obj_constraints(M, reg_bounds, len(feas_gps))

                    nd_mask = _is_non_dominated(Y_feas_t)
                    X_baseline_t = X_feas_t[nd_mask]
                    if X_baseline_t.shape[0] < 2:
                        X_baseline_t = X_feas_t

                    sampler = SobolQMCNormalSampler(sample_shape=torch.Size([128]))
                    acqf = qLogNEHVI(
                        model=combined,
                        ref_point=Y_ref,
                        X_baseline=X_baseline_t,
                        sampler=sampler,
                        objective=mo_objective,
                        constraints=(mech_constraints or None),
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
                    del acqf, combined, obj_model, feas_gps, reg_gps, candidates, sampler
                    del X_all_t, X_feas_t, Y_feas_t
                    del Y_min, Y_max, Y_ref, mo_objective, mech_constraints
                    del nd_mask, X_baseline_t
                except OptimizationCancelled:
                    raise
                except Exception as exc:
                    logger.warning("AFM-CBO multi-obj acquisition failed at iter %d: %s", it + 1, exc)
                    candidates_np = np.array(lhs_sample(q, variables))

            for x_row in candidates_np:
                if aborted:
                    break
                _evaluate(x_row.tolist(), it + 1)
                reporter.update_sync(
                    it + 1, stats.total,
                    f"AFM-CBO {stats.total}/{total_expected} (q={q})",
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
        logger.info("AFM-CBO (qLogNEHVI) cancelled by user")

    wall_time = time.time() - start
    if owns_reporter:
        reporter.finalize(aborted)

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
    active_final, _, _ = _mechanism_labels(all_tags, min_count, n_dims=len(variables),
                                            prev_gate=_gate_state[0])
    mech_tally = Counter(t for tags in all_tags for t in tags)

    def _fmt_point(p):
        xs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, p["x"]))
        fs = ", ".join(f"{n}={v:.4g} ({dr})"
                       for n, v, dr in zip(obj_labels, p["f"], obj_dirs))
        return f"{xs} -> {fs}"

    header = "ABORTED" if aborted else "AFM-CBO (qLogNEHVI) complete"
    lines = [f"{header}: {stats.total} evals (n_initial={n_initial}, "
             f"n_iterations={n_iterations}, q={q}), wall-time {wall_time:.1f}s"]
    lines.append(f"Objective GPs trained on {len(X_feas)} feasible points")
    lines.append(f"Per-mechanism feasibility GPs ({len(active_final)}): "
                 f"{', '.join(active_final) if active_final else 'none yet'}")
    lines.append(f"\nPareto Front ({len(pareto)} solutions):")
    for idx, p in enumerate(pareto):
        marker = " <<<" if idx == comp_idx else ""
        lines.append(f"  #{idx + 1}: {_fmt_point(p)}{marker}")

    if pareto and comp_idx >= 0:
        lines.append(f"\nBest compromise: {_fmt_point(pareto[comp_idx])}")

    lines.append("")
    lines.append(stats.format_report())
    if mech_tally:
        lines.append("- Failure mechanisms (multi-label):")
        for tag, n in sorted(mech_tally.items(), key=lambda kv: -kv[1]):
            lines.append(f"  - {tag}: {n}")

    if debug_log:
        unique_msgs = list(dict.fromkeys(debug_log[:20]))
        lines.append(f"\nFailure details ({len(debug_log)}):")
        lines += [f"  {m}" for m in unique_msgs]

    log_lines = [f"AFM-CBO (qLogNEHVI): {stats.total} evals, q={q}, "
                 f"per-mechanism feasibility GPs + constrained HVI"]

    if output_dir:
        try:
            settings = {
                "Algorithm": "AFM-CBO (qLogNEHVI, BoTorch)",
                "Feasibility mode": "decomposed (per-mechanism)",
                "n_initial": n_initial,
                "n_iterations": n_iterations,
                "Batch q": q,
                "min_count": min_count,
                "Seed": seed if seed is not None else "random",
                "Max retries": max_retries,
                "Obj GP points": len(X_feas),
                "Mechanism GPs": len(active_final),
                "Mechanisms": ", ".join(active_final) if active_final else "none",
                "Wall-time (s)": f"{wall_time:.1f}",
            }
            path = save_results_generic(
                algorithm="AFM-CBO-qLogNEHVI", session_name=session_name,
                variables=variables, objectives=objectives, constraints=constraints,
                settings=settings, pareto=pareto, weights=weights,
                log_lines=log_lines, eval_log=eval_log, stats=stats,
                output_dir=output_dir,
            )
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save AFM-CBO results: %s", e, exc_info=True)
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
