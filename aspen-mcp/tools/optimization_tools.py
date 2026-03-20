"""NSGA-II multi-objective optimization for Aspen Plus simulations.

Uses DEAP to find Pareto-optimal solutions by iteratively setting
decision variables, running the simulation, and reading objective values.
"""

from __future__ import annotations

import random
import math
import os
from datetime import datetime
from typing import TYPE_CHECKING

from deap import base, creator, tools, algorithms

from tools import main_tools

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_weights(objectives: list[dict]) -> tuple[float, ...]:
    """Convert objective directions to DEAP fitness weights."""
    w = []
    for obj in objectives:
        d = obj.get("direction", "minimize").lower()
        w.append(1.0 if d == "maximize" else -1.0)
    return tuple(w)


def _clip(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _short_name(aspen_path: str) -> str:
    """Extract readable name from an Aspen path."""
    parts = aspen_path.replace("\\\\", "\\").strip("\\").split("\\")
    return parts[-1] if parts else aspen_path


def _unique_names(paths: list[str]) -> list[str]:
    """Generate unique short names, adding parent context for duplicates."""
    short = [_short_name(p) for p in paths]
    # Find duplicates
    from collections import Counter
    counts = Counter(short)
    if max(counts.values()) <= 1:
        return short

    # For duplicates, prepend block/stream name (3rd path segment)
    result = []
    for i, (s, p) in enumerate(zip(short, paths)):
        if counts[s] > 1:
            parts = p.replace("\\\\", "\\").strip("\\").split("\\")
            # Try to find a block/stream name (usually parts[2])
            prefix = parts[2] if len(parts) > 2 else str(i)
            result.append(f"{prefix}_{s}")
        else:
            result.append(s)
    return result


def _decode(individual, variables: list[dict]) -> list[float]:
    """Decode an individual, rounding integer variables and clipping to bounds."""
    decoded = []
    for gene, var in zip(individual, variables):
        lo, hi = var["lower"], var["upper"]
        v = _clip(gene, lo, hi)
        if var.get("type") == "int":
            v = round(v)
        decoded.append(v)
    return decoded


PENALTY = 1e10


def _read_value(manager, session_name: str, aspen_path: str):
    """Read a numeric value from an Aspen path. Returns float or None."""
    raw = manager.get_node_value(session_name, aspen_path)
    try:
        num_str = raw.split("(")[0].strip()
        return float(num_str)
    except (ValueError, TypeError):
        return None


def _read_objective(manager, session_name: str, obj: dict):
    """Read an objective value. Supports single path or sum of multiple paths.

    - {"aspen_path": "..."} → single value
    - {"aspen_paths": ["...", "..."]} → sum of values
    """
    if "aspen_paths" in obj:
        total = 0.0
        for p in obj["aspen_paths"]:
            v = _read_value(manager, session_name, p)
            if v is None:
                return None
            total += v
        return total
    else:
        return _read_value(manager, session_name, obj["aspen_path"])


def _obj_label(obj: dict) -> str:
    """Generate a display label for an objective."""
    if "aspen_paths" in obj:
        names = [_short_name(p) for p in obj["aspen_paths"]]
        return "+".join(names)
    return _short_name(obj["aspen_path"])


def _evaluate(individual, manager, session_name: str,
              variables: list[dict], objectives: list[dict],
              constraints: list[dict] | None,
              weights: tuple[float, ...]):
    """Evaluate one individual: set vars → run → read objectives."""
    decoded = _decode(individual, variables)

    # Set decision variables
    for val, var in zip(decoded, variables):
        set_val = int(val) if var.get("type") == "int" else val
        result = manager.set_node_value(session_name, var["aspen_path"], value=set_val)
        if result.startswith("Error") or result.startswith("Node not found"):
            return tuple(PENALTY * (-w) for w in weights)

    # Run simulation
    run_result = main_tools.run_simulation(manager, session_name)

    # Check convergence — if "errors" or block issues appear, penalize
    run_lower = run_result.lower()
    if ("error" in run_lower and "0 errors" not in run_lower) or \
       "cannot run" in run_lower or "failed" in run_lower:
        return tuple(PENALTY * (-w) for w in weights)

    # Read objective values
    obj_values = []
    for obj in objectives:
        v = _read_objective(manager, session_name, obj)
        if v is None:
            return tuple(PENALTY * (-w) for w in weights)
        obj_values.append(v)

    # Check constraints
    if constraints:
        for con in constraints:
            val = _read_value(manager, session_name, con["aspen_path"])
            if val is None:
                return tuple(PENALTY * (-w) for w in weights)
            lo = con.get("lower")
            hi = con.get("upper")
            if lo is not None and val < lo:
                return tuple(PENALTY * (-w) for w in weights)
            if hi is not None and val > hi:
                return tuple(PENALTY * (-w) for w in weights)

    return tuple(obj_values)


# ---------------------------------------------------------------------------
# Best compromise selection (normalized Euclidean distance to ideal)
# ---------------------------------------------------------------------------

def _best_compromise(pareto_front, weights):
    """Select the solution closest to the ideal point in normalized space."""
    if len(pareto_front) <= 1:
        return 0

    n_obj = len(weights)
    # Gather objective arrays
    obj_matrix = [ind.fitness.values for ind in pareto_front]

    # Compute min/max per objective for normalization
    mins = [min(row[i] for row in obj_matrix) for i in range(n_obj)]
    maxs = [max(row[i] for row in obj_matrix) for i in range(n_obj)]

    best_idx, best_dist = 0, float("inf")
    for idx, row in enumerate(obj_matrix):
        dist = 0.0
        for i in range(n_obj):
            span = maxs[i] - mins[i]
            if span == 0:
                continue
            # Ideal is min for minimize (w=-1), max for maximize (w=1)
            ideal = mins[i] if weights[i] < 0 else maxs[i]
            norm = (row[i] - ideal) / span
            dist += norm ** 2
        dist = math.sqrt(dist)
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


# ---------------------------------------------------------------------------
# Result saving
# ---------------------------------------------------------------------------

def _save_results(session_name: str, variables: list[dict], objectives: list[dict],
                  constraints: list[dict] | None, pop_size: int, n_gen: int,
                  crossover_prob: float, mutation_prob: float,
                  pareto, weights, log_lines: list[str],
                  eval_log: list, output_dir: str) -> str:
    """Save optimization results: Markdown report + CSV evaluation log."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(output_dir, f"opt_{session_name}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    filepath = os.path.join(run_dir, "report.md")

    comp_idx = _best_compromise(pareto, weights)
    var_names = _unique_names([v["aspen_path"] for v in variables])
    obj_names = [_obj_label(o) for o in objectives]
    obj_dirs = [o.get("direction", "minimize") for o in objectives]

    lines = [
        f"# Optimization Report — {session_name}",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Settings",
        "",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| Population | {pop_size} |",
        f"| Generations | {n_gen} |",
        f"| Crossover | {crossover_prob} |",
        f"| Mutation | {mutation_prob} |",
        "",
        "### Decision Variables",
        "",
        "| Name | Aspen Path | Lower | Upper | Type |",
        "|------|------------|-------|-------|------|",
    ]
    for name, v in zip(var_names, variables):
        vtype = v.get("type", "float")
        lines.append(f"| {name} | `{v['aspen_path']}` | {v['lower']} | {v['upper']} | {vtype} |")

    lines += ["", "### Objectives", "",
              "| Name | Direction | Aspen Path |",
              "|------|-----------|------------|"]
    for name, d, o in zip(obj_names, obj_dirs, objectives):
        path = ", ".join(o["aspen_paths"]) if "aspen_paths" in o else o["aspen_path"]
        lines.append(f"| {name} | {d} | `{path}` |")

    if constraints:
        lines += ["", "### Constraints", "",
                  "| Aspen Path | Lower | Upper |",
                  "|------------|-------|-------|"]
        for c in constraints:
            lo = c.get("lower", "-")
            hi = c.get("upper", "-")
            lines.append(f"| `{c['aspen_path']}` | {lo} | {hi} |")

    # Pareto front table
    header_cols = ["#"] + var_names + [f"{n} ({d})" for n, d in zip(obj_names, obj_dirs)] + ["Best"]
    lines += [
        "",
        f"## Pareto Front ({len(pareto)} solutions)",
        "",
        "| " + " | ".join(header_cols) + " |",
        "| " + " | ".join(["---"] * len(header_cols)) + " |",
    ]
    for idx, ind in enumerate(pareto):
        decoded = _decode(ind, variables)
        row = [str(idx + 1)]
        row += [f"{v:.4g}" for v in decoded]
        row += [f"{ind.fitness.values[i]:.4g}" for i in range(len(objectives))]
        row += ["**>>>**" if idx == comp_idx else ""]
        lines.append("| " + " | ".join(row) + " |")

    # Generation log
    lines += ["", "## Generation Log", ""]
    for l in log_lines:
        lines.append(f"- {l}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Save CSV evaluation log (every evaluation, for plotting)
    csv_path = os.path.join(run_dir, "evaluations.csv")
    csv_header = ["gen"] + var_names + obj_names + ["feasible"]
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(",".join(csv_header) + "\n")
        for gen_num, decoded, obj_vals, feasible in eval_log:
            row = [str(gen_num)]
            row += [f"{v:.6g}" for v in decoded]
            row += [f"{v:.6g}" for v in obj_vals]
            row += ["1" if feasible else "0"]
            f.write(",".join(row) + "\n")

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
    """Run NSGA-II multi-objective optimization on an Aspen Plus simulation.

    Returns a formatted string with the Pareto front and best compromise.
    """
    # Validate inputs
    if not variables:
        return "Error: at least one decision variable is required."
    if not objectives:
        return "Error: at least one objective is required."

    for v in variables:
        if "aspen_path" not in v or "lower" not in v or "upper" not in v:
            return "Error: each variable needs 'aspen_path', 'lower', and 'upper'."
    for o in objectives:
        if "aspen_path" not in o and "aspen_paths" not in o:
            return "Error: each objective needs 'aspen_path' or 'aspen_paths'."

    weights = _parse_weights(objectives)
    n_var = len(variables)

    # --- DEAP setup (use unique names to avoid creator conflicts) ----------
    fit_name = "FitnessMulti_Opt"
    ind_name = "Individual_Opt"
    if hasattr(creator, fit_name):
        delattr(creator, fit_name)
    if hasattr(creator, ind_name):
        delattr(creator, ind_name)

    creator.create(fit_name, base.Fitness, weights=weights)
    creator.create(ind_name, list, fitness=getattr(creator, fit_name))

    toolbox = base.Toolbox()

    # Attribute generators — one per variable
    for i, var in enumerate(variables):
        toolbox.register(f"attr_{i}", random.uniform, var["lower"], var["upper"])

    def _init_ind():
        ind = getattr(creator, ind_name)(
            getattr(toolbox, f"attr_{i}")() for i in range(n_var)
        )
        return ind

    toolbox.register("individual", _init_ind)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    # Genetic operators
    toolbox.register("mate", tools.cxSimulatedBinaryBounded,
                     low=[v["lower"] for v in variables],
                     up=[v["upper"] for v in variables],
                     eta=20.0)
    toolbox.register("mutate", tools.mutPolynomialBounded,
                     low=[v["lower"] for v in variables],
                     up=[v["upper"] for v in variables],
                     eta=20.0, indpb=1.0 / n_var)
    toolbox.register("select", tools.selNSGA2)

    toolbox.register("evaluate", _evaluate,
                     manager=manager, session_name=session_name,
                     variables=variables, objectives=objectives,
                     constraints=constraints, weights=weights)

    # --- Run NSGA-II -------------------------------------------------------
    random.seed(42)
    pop = toolbox.population(n=pop_size)

    log_lines = []
    eval_log = []  # Record every evaluation: (gen, variables..., objectives...)

    # Total evaluations estimate: initial pop + n_gen * pop_size (upper bound)
    total_evals = pop_size + n_gen * pop_size
    eval_count = 0

    def _record(gen_num, individual, fit_values):
        """Record one evaluation to eval_log."""
        decoded = _decode(individual, variables)
        feasible = all(abs(v) < PENALTY * 0.1 for v in fit_values)
        eval_log.append((gen_num, decoded, list(fit_values), feasible))

    # Evaluate initial population
    for ind in pop:
        ind.fitness.values = toolbox.evaluate(ind)
        _record(0, ind, ind.fitness.values)
        eval_count += 1
        if ctx:
            await ctx.report_progress(eval_count, total_evals)

    log_lines.append(f"Gen 0: evaluated {len(pop)} individuals")

    for gen in range(1, n_gen + 1):
        # Select and clone
        offspring = toolbox.select(pop, len(pop))
        offspring = list(map(toolbox.clone, offspring))

        # Crossover
        for i in range(0, len(offspring) - 1, 2):
            if random.random() < crossover_prob:
                toolbox.mate(offspring[i], offspring[i + 1])
                del offspring[i].fitness.values
                del offspring[i + 1].fitness.values

        # Mutation
        for mutant in offspring:
            if random.random() < mutation_prob:
                toolbox.mutate(mutant)
                del mutant.fitness.values

        # Evaluate individuals with invalid fitness
        invalids = [ind for ind in offspring if not ind.fitness.valid]
        for ind in invalids:
            ind.fitness.values = toolbox.evaluate(ind)
            _record(gen, ind, ind.fitness.values)
            eval_count += 1
            if ctx:
                await ctx.report_progress(eval_count, total_evals)

        # Survivor selection
        pop = toolbox.select(pop + offspring, pop_size)

        log_lines.append(f"Gen {gen}/{n_gen}: evaluated {len(invalids)} new")

    # --- Extract Pareto front ----------------------------------------------
    pareto = tools.sortNondominated(pop, len(pop), first_front_only=True)[0]

    # Sort pareto by first objective for consistent display
    pareto.sort(key=lambda ind: ind.fitness.values[0])

    # Build variable/objective short names
    var_names = _unique_names([v["aspen_path"] for v in variables])
    obj_names = [_obj_label(o) for o in objectives]
    obj_dirs = [o.get("direction", "minimize")[:3] for o in objectives]

    # Format output
    lines = [
        f"Optimization complete: {n_gen} generations, {pop_size} population size",
        "",
        f"Pareto Front ({len(pareto)} solutions):",
    ]

    for idx, ind in enumerate(pareto):
        decoded = _decode(ind, variables)
        var_str = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, decoded))
        obj_str = ", ".join(
            f"{n}={ind.fitness.values[i]:.4g} ({d})"
            for i, (n, d) in enumerate(zip(obj_names, obj_dirs))
        )
        lines.append(f"  #{idx + 1}: {var_str} → {obj_str}")

    # Best compromise
    comp_idx = _best_compromise(pareto, weights)
    comp = pareto[comp_idx]
    comp_decoded = _decode(comp, variables)
    lines.append("")
    lines.append("Best compromise (normalized distance):")
    var_str = ", ".join(f"{n}={v:.4g}" for n, v in zip(var_names, comp_decoded))
    obj_str = ", ".join(
        f"{n}={comp.fitness.values[i]:.4g}"
        for i, n in enumerate(obj_names)
    )
    lines.append(f"  {var_str} → {obj_str}")

    # Append generation log
    lines.append("")
    lines.append("Generation log:")
    for l in log_lines:
        lines.append(f"  {l}")

    # Auto-save results
    if output_dir:
        try:
            filepath = _save_results(
                session_name, variables, objectives, constraints,
                pop_size, n_gen, crossover_prob, mutation_prob,
                pareto, weights, log_lines, eval_log, output_dir,
            )
            lines.append("")
            lines.append(f"Results saved to: {filepath}")
        except Exception as exc:
            lines.append("")
            lines.append(f"Warning: failed to save results: {exc}")

    return "\n".join(lines)
