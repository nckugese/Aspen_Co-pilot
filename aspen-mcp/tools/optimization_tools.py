"""NSGA-II multi-objective optimization for Aspen Plus simulations."""

from __future__ import annotations

import csv
import json
import logging
import math
import os
import random
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING

from deap import base, creator, tools

from tools import main_tools

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context

PENALTY = 1e10


# ---------------------------------------------------------------------------
# Progress window (launched as separate process)
# ---------------------------------------------------------------------------

class _ProgressWindow:
    """Launches progress_window.py as a subprocess, communicates via JSON file."""

    def __init__(self, total: int, n_gen: int, obj_names: list[str]):
        self._n_gen = n_gen
        self._obj_names = obj_names
        self._total = total

        # Create temp file for state exchange
        fd, self._state_file = tempfile.mkstemp(suffix=".json", prefix="opt_progress_")
        os.close(fd)

        # Write initial state
        self._write_state(0, 0, "Starting...", None, False)

        # Launch the window as an independent GUI process
        script = os.path.join(os.path.dirname(__file__), "progress_window.py")
        try:
            # Use pythonw.exe on Windows for GUI-only process (no console)
            python = sys.executable
            if sys.platform == "win32":
                pythonw = python.replace("python.exe", "pythonw.exe")
                if os.path.exists(pythonw):
                    python = pythonw
            self._proc = subprocess.Popen(
                [python, script, self._state_file],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
        except Exception:
            logger.warning("Failed to launch progress window subprocess", exc_info=True)
            self._proc = None

    def _write_state(self, gen, eval_count, status, best_objs, done):
        state = {
            "gen": gen, "n_gen": self._n_gen,
            "eval_count": eval_count, "total": self._total,
            "status": status, "obj_names": self._obj_names,
            "best_objs": best_objs, "done": done,
        }
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception:
            logger.debug("Failed to write progress state file", exc_info=True)

    def update(self, gen: int, eval_count: int, status: str,
               best_objs: list[float] | None = None):
        self._write_state(gen, eval_count, status, best_objs, False)

    def finish(self):
        self._write_state(0, self._total, "Optimization complete!", None, True)
        # Cleanup temp file after window closes
        try:
            if self._proc:
                self._proc.wait(timeout=5)
        except Exception:
            logger.debug("Progress window process did not exit cleanly", exc_info=True)
        try:
            os.remove(self._state_file)
        except Exception:
            logger.debug("Could not remove progress state file: %s", self._state_file)


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

def _short_name(path: str) -> str:
    parts = path.replace("\\\\", "\\").strip("\\").split("\\")
    return parts[-1] if parts else path


def _unique_names(paths: list[str]) -> list[str]:
    short = [_short_name(p) for p in paths]
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


def _obj_label(obj: dict) -> str:
    if "aspen_paths" in obj:
        expr = obj.get("expression")
        if expr:
            return expr
        return "+".join(_short_name(p) for p in obj["aspen_paths"])
    return _short_name(obj["aspen_path"])


# ---------------------------------------------------------------------------
# Decode / evaluate
# ---------------------------------------------------------------------------

def _decode(individual, variables: list[dict]) -> list[float]:
    decoded = []
    for gene, var in zip(individual, variables):
        v = max(var["lower"], min(var["upper"], gene))
        if var.get("type") == "int":
            v = round(v)
        decoded.append(v)
    return decoded


def _read_value(manager, session_name: str, path: str):
    raw = manager.get_node_value(session_name, path)
    try:
        return float(raw.split("(")[0].strip())
    except (ValueError, TypeError):
        return None


# Safe namespace for expression evaluation (math functions only)
_EXPR_NAMESPACE = {k: getattr(math, k) for k in
                   ("sqrt", "log", "log10", "exp", "sin", "cos", "tan",
                    "pow", "pi", "e", "floor", "ceil", "fabs")}
_EXPR_NAMESPACE["__builtins__"] = {}
_EXPR_NAMESPACE["abs"] = abs
_EXPR_NAMESPACE["max"] = max
_EXPR_NAMESPACE["min"] = min


def _read_objective(manager, session_name: str, obj: dict):
    if "aspen_paths" in obj:
        values = []
        for p in obj["aspen_paths"]:
            v = _read_value(manager, session_name, p)
            if v is None:
                return None
            values.append(v)
        expr = obj.get("expression")
        if expr:
            # Build v0, v1, v2... variables for the expression
            ns = dict(_EXPR_NAMESPACE)
            for i, val in enumerate(values):
                ns[f"v{i}"] = val
            try:
                return float(eval(expr, ns))
            except Exception:
                logger.warning("Expression eval failed: '%s' with values %s", expr, values, exc_info=True)
                return None
        return sum(values)
    return _read_value(manager, session_name, obj["aspen_path"])


def _evaluate(individual, *, manager, session_name, variables, objectives,
              constraints, weights, _debug_log=None):
    penalty = tuple(PENALTY * (-w) for w in weights)
    decoded = _decode(individual, variables)

    def _dbg(msg):
        if _debug_log is not None:
            _debug_log.append(msg)

    # Set decision variables
    for val, var in zip(decoded, variables):
        set_val = int(val) if var.get("type") == "int" else val
        result = manager.set_node_value(session_name, var["aspen_path"], value=set_val)
        if not result.startswith("Set "):
            _dbg(f"SET_FAIL: {var['aspen_path']}={set_val} → {result}")
            return penalty

    # Run simulation — call Run2() directly to skip the completeness check
    # in run_simulation(), which falsely blocks after programmatic input changes.
    app = manager.get_app(session_name)
    try:
        app.Run2()
    except Exception as exc:
        logger.debug("Optimization Run2() failed: %s", exc)
        _dbg(f"RUN_FAIL: {exc}")
        return penalty

    # Check run status for errors
    try:
        status_msg = (main_tools._check_run_status(app) or "").lower()
        if any(k in status_msg for k in ("failed",)) or \
           ("error" in status_msg and "0 errors" not in status_msg):
            _dbg(f"STATUS_FAIL: {status_msg}")
            return penalty
    except Exception:
        logger.debug("Could not check run status during optimization eval", exc_info=True)

    # Read objectives
    obj_values = []
    for obj in objectives:
        v = _read_objective(manager, session_name, obj)
        if v is None:
            _dbg(f"OBJ_READ_FAIL: {obj}")
            return penalty
        obj_values.append(v)

    # Check constraints
    for con in (constraints or []):
        val = _read_value(manager, session_name, con["aspen_path"])
        if val is None:
            _dbg(f"CONSTRAINT_READ_FAIL: {con['aspen_path']}")
            return penalty
        lo, hi = con.get("lower"), con.get("upper")
        if (lo is not None and val < lo) or (hi is not None and val > hi):
            _dbg(f"CONSTRAINT_VIOLATED: {con['aspen_path']}={val}")
            return penalty

    return tuple(obj_values)


# ---------------------------------------------------------------------------
# Best compromise (normalized distance to ideal point)
# ---------------------------------------------------------------------------

def _best_compromise(pareto, weights):
    if len(pareto) <= 1:
        return 0
    n = len(weights)
    matrix = [ind.fitness.values for ind in pareto]
    mins = [min(r[i] for r in matrix) for i in range(n)]
    maxs = [max(r[i] for r in matrix) for i in range(n)]

    best_idx, best_dist = 0, float("inf")
    for idx, row in enumerate(matrix):
        dist = 0.0
        for i in range(n):
            span = maxs[i] - mins[i]
            if span == 0:
                continue
            ideal = mins[i] if weights[i] < 0 else maxs[i]
            dist += ((row[i] - ideal) / span) ** 2
        dist = math.sqrt(dist)
        if dist < best_dist:
            best_dist, best_idx = dist, idx
    return best_idx


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------

def _save_results(session_name, variables, objectives, constraints,
                  pop_size, n_gen, cx_prob, mut_prob,
                  pareto, weights, log_lines, eval_log, output_dir):
    run_dir = os.path.join(output_dir,
                           f"opt_{session_name}_{datetime.now():%Y%m%d_%H%M%S}")
    os.makedirs(run_dir, exist_ok=True)

    var_names = _unique_names([v["aspen_path"] for v in variables])
    obj_names = [_obj_label(o) for o in objectives]
    obj_dirs = [o.get("direction", "minimize") for o in objectives]
    comp_idx = _best_compromise(pareto, weights)

    # --- Markdown report ---
    md = [
        f"# Optimization Report — {session_name}",
        f"\n**Date:** {datetime.now():%Y-%m-%d %H:%M:%S}",
        "\n## Settings\n",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Population | {pop_size} |",
        f"| Generations | {n_gen} |",
        f"| Crossover | {cx_prob} |",
        f"| Mutation | {mut_prob} |",
        "\n### Decision Variables\n",
        "| Name | Path | Lower | Upper | Type |",
        "|------|------|-------|-------|------|",
    ]
    for name, v in zip(var_names, variables):
        md.append(f"| {name} | `{v['aspen_path']}` | {v['lower']} | {v['upper']} | {v.get('type', 'float')} |")

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
            md.append(f"| `{c['aspen_path']}` | {c.get('lower', '-')} | {c.get('upper', '-')} |")

    # Pareto table
    hdr = ["#"] + var_names + [f"{n} ({d})" for n, d in zip(obj_names, obj_dirs)] + ["Best"]
    md += [f"\n## Pareto Front ({len(pareto)} solutions)\n",
           "| " + " | ".join(hdr) + " |",
           "| " + " | ".join("---" for _ in hdr) + " |"]
    for idx, ind in enumerate(pareto):
        row = [str(idx + 1)]
        row += [f"{v:.4g}" for v in _decode(ind, variables)]
        row += [f"{ind.fitness.values[i]:.4g}" for i in range(len(objectives))]
        row += ["**>>>**" if idx == comp_idx else ""]
        md.append("| " + " | ".join(row) + " |")

    md += ["\n## Generation Log\n"] + [f"- {l}" for l in log_lines]

    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    # --- CSV log ---
    with open(os.path.join(run_dir, "evaluations.csv"), "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["gen"] + var_names + obj_names + ["feasible"])
        for gen_num, decoded, obj_vals, feasible in eval_log:
            writer.writerow([gen_num] + [f"{v:.6g}" for v in decoded]
                            + [f"{v:.6g}" for v in obj_vals]
                            + [int(feasible)])

    return run_dir


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
    output_dir: str | None = None,
    ctx: "Context | None" = None,
) -> str:
    """Run NSGA-II optimization. Returns formatted Pareto front and best compromise."""
    # Validate
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

    weights = tuple(1.0 if o.get("direction", "minimize").lower() == "maximize" else -1.0
                    for o in objectives)
    n_var = len(variables)
    lows = [v["lower"] for v in variables]
    highs = [v["upper"] for v in variables]

    # DEAP setup
    for name in ("_OptFitness", "_OptIndividual"):
        if hasattr(creator, name):
            delattr(creator, name)
    creator.create("_OptFitness", base.Fitness, weights=weights)
    creator.create("_OptIndividual", list, fitness=creator._OptFitness)

    tb = base.Toolbox()
    tb.register("individual", tools.initIterate, creator._OptIndividual,
                lambda: [random.uniform(lo, hi) for lo, hi in zip(lows, highs)])
    tb.register("population", tools.initRepeat, list, tb.individual)
    tb.register("mate", tools.cxSimulatedBinaryBounded, low=lows, up=highs, eta=20.0)
    tb.register("mutate", tools.mutPolynomialBounded, low=lows, up=highs,
                eta=20.0, indpb=1.0 / n_var)
    tb.register("select", tools.selNSGA2)
    debug_log = []
    tb.register("evaluate", _evaluate, manager=manager, session_name=session_name,
                variables=variables, objectives=objectives,
                constraints=constraints, weights=weights,
                _debug_log=debug_log)

    # Run
    random.seed(42)
    pop = tb.population(n=pop_size)

    total_evals = pop_size * (1 + n_gen)
    eval_count = 0
    log_lines = []
    eval_log = []
    best_objs = None
    obj_labels = [_obj_label(o) for o in objectives]
    win = _ProgressWindow(total_evals, n_gen, obj_labels)

    def _is_feasible(vals):
        return all(abs(v) < PENALTY * 0.1 for v in vals)

    def _record_and_update(gen, ind):
        nonlocal eval_count, best_objs
        decoded = _decode(ind, variables)
        vals = ind.fitness.values
        feasible = _is_feasible(vals)
        eval_log.append((gen, decoded, list(vals), feasible))
        eval_count += 1
        # Update best
        if feasible:
            if best_objs is None:
                best_objs = list(vals)
            else:
                for i, (w, v, b) in enumerate(zip(weights, vals, best_objs)):
                    if (w > 0 and v > b) or (w < 0 and v < b):
                        best_objs[i] = v

    # Initial population
    for ind in pop:
        ind.fitness.values = tb.evaluate(ind)
        _record_and_update(0, ind)
        if ctx:
            await ctx.report_progress(eval_count, total_evals)
        win.update(0, eval_count, f"Initial population ({eval_count}/{pop_size})", best_objs)
    log_lines.append(f"Gen 0: evaluated {len(pop)} individuals")

    # Evolution
    for gen in range(1, n_gen + 1):
        offspring = list(map(tb.clone, tb.select(pop, len(pop))))

        for i in range(0, len(offspring) - 1, 2):
            if random.random() < crossover_prob:
                tb.mate(offspring[i], offspring[i + 1])
                del offspring[i].fitness.values
                del offspring[i + 1].fitness.values

        for mut in offspring:
            if random.random() < mutation_prob:
                tb.mutate(mut)
                del mut.fitness.values

        invalids = [ind for ind in offspring if not ind.fitness.valid]
        for i, ind in enumerate(invalids):
            ind.fitness.values = tb.evaluate(ind)
            _record_and_update(gen, ind)
            if ctx:
                await ctx.report_progress(eval_count, total_evals)
            win.update(gen, eval_count, f"Gen {gen}: {i+1}/{len(invalids)} evaluated", best_objs)

        pop = tb.select(pop + offspring, pop_size)
        log_lines.append(f"Gen {gen}/{n_gen}: evaluated {len(invalids)} new")

    win.finish()

    # Extract Pareto front
    pareto = tools.sortNondominated(pop, len(pop), first_front_only=True)[0]
    pareto.sort(key=lambda ind: ind.fitness.values[0])

    var_names = _unique_names([v["aspen_path"] for v in variables])
    obj_dirs = [o.get("direction", "minimize")[:3] for o in objectives]
    comp_idx = _best_compromise(pareto, weights)

    # Format output
    def _fmt_ind(ind):
        d = _decode(ind, variables)
        vs = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, d))
        os_ = ", ".join(f"{n}={ind.fitness.values[i]:.4g} ({dr})"
                        for i, (n, dr) in enumerate(zip(obj_labels, obj_dirs)))
        return f"{vs} → {os_}"

    lines = [f"Optimization complete: {n_gen} generations, {pop_size} population",
             f"\nPareto Front ({len(pareto)} solutions):"]
    for idx, ind in enumerate(pareto):
        marker = " <<<" if idx == comp_idx else ""
        lines.append(f"  #{idx+1}: {_fmt_ind(ind)}{marker}")

    comp = pareto[comp_idx]
    lines.append(f"\nBest compromise: {_fmt_ind(comp)}")
    lines.append("\nGeneration log:")
    lines += [f"  {l}" for l in log_lines]

    if debug_log:
        unique_msgs = list(dict.fromkeys(debug_log[:20]))  # first 20 unique
        lines.append(f"\nDebug ({len(debug_log)} failures):")
        lines += [f"  {m}" for m in unique_msgs]

    if output_dir:
        try:
            path = _save_results(session_name, variables, objectives, constraints,
                                 pop_size, n_gen, crossover_prob, mutation_prob,
                                 pareto, weights, log_lines, eval_log, output_dir)
            lines.append(f"\nResults saved to: {path}")
        except Exception as e:
            logger.error("Failed to save optimization results: %s", e, exc_info=True)
            lines.append(f"\nWarning: failed to save results: {e}")

    return "\n".join(lines)
