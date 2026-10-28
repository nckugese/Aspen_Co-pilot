"""Shared evaluation core for all optimization algorithms.

Provides:
- ``evaluate_x``: the universal Aspen evaluation function (set vars → run → read
  objectives/constraints → return penalty on failure).
- ``EvalStats``: failure-reason bookkeeping.
- ``ProgressReporter``: Tkinter progress window (same one used by NSGA-II).
- ``lhs_sample`` / ``best_compromise`` / ``decode_x`` / ``read_objective`` helpers
  used by every optimizer.
- ``save_results_generic``: Markdown + CSV report writer usable by all algorithms.
"""

from __future__ import annotations

import ast
import asyncio
import contextvars
import csv
import json
import logging
import math
import operator
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools import dialogs, main_tools, probes

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context


# ---------------------------------------------------------------------------
# Shared helpers used by every optimizer's ``_run_*_core`` function
# ---------------------------------------------------------------------------

def error_result(msg: str) -> dict:
    """Canonical error-return shape for optimizer core functions."""
    return {
        "report": f"Error: {msg}",
        "pareto": [], "eval_log": [], "stats": None,
        "wall_time": 0.0, "weights": (), "aborted": True,
        "best_compromise_idx": -1,
    }


def validate_session(manager, session_name: str) -> dict | None:
    """Return ``error_result`` dict if no active session, else ``None``."""
    if manager.get_app(session_name) is None:
        return error_result(
            f"No active Aspen session '{session_name}'. "
            f"Open Aspen first with open_aspen_plus."
        )
    return None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PENALTY = 1e10
DEFAULT_PENALTY_SCALE = 1e8  # base scale for distance-based constraint penalty
INFEASIBLE_VIOLATION = 1e6   # marker violation value when simulation itself fails
MAX_CONSECUTIVE_COM_FAILS = 3  # abort after N consecutive COM-level crashes

# L-BFGS step cap for one acquisition optimization (bo / cbo / afmcbo). botorch's default is
# 2000. On a 300-evaluation AFM-CBO state (3 objectives, 10 variables) L-BFGS ran about 850
# steps under that default and one candidate took 139 s; at 200 it took 43 s, and the
# acquisition value moved less than the spread between two quasi-Monte-Carlo draws. 200 is
# the value botorch's own tutorials use.
ACQF_MAXITER = 200


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

_UNSAFE_FILE_CHARS = re.compile(r"[^\w.-]")


def safe_file_part(text: str) -> str:
    """``text`` made safe as part of a file or folder name: anything but letters, digits,
    ``_``, ``.`` and ``-`` becomes ``_`` (no path separators, no drive letters); leading dots
    are dropped so it can never be ``..``."""
    s = _UNSAFE_FILE_CHARS.sub("_", str(text or "")).lstrip(".")
    return s or "session"


def short_name(path: str) -> str:
    parts = path.replace("\\\\", "\\").strip("\\").split("\\")
    return parts[-1] if parts else path


def unique_names(paths: list[str]) -> list[str]:
    short = [short_name(p) for p in paths]
    counts = Counter(short)
    if max(counts.values()) <= 1:
        return short
    result = []
    for i, (s, p) in enumerate(zip(short, paths)):
        if counts[s] > 1:
            parts = p.replace("\\\\", "\\").strip("\\").split("\\")
            result.append(f"{parts[2]}_{s}" if len(parts) > 2 else f"{i}_{s}")
        else:
            result.append(s)
    return result


def obj_label(obj: dict) -> str:
    if "aspen_paths" in obj:
        expr = obj.get("expression")
        if expr:
            return expr
        return "+".join(short_name(p) for p in obj["aspen_paths"])
    return short_name(obj["aspen_path"])


# ---------------------------------------------------------------------------
# Safe expression namespace (for objectives using `expression`)
# ---------------------------------------------------------------------------

_EXPR_NAMESPACE = {k: getattr(math, k) for k in
                   ("sqrt", "log", "log10", "exp", "sin", "cos", "tan",
                    "pow", "pi", "e", "floor", "ceil", "fabs")}
_EXPR_NAMESPACE["abs"] = abs
_EXPR_NAMESPACE["max"] = max
_EXPR_NAMESPACE["min"] = min

_EXPR_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
             ast.Pow: lambda a, b: float(a) ** b}   # float: a huge power overflows at once instead of hanging
_EXPR_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}
_EXPR_CMP = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
             ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}
_EXPR_MAX_LEN = 1000


def eval_expression(expr: str, ns: dict) -> float:
    """Value of an objective/constraint ``expression`` over the names in ``ns``, evaluated by
    walking its syntax tree: numbers, names from ``ns``, + - * / // % **, unary - and +,
    comparisons, ``and``/``or``/``not``, ``a if c else b`` and calls of the callables in
    ``ns``. Anything else (attributes, subscripts, strings, keywords, lambdas) raises
    ValueError, so an expression from a tool argument or a resumed config.json can only
    compute. Arithmetic errors propagate as Python raises them."""
    text = str(expr if expr is not None else "")
    if len(text) > _EXPR_MAX_LEN:
        raise ValueError(f"expression longer than {_EXPR_MAX_LEN} characters")
    tree = ast.parse(text.strip(), mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError(f"only numbers are allowed, not {node.value!r}")
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in ns or callable(ns[node.id]):
                raise ValueError(f"unknown name {node.id!r}")
            return ns[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _EXPR_BIN:
            return _EXPR_BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _EXPR_UNARY:
            return _EXPR_UNARY[type(node.op)](ev(node.operand))
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                val = True
                for v in node.values:
                    val = ev(v)
                    if not val:
                        return val
                return val
            val = False
            for v in node.values:
                val = ev(v)
                if val:
                    return val
            return val
        if isinstance(node, ast.Compare) and all(type(o) in _EXPR_CMP for o in node.ops):
            left = ev(node.left)
            for o, comp in zip(node.ops, node.comparators):
                right = ev(comp)
                if not _EXPR_CMP[type(o)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return ev(node.body) if ev(node.test) else ev(node.orelse)
        if isinstance(node, ast.Call):
            if (not isinstance(node.func, ast.Name) or node.keywords
                    or not callable(ns.get(node.func.id))):
                raise ValueError("only plain calls of the listed functions are allowed")
            return ns[node.func.id](*[ev(a) for a in node.args])
        raise ValueError(f"{type(node).__name__} is not allowed in an expression")

    return ev(tree)


# ---------------------------------------------------------------------------
# Decoding / reading
# ---------------------------------------------------------------------------

def decode_x(x, variables: list[dict]) -> list[float]:
    """Clip x to variable bounds and round ints."""
    decoded = []
    for gene, var in zip(x, variables):
        v = max(var["lower"], min(var["upper"], float(gene)))
        if var.get("type") == "int":
            v = round(v)
        decoded.append(v)
    return decoded


def read_value(manager, session_name: str, path: str):
    raw = manager.get_node_value(session_name, path)
    try:
        return float(raw.split("(")[0].strip())
    except (ValueError, TypeError, AttributeError):
        return None


def read_objective(manager, session_name: str, obj: dict):
    if "aspen_paths" in obj:
        values = []
        for p in obj["aspen_paths"]:
            v = read_value(manager, session_name, p)
            if v is None:
                return None
            values.append(v)
        expr = obj.get("expression")
        if expr:
            ns = dict(_EXPR_NAMESPACE)
            for i, val in enumerate(values):
                ns[f"v{i}"] = val
            try:
                return float(eval_expression(expr, ns))
            except Exception:
                logger.warning("Expression eval failed: '%s' with values %s", expr, values,
                               exc_info=True)
                return None
        return sum(values)
    return read_value(manager, session_name, obj["aspen_path"])


# ---------------------------------------------------------------------------
# Evaluation statistics
# ---------------------------------------------------------------------------

@dataclass
class EvalStats:
    total: int = 0
    successes: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)
    consecutive_com_fails: int = 0
    aborted: bool = False
    abort_reason: str = ""

    def record(self, reason: str):
        self.total += 1
        if reason == "ok":
            self.successes += 1
            self.consecutive_com_fails = 0
        else:
            self.by_reason[reason] = self.by_reason.get(reason, 0) + 1
            if reason == "com_error":
                self.consecutive_com_fails += 1
            else:
                self.consecutive_com_fails = 0

    @property
    def failures(self) -> int:
        return self.total - self.successes

    @property
    def failure_rate(self) -> float:
        return self.failures / self.total if self.total > 0 else 0.0

    def format_report(self) -> str:
        lines = [
            "## Evaluation Statistics",
            f"- Total evaluations: {self.total}",
            f"- Successes: {self.successes} ({(1 - self.failure_rate) * 100:.1f}%)",
            f"- Failures: {self.failures}",
        ]
        for reason, n in sorted(self.by_reason.items(), key=lambda kv: -kv[1]):
            lines.append(f"  - {reason}: {n}")
        if self.failure_rate > 0.3:
            lines.append("")
            lines.append("WARNING: failure rate > 30%. Suggestions:")
            lines.append("  1. Check variable bounds cover only physically reasonable ranges")
            lines.append("  2. Add tighter constraints to narrow the search space")
            lines.append("  3. Invoke the aspen-error-troubleshooting skill to diagnose")
        return "\n".join(lines)


class OptimizationAborted(RuntimeError):
    """Raised by the evaluation after the one that reached the consecutive-failure limit
    (that one returns its failure, so it is logged); optimizers should catch this and
    return partial results."""


class OptimizationCancelled(RuntimeError):
    """Raised when the user clicks Cancel in the progress window."""


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

# Who watches the evaluations of the optimization running now: a callable given
# ``(decoded_x, values, feasible)`` after every ``evaluate_x``, failed ones included. The
# ``optimize`` dispatcher sets it to know whether the model was touched and which point
# to leave it at. Unset (an entry point called directly), nothing is called.
eval_observer: contextvars.ContextVar = contextvars.ContextVar("eval_observer", default=None)


def status_failed(status_msg: str) -> bool:
    """Whether a Run-Status message (``main_tools._check_run_status``, as Aspen cased it) means
    the run failed; a warning whose text says "error" does not (``probes.run_failed``)."""
    return probes.run_failed(status_msg)


def confirm_run(app, manager=None, session=None) -> tuple[str, str]:
    """Run once so the results match the inputs just written: ``("ok" | "warn" | "error" |
    "unknown" | "refused", detail)`` -- Aspen's run status judged as the journal judges it
    (``probes.run_state`` on the lines ``main_tools._check_run_status`` read: a line every clean
    run carries is not a warning); "unknown": the run status could not be read, not ok. Runs
    without Reinit first; when that ends in errors, Reinit and run once more. Given the
    ``manager`` and ``session``: "refused", not run at all (Aspen never asked; the journal's
    run record says so, not failed), in a session Aspen reported an internal fault in
    (main_tools.fault_refusal) -- no more ok than "error"."""
    refused = main_tools.fault_refusal(manager, session) if manager is not None else None
    if refused:
        return "refused", refused
    detail = ""
    for attempt in range(2):
        try:
            t = time.perf_counter()
            with dialogs.suppressed(app):
                if attempt:
                    app.Reinit()
                app.Run2()
                while app.Engine.IsRunning:
                    time.sleep(0.5)
            status = main_tools._check_run_status(app) or ""
        except Exception as exc:
            detail = f"{type(exc).__name__}: " + " ".join(str(exc).split())
            continue
        lines = probes.said_lines(app, status, t)
        verdict = probes.run_state(None, blocks=False, lines=lines)["status"] if lines is not None else "unknown"
        if verdict == "ok":
            return "ok", ""
        if verdict in ("warn", "unknown"):
            return verdict, " ".join(status.split())
        detail = main_tools.extract_error_keywords(app) or " ".join(status.split())
    return "error", detail


def evaluate_x(
    x: list[float],
    *,
    manager,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    weights: tuple[float, ...],
    max_retries: int = 1,
    debug_log: list | None = None,
    stats: EvalStats | None = None,
    return_violation: bool = False,
    info: dict | None = None,
):
    """Run one Aspen evaluation.

    Returns
    -------
    (f_values, feasible, reason) when ``return_violation`` is False (default).
    (f_values, feasible, reason, violation) when ``return_violation`` is True.

    If ``info`` (a dict) is supplied, it is populated with ``info["reason"]`` and
    ``info["detail"]`` for this evaluation. ``detail`` is the actual Aspen error
    keyword (e.g. "COL1: COLUMN NOT IN MASS BALANCE"), the failing node path, or
    the violated constraint — empty on success. This is recorded per evaluation
    into evaluations.csv without changing the return tuple.

    ``violation``:
      - 0.0 if feasible (or no constraints)
      - > 0.0 (sum of all constraint violations) if constraint(s) violated
        — in this case ``f_values`` contains the REAL objective values, not penalty
      - INFEASIBLE_VIOLATION (large positive) if simulation itself failed
        — ``f_values`` contains penalty
    """
    def _penalty():
        return [(-w) * PENALTY for w in weights]

    def _dbg(msg: str):
        if debug_log is not None:
            debug_log.append(msg)

    observer = eval_observer.get()

    def _observe(vals: list[float], feasible: bool):
        if observer is not None:
            try:
                observer(list(decoded), list(vals), bool(feasible))
            except Exception:
                logger.debug("eval observer failed", exc_info=True)

    def _done(reason: str, vals: list[float], feasible: bool, violation: float = 0.0,
              detail: str = ""):
        _observe(vals, feasible)
        if stats is not None:
            stats.record(reason)
        if info is not None:
            info["reason"] = reason
            info["detail"] = detail
        if return_violation:
            return vals, feasible, reason, violation
        return vals, feasible, reason

    decoded = decode_x(x, variables)
    # The call that hit the limit returned its failure, so the caller logged it; this one aborts.
    if stats is not None and stats.aborted:
        raise OptimizationAborted(stats.abort_reason)

    # --- Layer 0: reinitialize simulation before each evaluation -------------
    try:
        app = manager.get_app(session_name)
        with dialogs.suppressed(app):
            app.Reinit()
    except Exception as exc:
        logger.debug("Reinit before eval failed: %s", exc)

    # --- Layer 1: set decision variables -------------------------------------
    for val, var in zip(decoded, variables):
        set_val = int(val) if var.get("type") == "int" else val
        try:
            result = manager.set_node_value(session_name, var["aspen_path"], value=set_val)
        except Exception as exc:
            _dbg(f"SET_EXC: {var['aspen_path']}={set_val} → {exc}")
            return _done("set_fail", _penalty(), False, INFEASIBLE_VIOLATION,
                         f"set_exc {var['aspen_path']}={set_val}: "
                         + " ".join(str(exc).split()))
        if not result.startswith("Set "):
            _dbg(f"SET_FAIL: {var['aspen_path']}={set_val} → {result}")
            return _done("set_fail", _penalty(), False, INFEASIBLE_VIOLATION,
                         f"set_rejected {var['aspen_path']}={set_val}: "
                         + " ".join(str(result).split()))

    # --- Layer 2: Run2() with retry (and COM-error detection) ---------------
    # Auto-reopen to shake off Aspen's accumulated state (history/fortran
    # scratch files / COM memory). Controlled via ``manager.set_reopen_interval``.
    if (manager.reopen_every is not None
            and manager.eval_count > 0
            and manager.eval_count % manager.reopen_every == 0):
        logger.info("Auto-reopen triggered at eval %d", manager.eval_count)
        manager.reopen(session_name)
        # Re-apply variable values after reopen (they reset to .bkp defaults)
        for val, var in zip(decoded, variables):
            set_val = int(val) if var.get("type") == "int" else val
            try:
                manager.set_node_value(session_name, var["aspen_path"], value=set_val)
            except Exception:
                logger.debug("Re-apply var after reopen failed", exc_info=True)
    manager.eval_count += 1

    try:
        app = manager.get_app(session_name)
    except Exception as exc:
        _dbg(f"GET_APP_FAIL: {exc}")
        return _done("com_error", _penalty(), False, INFEASIBLE_VIOLATION,
                     "get_app: " + " ".join(str(exc).split()))

    run_ok = False
    last_exc = None
    for attempt in range(max_retries):
        try:
            with dialogs.suppressed(app):
                app.Run2()
                while app.Engine.IsRunning:
                    time.sleep(0.5)
            run_ok = True
            break
        except Exception as exc:
            last_exc = exc
            logger.debug("Run2() attempt %d failed: %s", attempt + 1, exc)
            if attempt < max_retries - 1:
                try:
                    with dialogs.suppressed(app):
                        app.Reinit()
                    time.sleep(0.5)
                except Exception:
                    logger.debug("Reinit before retry failed", exc_info=True)

    if not run_ok:
        _observe(_penalty(), False)
        exc_name = type(last_exc).__name__ if last_exc else "Unknown"
        is_com = "com_error" in exc_name.lower() or "pywintypes" in exc_name.lower()
        reason = "com_error" if is_com else "run_fail"
        _dbg(f"RUN_FAIL ({reason}) after {max_retries} attempts: {last_exc}")
        if info is not None:
            info["reason"] = reason
            info["detail"] = f"{exc_name}: " + " ".join(str(last_exc).split())
        if stats is not None:
            stats.record(reason)
            if stats.consecutive_com_fails >= MAX_CONSECUTIVE_COM_FAILS:
                stats.aborted = True
                stats.abort_reason = (
                    f"Aspen session may have crashed "
                    f"({stats.consecutive_com_fails} consecutive COM errors). "
                    f"Close and reopen Aspen, or recreate the session with open_aspen_plus."
                )
        if return_violation:
            return _penalty(), False, reason, INFEASIBLE_VIOLATION
        return _penalty(), False, reason

    # --- Layer 3: simulation status check -----------------------------------
    try:
        status_msg = main_tools._check_run_status(app) or ""
        if status_failed(status_msg):
            _dbg(f"STATUS_FAIL: {status_msg}")
            detail = main_tools.extract_error_keywords(app) or "run completed with errors"
            return _done("not_converged", _penalty(), False, INFEASIBLE_VIOLATION, detail)
    except Exception:
        logger.debug("Could not check run status during eval", exc_info=True)

    # --- Layer 4: read objectives --------------------------------------------
    obj_values = []
    for obj in objectives:
        v = read_objective(manager, session_name, obj)
        if v is None:
            _dbg(f"OBJ_READ_FAIL: {obj}")
            return _done("obj_read_fail", _penalty(), False, INFEASIBLE_VIOLATION,
                         f"objective read failed: {obj_label(obj)}")
        obj_values.append(v)

    # --- Layer 5: check constraints (distance-based) ------------------------
    total_violation = 0.0
    viol_details: list[str] = []
    for ci, con in enumerate(constraints or []):
        if "aspen_paths" in con:
            val = read_objective(manager, session_name, con)
        else:
            val = read_value(manager, session_name, con["aspen_path"])
        if val is None:
            con_label = ", ".join(con.get("aspen_paths", [])) or con.get("aspen_path", "?")
            _dbg(f"CONSTRAINT_READ_FAIL: {con_label}")
            return _done("obj_read_fail", _penalty(), False, INFEASIBLE_VIOLATION,
                         f"constraint read failed: {con_label}")
        if info is not None:
            # Expose each constraint's RAW value (feasible AND violated points) so a
            # continuous regression GP can be trained on it (afm_cbo hybrid). Additive;
            # other optimizers simply ignore this info key.
            info.setdefault("con_values", {})[ci] = val
        lo, hi = con.get("lower"), con.get("upper")
        violation = 0.0
        if lo is not None and val < lo:
            violation += (lo - val)
        if hi is not None and val > hi:
            violation += (val - hi)
        if violation > 0:
            con_label = con.get("expression") or ", ".join(con.get("aspen_paths", [])) or con.get("aspen_path", "?")
            _dbg(f"CONSTRAINT_VIOLATED: {con_label}={val} (violation={violation:.4g})")
            total_violation += violation
            viol_details.append(f"{short_name(str(con_label))}={val:.4g} (viol={violation:.4g})")

    if total_violation > 0:
        # Caller may want raw obj_values (with violation) or penalty (legacy).
        # New CV-aware callers pass return_violation=True and get raw values.
        # Legacy callers get the penalty path for backward compatibility.
        detail = "constraint violated: " + "; ".join(viol_details)
        if return_violation:
            return _done("constraint", obj_values, False, total_violation, detail)
        penalty_vals = [(-w) * DEFAULT_PENALTY_SCALE * (1 + total_violation) for w in weights]
        return _done("constraint", penalty_vals, False, 0.0, detail)

    return _done("ok", obj_values, True, 0.0)


def is_feasible_values(values: list[float]) -> bool:
    """Heuristic: value with abs >= PENALTY * 0.1 is a penalty, not a real eval."""
    return all(abs(v) < PENALTY * 0.1 for v in values)


def unpack_eval_entry(entry: tuple):
    """Normalize an eval_log entry to a fixed 7-field tuple.

    Returns ``(iteration, decoded, obj_vals, feasible, time_s, reason, detail)``.
    Tolerates legacy entry shapes so old result dicts still load:
      - 4-tuple: ``(iter, decoded, obj_vals, feasible)``      (no time_s)
      - 5-tuple: ``(..., time_s)``                            (no reason/detail)
      - 7-tuple: ``(..., reason, detail)``                    (current)
    """
    it = entry[0]
    decoded = entry[1]
    obj_vals = entry[2]
    feasible = entry[3]
    t_s = entry[4] if len(entry) > 4 else 0.0
    reason = entry[5] if len(entry) > 5 else ("ok" if feasible else "")
    detail = entry[6] if len(entry) > 6 else ""
    return it, decoded, obj_vals, feasible, t_s, reason, detail


# ---------------------------------------------------------------------------
# Resume from prior CSV
# ---------------------------------------------------------------------------

def load_resume_records(csv_path: str, variables: list[dict],
                        objectives: list[dict]) -> list[dict]:
    """Read a checkpoint / final-results CSV and return prior eval records.

    Each returned dict has: ``x`` (decoded list), ``f_vals``, ``feasible``,
    ``reason``, ``detail``, ``t_s``.

    CSV must contain columns matching the *short names* of variables and
    objectives (as produced by ``unique_names``), plus a ``feasible`` 0/1
    column. ``reason`` and ``error_detail`` columns are optional.
    """
    var_names = unique_names([v["aspen_path"] for v in variables])
    # Objective column names must mirror the CSV writer, which labels columns
    # with obj_label() (the expression string for multi-path objectives). Using
    # unique_names(first_path) here mismatched expression-based objectives and
    # broke resume with "missing columns" (e.g. looked for QCALC instead of
    # "v0+v1+v2+v3+v4").
    obj_names = [obj_label(o) for o in objectives]
    records: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        missing = [c for c in var_names + obj_names + ["feasible"]
                   if c not in headers]
        if missing:
            raise ValueError(
                f"resume CSV missing columns: {missing}. got: {headers}"
            )
        for row in reader:
            try:
                x = [float(row[n]) for n in var_names]
                f_vals = [float(row[n]) for n in obj_names]
                feas = bool(int(float(row["feasible"])))
            except (ValueError, KeyError) as e:
                logger.warning("Skipping malformed row in resume CSV: %s", e)
                continue
            records.append({
                "x": x, "f_vals": f_vals, "feasible": feas,
                "reason": row.get("reason", "ok" if feas else ""),
                "detail": row.get("error_detail", ""),
                "t_s": float(row.get("time_s", 0.0) or 0.0),
            })
    return records


def resolve_resume(resume_from: str) -> tuple[str, dict | None]:
    """Resolve a resume path to ``(evaluations_csv_path, config_dict_or_None)``.

    ``resume_from`` may be a prior run **folder** or an ``evaluations.csv`` path.
    A sibling ``config.json`` (written by ``save_results_generic``) is read when
    present, so a resume can reload the exact variables / objectives /
    constraints instead of re-specifying them by hand.
    """
    if os.path.isdir(resume_from):
        csv_path = os.path.join(resume_from, "evaluations.csv")
        cfg_path = os.path.join(resume_from, "config.json")
    else:
        csv_path = resume_from
        cfg_path = os.path.join(os.path.dirname(resume_from), "config.json")
    cfg = None
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except (ValueError, OSError):
            logger.warning("Failed to read resume config %s", cfg_path, exc_info=True)
    return csv_path, cfg


def resume_preview(csv_path: str, variables: list[dict], objectives: list[dict],
                   n_initial: int, n_iterations: int, mult: int) -> str:
    """Dry-run note for a resume: prior-evaluation count, column match, and the
    projected total evaluations after this run. ``mult`` is the batch size
    ``q`` for multi-objective (else 1)."""
    lines = ["\n--- Resume ---", f"  resume CSV: {csv_path}"]
    try:
        records = load_resume_records(csv_path, variables, objectives)
        n_resumed = len(records)
        n_init_rem = max(0, n_initial - n_resumed)
        added = n_init_rem + n_iterations * mult
        lines.append(f"  loaded {n_resumed} prior evaluations (columns match OK)")
        lines.append(f"  this run adds {added} (init {n_init_rem} + iters "
                     f"{n_iterations}×{mult}) -> projected total {n_resumed + added}")
    except FileNotFoundError:
        lines.append("  WARNING: resume CSV not found — the run would start fresh.")
    except ValueError as e:
        lines.append(f"  ERROR: {e}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Best compromise (normalized distance to ideal)
# ---------------------------------------------------------------------------

def best_compromise(fitness_matrix: list[list[float]], weights: tuple[float, ...]) -> int:
    """Return index of the Pareto point closest to the ideal in normalized space.

    ``fitness_matrix`` is a list of objective vectors (raw values, not sign-flipped).
    ``weights`` is +1 for maximize, -1 for minimize.
    """
    if len(fitness_matrix) <= 1:
        return 0
    n = len(weights)
    mins = [min(r[i] for r in fitness_matrix) for i in range(n)]
    maxs = [max(r[i] for r in fitness_matrix) for i in range(n)]

    best_idx, best_dist = 0, float("inf")
    for idx, row in enumerate(fitness_matrix):
        dist = 0.0
        for i in range(n):
            span = maxs[i] - mins[i]
            if span == 0:
                continue
            ideal = maxs[i] if weights[i] > 0 else mins[i]
            dist += ((row[i] - ideal) / span) ** 2
        dist = math.sqrt(dist)
        if dist < best_dist:
            best_dist, best_idx = dist, idx
    return best_idx


# ---------------------------------------------------------------------------
# Latin Hypercube Sampling (framework-agnostic, returns list[list[float]])
# ---------------------------------------------------------------------------

def lhs_sample(n_samples: int, variables: list[dict]) -> list[list[float]]:
    """Generate ``n_samples`` Latin-Hypercube samples within variable bounds."""
    n_var = len(variables)
    intervals = [list(range(n_samples)) for _ in range(n_var)]
    for iv in intervals:
        random.shuffle(iv)

    population = []
    for i in range(n_samples):
        genes = []
        for j, var in enumerate(variables):
            lo, hi = var["lower"], var["upper"]
            stratum = intervals[j][i]
            gene = lo + (stratum + random.random()) / n_samples * (hi - lo)
            if var.get("type") == "int":
                gene = round(gene)
            genes.append(gene)
        population.append(genes)
    return population


# ---------------------------------------------------------------------------
# Progress window (subprocess GUI)
# ---------------------------------------------------------------------------

# Who shows an optimization's progress in place of the progress window: a callable given
# the progress file's path. The Aspen Workbench sets it around its optimize steps and
# draws its own bar from that file, and cancels through it. Unset, the window opens.
progress_sink: contextvars.ContextVar = contextvars.ContextVar("progress_sink", default=None)

# The reporter of the optimization running now, so that code without a handle on it (an
# acquisition function deep inside BoTorch) can still see a cancel.
_active: "ProgressReporter | None" = None


BREATHS = 3                   # event-loop passes an evaluation hands over (breathe)


async def breathe() -> None:
    """Let the event loop run what fell due while an evaluation kept it waiting, on this
    thread -- COM never leaves it. An evaluation blocks the loop (Aspen's run is a COM call);
    a single ``await asyncio.sleep(0)`` only lets the loop fire the timers that expired
    meanwhile, and the tasks they wake (the workbench's sync loop: the window's edits, Run,
    Save, refused while the optimization holds the session) would then first run after the
    next evaluation. Three passes: timers, the woken tasks, back here. Microseconds."""
    for _ in range(BREATHS):
        await asyncio.sleep(0)


def cancel_marker(state_file: str) -> str:
    """The file whose existence means "cancel": a separate file, because the optimizer
    rewrites the state file all the time and a flag written into it can be lost."""
    return state_file + ".cancel"


def cancelled_now() -> bool:
    """Cheap check for the running optimization's cancel, for hot loops."""
    rep = _active
    return rep is not None and (rep._cancelled or os.path.exists(rep._cancel_file))


def cancellable(optimize_acqf):
    """``optimize_acqf`` that stops as soon as the user cancels: the acquisition function
    raises OptimizationCancelled on its next evaluation, instead of the optimization
    carrying on until it converges, which late in a long BO run can take minutes."""
    def run(*args, acq_function, **kwargs):
        forward = acq_function.forward

        def checked(X, *a, **k):
            if cancelled_now():
                raise OptimizationCancelled("User cancelled")
            return forward(X, *a, **k)

        acq_function.forward = checked
        return optimize_acqf(*args, acq_function=acq_function, **kwargs)
    return run


class ProgressReporter:
    """Launches progress_window.py as a subprocess, communicates via JSON file.

    Works for any optimizer (NSGA-II, NSGA-III, PSO, BO, SLSQP...). The GUI shows:
      - Title "{algorithm} Progress"
      - "{iteration_label} X / Y"
      - Progress bar X / total_evals
      - Current best objective values
    """

    def __init__(
        self,
        algorithm: str,
        total_evals: int,
        n_iterations: int,
        obj_names: list[str],
        iteration_label: str = "Generation",
        mcp_ctx: "Context | None" = None,
    ):
        self._algorithm = algorithm
        self._n_iterations = n_iterations
        self._obj_names = obj_names
        self._total = total_evals
        self._iteration_label = iteration_label
        self._mcp_ctx = mcp_ctx
        # Cumulative offset for a reporter shared across sub-algorithms — preserves a
        # monotonic bar when each sub-algorithm's eval_count restarts at 0.
        self._offset = 0
        self._last_raw_count = 0
        self._cancelled = False

        fd, self._state_file = tempfile.mkstemp(suffix=".json", prefix="opt_progress_")
        os.close(fd)
        self._cancel_file = cancel_marker(self._state_file)
        global _active
        _active = self
        self._write_state(0, 0, "Starting...", None, False)

        sink = progress_sink.get()
        if sink is not None:                       # someone else shows it: no window
            self._proc = None
            try:
                sink(self._state_file)
            except Exception:
                logger.warning("progress sink failed", exc_info=True)
            return

        script = os.path.join(os.path.dirname(__file__), "progress_window.py")
        try:
            python = sys.executable
            if sys.platform == "win32":
                pythonw = Path(sys.executable).with_name("pythonw.exe")
                if pythonw.exists():
                    python = str(pythonw)
            self._proc = subprocess.Popen(
                [python, script, self._state_file],
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                               if sys.platform == "win32" else 0),
            )
        except Exception:
            logger.warning("Failed to launch progress window subprocess", exc_info=True)
            self._proc = None

    def _write_state(self, iteration, eval_count, status, best_objs, done):
        # Sync cancel flag from file first — the progress window writes
        # cancel_requested=True when the user clicks Cancel, and we must
        # not overwrite that with a stale False value.
        self.poll_cancel()
        state = {
            # Backward-compat keys (progress_window.py reads these)
            "gen": iteration,
            "n_gen": self._n_iterations,
            "eval_count": eval_count,
            "total": self._total,
            "status": status,
            "obj_names": self._obj_names,
            "best_objs": best_objs,
            "done": done,
            # New keys (ignored by older progress_window.py, used by updated one)
            "algorithm": self._algorithm,
            "iteration_label": self._iteration_label,
            "cancel_requested": self._cancelled,
        }
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception:
            logger.debug("Failed to write progress state file", exc_info=True)

    def poll_cancel(self) -> bool:
        """Read cancel flag from state file (written by progress window).

        Call this inside hot loops where ``update_sync``/``update`` aren't
        invoked every iteration — e.g. GP fitting, acquisition optimization,
        or per-particle evaluation inside a pymoo callback.
        """
        if self._cancelled:
            return True
        if os.path.exists(self._cancel_file):
            self._cancelled = True
            return True
        try:                              # the flag older progress windows write
            with open(self._state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            if state.get("cancel_requested"):
                self._cancelled = True
                return True
        except Exception:
            pass
        return False

    @property
    def cancelled(self) -> bool:
        """Cached cancel flag. Cheap — no I/O. Use ``poll_cancel()`` to refresh."""
        return self._cancelled

    def finalize(self, aborted: bool, abort_reason: str | None = None):
        """Close the progress window. Use in place of ``abort()``/``finish()``.

        If ``aborted``, shows ``abort_reason`` (defaults to "Cancelled by user"
        when the user cancelled, else "Aspen session error").
        """
        if aborted:
            if abort_reason is None:
                abort_reason = "Cancelled by user" if self._cancelled else "Aspen session error"
            self.abort(abort_reason)
        else:
            self.finish()

    async def update(
        self,
        iteration: int,
        eval_count: int,
        status: str,
        best_objs: list[float] | None = None,
    ):
        """Update both the GUI window and the MCP context (if provided), and let the event
        loop run (``breathe``) -- also when the client asked for no progress, where
        ``report_progress`` returns without ever giving the loop a turn."""
        display_count = self._apply_offset(eval_count)
        self._write_state(iteration, display_count, status, best_objs, False)
        if self._mcp_ctx is not None:
            try:
                await self._mcp_ctx.report_progress(display_count, self._total)
            except Exception:
                logger.debug("MCP ctx.report_progress failed", exc_info=True)
        await breathe()
        if self.poll_cancel():
            raise OptimizationCancelled("User cancelled from progress window")

    def update_sync(
        self,
        iteration: int,
        eval_count: int,
        status: str,
        best_objs: list[float] | None = None,
    ):
        """Sync variant for use inside non-async callbacks (pymoo/scipy)."""
        display_count = self._apply_offset(eval_count)
        self._write_state(iteration, display_count, status, best_objs, False)
        if self.poll_cancel():
            raise OptimizationCancelled("User cancelled from progress window")

    def _apply_offset(self, raw_count: int) -> int:
        """Track the raw count per phase; return monotonic cumulative count.
        Grows ``_total`` if our real progress exceeds the estimate (e.g. SLSQP
        does more evals than maxiter*(1+n_var) due to line search)."""
        self._last_raw_count = raw_count
        display = raw_count + self._offset
        if display > self._total:
            # Extend the bar so it doesn't sit pinned at 100%
            self._total = int(display * 1.15) + 1
        return display

    def advance_phase(self, extra_total: int | None = None):
        """A caller sharing one reporter calls this BEFORE starting a new sub-algorithm.
        Adds the last phase's raw count to the offset so the bar keeps going
        forward instead of resetting to 0 when the sub-algo's local counter
        restarts. Optionally grow total_evals (``extra_total``) so the bar
        width reflects the real budget."""
        self._offset += self._last_raw_count
        self._last_raw_count = 0
        if extra_total is not None and extra_total > 0:
            self._total = max(self._total, self._offset + extra_total)

    def set_algorithm(self, algorithm: str, iteration_label: str | None = None):
        """Rename mid-flight (when a shared reporter switches algorithm)."""
        self._algorithm = algorithm
        if iteration_label is not None:
            self._iteration_label = iteration_label

    def set_totals(self, total_evals: int | None = None,
                   n_iterations: int | None = None):
        """Update the displayed totals mid-flight (e.g. after CSV resume).

        Used by BO/CBO when the true target only becomes known once the
        resume CSV is parsed (initial estimate counted only the new evals,
        not the resumed ones)."""
        if total_evals is not None:
            self._total = total_evals
        if n_iterations is not None:
            self._n_iterations = n_iterations

    def abort(self, reason: str):
        self._write_state(0, self._total, f"Aborted: {reason}", None, True)
        self._cleanup()

    def finish(self):
        self._write_state(0, self._total, "Optimization complete!", None, True)
        self._cleanup()

    def _cleanup(self):
        try:
            if self._proc:
                self._proc.wait(timeout=10)
        except Exception:
            logger.debug("Progress window process did not exit cleanly", exc_info=True)
            if self._proc:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        global _active
        if _active is self:
            _active = None
        for path in (self._state_file, self._cancel_file):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except Exception:
                logger.debug("Could not remove progress file: %s", path)


# ---------------------------------------------------------------------------
# Generic report saving (Markdown + CSV)
# ---------------------------------------------------------------------------

def save_results_generic(
    *,
    algorithm: str,
    session_name: str,
    variables: list[dict],
    objectives: list[dict],
    constraints: list[dict] | None,
    settings: dict[str, Any],
    pareto: list[dict],           # each: {"x": [...], "f": [...]}
    weights: tuple[float, ...],
    log_lines: list[str],
    eval_log: list[tuple],        # (iteration, x, f_values, feasible, time_s)
    stats: EvalStats | None,
    output_dir: str,
) -> str:
    """Write a Markdown report + evaluations.csv. Returns run_dir path.

    ``settings`` is a dict of algorithm-specific hyperparameters (pop_size, n_gen, ...).
    """
    run_dir = os.path.join(output_dir,
                           f"opt_{safe_file_part(algorithm.lower())}_{safe_file_part(session_name)}_"
                           f"{datetime.now():%Y%m%d_%H%M%S}")
    os.makedirs(run_dir, exist_ok=True)

    var_names = unique_names([v["aspen_path"] for v in variables])
    obj_names = [obj_label(o) for o in objectives]
    obj_dirs = [o.get("direction", "minimize") for o in objectives]
    fitness_matrix = [p["f"] for p in pareto]
    comp_idx = best_compromise(fitness_matrix, weights) if pareto else -1

    md = [
        f"# Optimization Report — {algorithm} on {session_name}",
        f"\n**Date:** {datetime.now():%Y-%m-%d %H:%M:%S}",
        "\n## Settings\n",
        "| Parameter | Value |",
        "|-----------|-------|",
    ]
    for k, v in settings.items():
        md.append(f"| {k} | {v} |")

    md += ["\n### Decision Variables\n",
           "| Name | Path | Lower | Upper | Type |",
           "|------|------|-------|-------|------|"]
    for name, v in zip(var_names, variables):
        md.append(f"| {name} | `{v['aspen_path']}` | {v['lower']} | {v['upper']} | "
                  f"{v.get('type', 'float')} |")

    md += ["\n### Objectives\n",
           "| Name | Direction | Path |",
           "|------|-----------|------|"]
    for name, d, o in zip(obj_names, obj_dirs, objectives):
        p = ", ".join(o["aspen_paths"]) if "aspen_paths" in o else o["aspen_path"]
        md.append(f"| {name} | {d} | `{p}` |")

    if constraints:
        md += ["\n### Constraints\n",
               "| Path | Lower | Upper |",
               "|------|-------|-------|"]
        for c in constraints:
            c_path = ", ".join(c["aspen_paths"]) if "aspen_paths" in c else c["aspen_path"]
            c_expr = f" expr: `{c['expression']}`" if "expression" in c else ""
            md.append(f"| `{c_path}`{c_expr} | {c.get('lower', '-')} | {c.get('upper', '-')} |")

    hdr = ["#"] + var_names + [f"{n} ({d})" for n, d in zip(obj_names, obj_dirs)] + ["Best"]
    md += [f"\n## Pareto Front ({len(pareto)} solutions)\n",
           "| " + " | ".join(hdr) + " |",
           "| " + " | ".join("---" for _ in hdr) + " |"]
    for idx, p in enumerate(pareto):
        row = [str(idx + 1)]
        row += [f"{v:.4g}" for v in p["x"]]
        row += [f"{v:.4g}" for v in p["f"]]
        row += ["**>>>**" if idx == comp_idx else ""]
        md.append("| " + " | ".join(row) + " |")

    # Best-so-far progression (per-objective) — shows when each new best was found
    if eval_log:
        M = len(obj_names)
        best_vals: list[float | None] = [None] * M
        progression_rows: list[list[str]] = []
        for eval_idx, entry in enumerate(eval_log, start=1):
            it, decoded, obj_vals, feasible, t_s, _reason, _detail = unpack_eval_entry(entry)
            if not feasible or not is_feasible_values(obj_vals):
                continue
            improved_axes = []
            for j in range(M):
                v = obj_vals[j]
                d = obj_dirs[j]
                if best_vals[j] is None \
                   or (d == "maximize" and v > best_vals[j]) \
                   or (d == "minimize" and v < best_vals[j]):
                    best_vals[j] = v
                    improved_axes.append(obj_names[j])
            if improved_axes:
                row = [str(eval_idx), f"{t_s:.2f}", str(it)]
                row += [f"{v:.4g}" for v in decoded]
                row += [f"{v:.4g}" if v is not None else "-" for v in best_vals]
                row.append(", ".join(improved_axes))
                progression_rows.append(row)
        if progression_rows:
            md += ["\n## Best-so-far Progression\n",
                   "Each row marks a new best value found on at least one objective.\n",
                   "| eval | time_s | iter | " + " | ".join(var_names)
                   + " | " + " | ".join(f"best_{n}" for n in obj_names)
                   + " | improved |",
                   "| " + " | ".join("---" for _ in range(3 + len(var_names) + M + 1)) + " |"]
            for row in progression_rows:
                md.append("| " + " | ".join(row) + " |")

    md += ["\n## Iteration Log\n"] + [f"- {line}" for line in log_lines]

    if stats is not None:
        md += ["\n" + stats.format_report()]

    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    with open(os.path.join(run_dir, "evaluations.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["eval", "iter", "time_s"] + var_names + obj_names
                        + ["feasible", "reason", "error_detail"])
        for eval_idx, entry in enumerate(eval_log, start=1):
            it, decoded, obj_vals, feasible, t_s, reason, detail = unpack_eval_entry(entry)
            writer.writerow([eval_idx, it, f"{t_s:.4f}"]
                            + [f"{v:.6g}" for v in decoded]
                            + [f"{v:.6g}" for v in obj_vals]
                            + [int(feasible), reason, detail])

    # Pareto as standalone CSV for easy import
    with open(os.path.join(run_dir, "pareto.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(var_names + obj_names + ["is_best_compromise"])
        for idx, p in enumerate(pareto):
            writer.writerow([f"{v:.6g}" for v in p["x"]]
                            + [f"{v:.6g}" for v in p["f"]]
                            + [int(idx == comp_idx)])

    # Machine-readable problem config — lets a later resume reload the exact
    # variables / objectives / constraints without hand-reconstruction from the
    # report. See resolve_resume().
    try:
        with open(os.path.join(run_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({
                "algorithm": algorithm,
                "session_name": session_name,
                "variables": variables,
                "objectives": objectives,
                "constraints": constraints or [],
                "settings": settings,
            }, f, indent=2, default=str)
    except OSError:
        logger.warning("Failed to write config.json", exc_info=True)

    return run_dir
