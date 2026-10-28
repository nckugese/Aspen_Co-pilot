"""The single ``optimize`` MCP tool: pick an algorithm, size it, run it.

Every algorithm keeps its own module and ``run_*`` entry point, which still does all of its
own validation, preview and reporting. This module only

- resolves ``algorithm`` to one of those entry points,
- turns ``eval_budget`` into that algorithm's own size parameters (population and
  generations, initial design and iterations, ...), and
- checks ``options`` against the parameters the entry point actually takes, so a typo is
  reported instead of silently ignored, and
- decides where the model is left afterwards (``finish``): back at its start values, at
  the best feasible point, or at the last evaluated point. The entry points themselves
  always leave the last point, so callers that use them directly are unaffected.
"""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING

from tools import main_tools
from tools._common_eval import (
    best_compromise,
    _EXPR_NAMESPACE,
    confirm_run,
    eval_expression,
    eval_observer,
    load_resume_records,
    obj_label,
    resolve_resume,
)
from tools.afm_cbo_tools import run_afm_cbo
from tools.bo_tools import run_bo
from tools.cbo_tools import run_cbo
from tools.de_tools import run_de
from tools.gradient_tools import run_gradient
from tools.gridsearch_tools import run_gridsearch
from tools.nsga3_tools import run_nsga3
from tools.optimization_tools import run_optimization
from tools.pso_tools import run_pso

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)

# algorithm key -> (entry point, how eval_budget is split)
_ALGORITHMS = {
    "nsga2": (run_optimization, "population"),
    "nsga3": (run_nsga3, "population"),
    "de": (run_de, "population"),
    "gde3": (run_de, "population"),
    "pso": (run_pso, "swarm"),
    "mopso": (run_pso, "swarm"),
    "bo": (run_bo, "surrogate"),
    "cbo": (run_cbo, "surrogate"),
    "afmcbo": (run_afm_cbo, "surrogate"),
    "gradient": (run_gradient, "gradient"),
    "grid": (run_gridsearch, "grid"),
}

# Spellings people actually use, after lower-casing and dropping '-', '_' and spaces.
_ALIASES = {"nsgaii": "nsga2", "nsgaiii": "nsga3", "gridsearch": "grid", "slsqp": "gradient"}

# gde3 / mopso name the multi-objective variant explicitly; de / pso pick by objective count.
_MIN_OBJECTIVES = {"nsga3": 2, "gde3": 2, "mopso": 2}

# Passed at the top level of ``optimize``, never through ``options``.
_SHARED = {"manager", "session_name", "variables", "objectives", "constraints", "seed",
           "max_retries", "dry_run", "output_dir", "ctx", "resume_from", "finish", "report"}

# Where the model is left when the run ends (see _finish).
FINISH = ("restore", "best", "last")


def _normalize(algorithm: str) -> str:
    key = "".join(ch for ch in str(algorithm).lower() if ch not in "-_ ")
    return _ALIASES.get(key, key)


def _option_defaults(fn) -> dict:
    """Algorithm-specific parameters of an entry point, with their defaults."""
    return {name: p.default for name, p in inspect.signature(fn).parameters.items()
            if name not in _SHARED}


def _coerce(value, default):
    """JSON gives 50.0 where the entry point wants 50; the typed tools used to fix that."""
    if value is None or isinstance(default, bool):
        return value
    if isinstance(default, int) and isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(default, float) and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    return value


def _bad_expression(objectives, constraints) -> str | None:
    """An error for the first objective or constraint ``expression`` the evaluator refuses,
    checked with every v_i = 1 before any Aspen run; arithmetic errors at that point are not
    counted (a real value may avoid them)."""
    for kind, items in (("objective", objectives), ("constraint", constraints)):
        for item in items or []:
            expr = item.get("expression") if isinstance(item, dict) else None
            if not expr:
                continue
            ns = dict(_EXPR_NAMESPACE)
            ns.update({f"v{i}": 1.0 for i in range(len(item.get("aspen_paths") or [None]))})
            try:
                eval_expression(expr, ns)
            except (ValueError, SyntaxError) as exc:
                return f"Error: {kind} expression {expr!r} is not allowed: {exc}"
            except (ArithmeticError, TypeError):
                pass
    return None


def _resumed_count(resume_from: str, variables, objectives) -> int:
    """Evaluations already in a resume source; 0 if it cannot be read (the run reports why)."""
    try:
        csv_path, _ = resolve_resume(resume_from)
        return len(load_resume_records(csv_path, variables, objectives))
    except Exception:
        return 0


def _split_budget(kind: str, budget: int, opts: dict, defaults: dict,
                  variables: list[dict], n_obj: int, done: int) -> dict:
    """Size parameters that spend at most ``budget`` Aspen evaluations.

    Anything the caller set explicitly in ``options`` is kept and the rest is derived
    around it.
    """
    if kind in ("population", "swarm"):
        size_key, iter_key = (("pop_size", "n_gen") if kind == "population"
                              else ("swarm_size", "n_iterations"))
        size = opts.get(size_key)
        if size is None:
            size = min(defaults[size_key], max(4, budget // 2))
        # pymoo counts the initial population as generation 1: evaluations = size * n_gen.
        return {size_key: size, iter_key: max(1, budget // size)}

    if kind == "surrogate":
        n_initial = opts.get("n_initial")
        if n_initial is None:
            n_initial = min(defaults["n_initial"], max(2, budget // 4))
        per_iter = opts.get("q", defaults.get("q", 1)) if n_obj >= 2 else 1
        return {"n_initial": n_initial,
                "n_iterations": max(0, (budget - max(done, n_initial)) // per_iter)}

    if kind == "gradient":
        # Each SLSQP iteration costs about one point plus one finite difference per variable.
        return {"maxiter": max(1, budget // (len(variables) + 1))}

    if kind == "grid":
        fixed, free = 1, 0
        for v in variables:
            if "points" in v:
                fixed *= max(1, int(v["points"]))
            else:
                free += 1
        if free == 0:
            return {}
        p = 1
        while fixed * (p + 1) ** free <= budget:
            p += 1
        return {"points_per_dim": max(2, p)}

    return {}


# ---------------------------------------------------------------------------
# Where the model is left afterwards (finish)
# ---------------------------------------------------------------------------

class _Seen:
    """The ``eval_observer`` of one run: how many evaluations ran, and the feasible ones."""

    def __init__(self):
        self.n = 0
        self.feasible: list[tuple[list, list]] = []      # (decoded x, objective values)

    def __call__(self, x, values, feasible):
        self.n += 1
        if feasible:
            self.feasible.append((x, values))


def _num(v) -> str:
    return f"{v:.6g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


def _fmt(entries: list[dict]) -> str:
    return ", ".join(f"{e['path']} = {_num(e['value'])}" + (f" {e['unit']}" if e.get("unit") else "")
                     for e in entries)


def _read_values(app, variables) -> list[dict]:
    """[{path, value, unit}] of each variable as the model holds it now."""
    out = []
    for v in variables or []:
        path, value, unit = v.get("aspen_path"), None, None
        try:
            node = app.Tree.FindNode(path) if app is not None and path else None
            if node is not None:
                value, unit = node.Value, (node.UnitString or None)
        except Exception:
            logger.debug("optimize finish: cannot read %s", path, exc_info=True)
        out.append({"path": path, "value": value, "unit": unit})
    return out


def _write_values(manager, session_name, app, entries: list[dict]) -> list[str]:
    """Write each entry's value; its unit too when the node's unit now differs. Returns
    the entries that could not be written, with Aspen's answer."""
    failed = []
    for e in entries:
        unit = None
        if e.get("unit"):
            try:
                if app.Tree.FindNode(e["path"]).UnitString != e["unit"]:
                    unit = e["unit"]
            except Exception:
                unit = e["unit"]
        try:
            res = manager.set_node_value(session_name, e["path"], value=e["value"], unit=unit)
        except Exception as exc:
            res = f"{type(exc).__name__}: {exc}"
        if not str(res).startswith("Set "):
            failed.append(f"{e['path']} ({' '.join(str(res).split())})")
    return failed


def _dominates(a, b) -> bool:
    return all(x >= y for x, y in zip(a, b)) and any(x > y for x, y in zip(a, b))


def _best(points: list[tuple[list, list]], objectives: list[dict]):
    """The best (x, values): by direction for one objective; for several, the best
    compromise among the non-dominated points. None when there is nothing to rank."""
    w = [1.0 if str(o.get("direction", "minimize")).lower() == "maximize" else -1.0
         for o in objectives or []]
    pts = [(x, f) for x, f in points if w and len(f) == len(w)
           and all(isinstance(v, (int, float)) and v == v and abs(v) != float("inf") for v in f)]
    if not pts:
        return None
    if len(w) == 1:
        return max(pts, key=lambda p: w[0] * p[1][0])
    front: list[tuple[list, list, list]] = []
    for x, f in pts:
        s = [wi * fi for wi, fi in zip(w, f)]
        if any(_dominates(t, s) for _, _, t in front):
            continue
        front = [p for p in front if not _dominates(s, p[2])] + [(x, f, s)]
    x, f, _ = front[best_compromise([f for _, f, _ in front], tuple(w))]
    return x, f


def _reopened(manager, count0: int) -> bool:
    """Whether evaluate_x's auto-reopen fired since the manager's eval_count was count0."""
    every, count1 = getattr(manager, "reopen_every", None), getattr(manager, "eval_count", 0)
    if not every or count1 <= count0:
        return False
    first = -(-max(count0, 1) // every) * every          # first multiple of every >= count0
    return first < count1


def _finish(manager, session_name, finish, variables, objectives, start, seen, count0,
            resumed) -> tuple[str, dict]:
    """Leave the model where ``finish`` says, run it once, and say so in plain words.
    Returns the text for the result and the report dict for the workbench."""
    rep = {"finish": finish, "state": "start", "values": [], "run": "skipped", "note": ""}
    if seen.n == 0:
        rep["note"] = "No evaluation ran; the model was not changed."
        return "", rep
    app = manager.get_app(session_name)
    if app is None:
        rep.update(state="unknown", note="The Aspen session is gone; nothing was written back.")
        return f"Model state: unknown -- {rep['note']}", rep

    notes, head, why = [], "", ""
    target = None
    if finish == "best":
        best = _best(seen.feasible + resumed, objectives)
        if best is None:
            why = ("there are no objectives to rank the points by" if not objectives
                   else "no feasible point was found")
        else:
            x, f = best
            target = [{"path": v["aspen_path"],
                       "value": int(round(val)) if v.get("type") == "int" else val}
                      for val, v in zip(x, variables)]
            objs = ", ".join(f"{obj_label(o)} = {_num(fv)}" for o, fv in zip(objectives, f))
            src = "" if any(x is px for px, _ in seen.feasible) else " (from resume_from)"
            head = f"set to the best feasible point{src} ({objs})"
            rep["state"] = "best"

    if finish == "last":
        rep.update(state="last", values=_read_values(app, variables))
        text = (f"Model state: left at the last evaluated point (finish='last'): "
                f"{_fmt(rep['values'])}. Not re-run: the results are that evaluation's.")
    else:
        if target is None:                                   # restore, or best fell back
            target = [e for e in start if e["value"] is not None]
            empty = [e["path"] for e in start if e["value"] is None]
            if empty:
                notes.append("Not restored (empty before the run): " + ", ".join(empty) + ".")
            head = "restored to the start values" + (f" (finish='best', but {why})" if why else "")
        failed = _write_values(manager, session_name, app, target)
        rep["values"] = _read_values(app, [{"aspen_path": e["path"]} for e in target])
        if failed:
            rep["state"], head = "unknown", "partly " + head
            notes.append("Could not write back: " + "; ".join(failed) + ".")
        if len(failed) < len(target):
            rep["run"], detail = confirm_run(app, manager, session_name)
            run_txt = {"ok": "Re-run: converged.",
                       "warn": f"Re-run: completed with warnings ({detail}).",
                       "error": f"Re-run: failed ({detail}); the inputs are set but the "
                                f"results do not match them.",
                       "unknown": f"Re-run: finished, but its run status could not be read ({detail}), "
                                  f"so whether it converged is not known.",
                       "refused": f"Not re-run ({detail}); the inputs are set but the results do not "
                                  f"match them."}[rep["run"]]
        else:
            run_txt = "Not re-run: nothing was written."
        text = f"Model state: {head}: {_fmt(rep['values']) or 'no variables'}. {run_txt}"
    if _reopened(manager, count0):
        notes.append("Aspen was reopened from its file during the run (set_reopen_interval), "
                     "so edits not saved before the run are not in the model.")
    rep["note"] = " ".join(notes)
    return (text + (" " + rep["note"] if rep["note"] else "")), rep


async def run_optimize(
    manager,
    session_name: str,
    algorithm: str,
    variables: list[dict] | None = None,
    objectives: list[dict] | None = None,
    constraints: list[dict] | None = None,
    eval_budget: int | None = None,
    options: dict | None = None,
    seed: int | None = None,
    max_retries: int = 1,
    dry_run: bool = True,
    output_dir: str | None = None,
    resume_from: str | None = None,
    ctx: "Context | None" = None,
    finish: str | None = "restore",
    report: dict | None = None,
) -> str:
    """Entry point for the ``optimize`` MCP tool.

    ``finish`` says where the model is left once at least one evaluation ran, also after a
    cancel or an error: ``restore`` (default; None means the same) writes the start values
    back, ``best`` the best feasible point, then both run once; ``last`` leaves the last
    evaluated point. A line "Model state: ..." is appended to the result, and ``report``
    (a dict) is filled with ``finish``, ``state`` (start | best | last | unknown),
    ``values`` ([{path, value, unit}]), ``run`` (ok | warn | error | unknown | refused |
    skipped) and ``note``, and for the journal ``algorithm``, ``evaluations``, ``feasible``
    and ``start`` (the values before the run, as ``values``).
    """
    key = _normalize(algorithm)
    if key not in _ALGORITHMS:
        return (f"Error: unknown algorithm '{algorithm}'. "
                f"Valid: {', '.join(_ALGORITHMS)}.")
    finish = str(finish or "restore").strip().lower()
    if finish not in FINISH:
        return f"Error: unknown finish '{finish}'. Valid: {', '.join(FINISH)}."
    fn, kind = _ALGORITHMS[key]
    defaults = _option_defaults(fn)

    options = dict(options or {})
    misplaced = sorted(k for k in options if k in _SHARED)
    if misplaced:
        return (f"Error: pass {', '.join(misplaced)} as a top-level argument of optimize, "
                f"not inside options.")
    unknown = sorted(k for k in options if k not in defaults)
    if unknown:
        return (f"Error: unknown option(s) for '{key}': {', '.join(unknown)}. "
                f"Valid: {', '.join(defaults) or 'none'}.")
    opts = {k: _coerce(v, defaults[k]) for k, v in options.items()}

    if resume_from and kind != "surrogate":
        return "Error: resume_from is only supported by bo, cbo and afmcbo."
    if resume_from and (not variables or not objectives):
        # The entry point does this too; the budget split below needs the problem first.
        _, cfg = resolve_resume(resume_from)
        if cfg:
            variables = variables or cfg.get("variables")
            objectives = objectives or cfg.get("objectives")
            if constraints is None:
                constraints = cfg.get("constraints") or None

    n_obj = len(objectives or [])
    need = _MIN_OBJECTIVES.get(key)
    if need and objectives and n_obj < need:
        single = {"nsga3": "'nsga2' or 'bo'", "gde3": "'de'", "mopso": "'pso'"}[key]
        return f"Error: {key} needs {need}+ objectives. Use {single} for a single objective."

    bad = _bad_expression(objectives, constraints)
    if bad:
        return bad

    budget_note = ""
    if eval_budget is not None:
        if int(eval_budget) < 2:
            return "Error: eval_budget must be at least 2."
        eval_budget = int(eval_budget)
        if variables:
            done = (_resumed_count(resume_from, variables, objectives)
                    if kind == "surrogate" and resume_from else 0)
            if done >= eval_budget:
                return (f"Error: resume_from already holds {done} evaluations, which meets "
                        f"eval_budget={eval_budget}. Raise eval_budget to continue.")
            sized = _split_budget(kind, eval_budget, opts, defaults, variables, n_obj, done)
            opts = {**sized, **opts}
            budget_note = (f"eval_budget {eval_budget} -> "
                           + ", ".join(f"{k}={opts[k]}" for k in sized))
            if done:
                budget_note += f" (after {done} resumed evaluations)"

    kwargs = dict(session_name=session_name, variables=variables, objectives=objectives,
                  constraints=constraints, max_retries=max_retries, dry_run=dry_run,
                  output_dir=output_dir, ctx=ctx)
    params = inspect.signature(fn).parameters
    if "seed" in params:
        kwargs["seed"] = seed
    if "resume_from" in params:
        kwargs["resume_from"] = resume_from
    kwargs.update(opts)

    logger.info("optimize: algorithm=%s %s finish=%s", key, budget_note, finish)
    if dry_run:
        if report is not None:
            report.clear()
            report.update(finish=finish, state="start", values=[], run="skipped",
                          note="Dry run; the model was not changed.", algorithm=key)
        result = await fn(manager, **kwargs)
        if budget_note and not result.startswith("Error"):
            result = f"{budget_note}\n\n{result}"
        return result

    refused = main_tools.fault_refusal(manager, session_name)     # its runs would never return
    if refused:
        return f"Error: {refused}"          # "Error": the journal and a program see it as failed
    start = _read_values(manager.get_app(session_name), variables)
    seen, count0 = _Seen(), getattr(manager, "eval_count", 0)
    text = ""
    token = eval_observer.set(seen)
    try:
        result = await fn(manager, **kwargs)
    finally:                         # a cancel or an error still puts the model back
        eval_observer.reset(token)
        resumed = []
        if finish == "best" and resume_from and seen.n:
            try:
                resumed = [(r["x"], r["f_vals"]) for r in
                           load_resume_records(resolve_resume(resume_from)[0], variables, objectives)
                           if r["feasible"]]
            except Exception:
                logger.debug("optimize finish: resume records unreadable", exc_info=True)
        try:
            text, rep = _finish(manager, session_name, finish, variables or [], objectives or [],
                                start, seen, count0, resumed)
        except Exception as exc:
            logger.warning("optimize finish failed", exc_info=True)
            rep = {"finish": finish, "state": "unknown", "values": [], "run": "skipped",
                   "note": f"Leaving the model at finish='{finish}' failed: {exc}"}
            text = f"Model state: unknown -- {rep['note']}"
        if report is not None:
            report.clear()
            report.update(rep, algorithm=key, evaluations=seen.n, feasible=len(seen.feasible), start=start)
        if text:
            logger.info("optimize: %s", text)
    return f"{result}\n\n{text}" if text else result
