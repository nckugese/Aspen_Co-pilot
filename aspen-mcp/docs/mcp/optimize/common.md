# optimize: shared arguments and behaviour

Every algorithm takes the same problem definition; the method files list only their own `options`. Index: [index.md](index.md).

## Arguments

| Argument | Type | Default | Purpose |
|---|---|---|---|
| `session_name` | str | | An open session |
| `algorithm` | str | | Method key ([index.md](index.md)) |
| `variables` | list | | Decision variables (below) |
| `objectives` | list | | Objectives (below); optional for `grid` |
| `constraints` | list | None | Bounds on values read after each run (below) |
| `eval_budget` | int ≥ 2 | None | Total Aspen evaluations; the method sizes itself from it (below). None: the method's own defaults |
| `options` | dict | None | Method settings (method files). An unknown key is refused with the valid list; a top-level argument such as `seed` placed in it is refused |
| `seed` | int | None | The same seed and call propose the same points; no effect on `gradient` and `grid` |
| `max_retries` | int | 1 | Run attempts per evaluation when the run call itself raises; 1 = no retry |
| `dry_run` | bool | True | Preview the parsed problem, the size split and the settings; nothing is written to the model |
| `output_dir` | str | None | Folder for the run's files (below); None saves nothing, except `grid` |
| `resume_from` | str | None | `bo`, `cbo`, `afmcbo` only: [bayesian.md](bayesian.md#resume) |
| `finish` | `restore`, `best`, `last` | `restore` | Where the model is left (below) |

## Variables, objectives, constraints

| Key | Used in | Purpose |
|---|---|---|
| `aspen_path` | all three | One tree path: the input written (variable) or the result read (objective, constraint) |
| `lower`, `upper` | variable | Bounds; proposed values are clipped into them |
| `type` | variable | `"int"`: rounded before it is written; default float |
| `points` | variable | `grid` only: points on this axis |
| `aspen_paths` | objective, constraint | Several result paths, read as `v0`, `v1`, ... in list order |
| `expression` | objective, constraint | Formula of `v0`, `v1`, ...; without it their sum |
| `direction` | objective | `minimize` (default) or `maximize` |
| `lower`, `upper` | constraint | Allowed range; either may be left out |

A variable is written as a bare number, in the unit its field shows at that moment.

An expression may use `sqrt`, `log`, `log10`, `exp`, `sin`, `cos`, `tan`, `pow`, `floor`, `ceil`, `fabs`, `abs`, `max`, `min`, `pi`, `e` and nothing else.

Column names in the files: a variable is the last segment of its path, prefixed with the third segment (the block or stream) when two variables share it (`B1_TEMP`, `B2_TEMP`); an objective is that last segment, its `expression` text, or `LEAF+LEAF` for `aspen_paths` without one.

## Budget split

| Methods | `eval_budget` sets | Example |
|---|---|---|
| `nsga2`, `nsga3`, `de`, `gde3` | `pop_size` = min(default, budget/2), at least 4; `n_gen` = budget / `pop_size` | 1000 → 50 × 20 |
| `pso`, `mopso` | `swarm_size` and `n_iterations`, the same way | 100 → 40 × 2 |
| `bo`, `cbo`, `afmcbo` | `n_initial` = min(10, budget/4), at least 2; `n_iterations` = (budget − `n_initial`) / `q`, `q` only with 2+ objectives | 300 → 10 + 290 |
| `gradient` | `maxiter` = budget / (variables + 1), approximate | 30, 2 variables → 10 |
| `grid` | the largest `points_per_dim` whose grid fits, at least 2; axes with `points` keep theirs | 30, 2 variables → 5 |

Divisions round down. The initial population counts as the first generation, so evaluations = size × generations. A size given in `options` is kept and the rest is derived around it (`swarm_size` 10, budget 100 → 10 iterations). The preview starts with the split, e.g. `eval_budget 300 -> n_initial=10, n_iterations=290`.

## One evaluation

Each evaluation reinitializes the run first, so it never starts from the previous point's results. Its `reason` in the files:

| `reason` | When |
|---|---|
| `ok` | Ran, every value read, every constraint met |
| `set_fail` | A variable write was refused |
| `run_fail` | The run call raised on every attempt (`max_retries`) |
| `com_error` | The same with a COM error; 3 in a row stop the run (`ABORTED`) |
| `not_converged` | Aspen's run status reports errors; `error_detail` holds the failing blocks' messages |
| `obj_read_fail` | An objective or constraint field holds no number |
| `constraint` | A constraint is out of range; `error_detail` names it with its excess |

What an infeasible point scores, and what the objective columns of its row hold:

| Methods | Crash | Constraint out of range |
|---|---|---|
| `nsga2`, `nsga3`, `de`, `gde3`, `pso` | ±1e10 | the real objective values; pymoo ranks it behind feasible points by its excess |
| `mopso`, `bo`, `grid` | ±1e10 | ±1e8 × (1 + excess) |
| `cbo`, `afmcbo` | kept out of the objective GP, trains the feasibility model | the same (`cbo`); a GP on the constraint value (`afmcbo`) |
| `gradient` | 1e10 | the real objective values; a scipy inequality on the value read ([gradient.md](gradient.md)) |

## Files (`output_dir`)

One folder per run, `opt_<engine>_<session>_<YYYYmmdd_HHMMSS>`, engine `nsga-ii`, `nsga-iii`, `de`, `gde3`, `pso`, `mopso`, `bo-skopt`, `bo-qlognehvi`, `cbo-cei`, `cbo-qlognehvi`, `afm-cbo-cei`, `afm-cbo-qlognehvi`, `slsqp` or `gridsearch`:

| File | Content |
|---|---|
| `report.md` | Settings, variables, objectives, constraints, front or best point, best-so-far progression, failure statistics |
| `evaluations.csv` | One row per evaluation: `eval, iter, time_s, <variables>, <objectives>, feasible, reason, error_detail` |
| `pareto.csv` | The non-dominated points (one point for one objective), with `is_best_compromise` |
| `config.json` | Algorithm, session, variables, objectives, constraints, settings; what `resume_from` reloads |

The answer lists the Pareto front with the best compromise marked `<<<` (2+ objectives) or the best point, then the failure statistics, then a `Model state:` line. The best compromise scales each objective to 0–1 over the front and takes the point nearest the ideal corner. A cancelled or stopped run is headed `ABORTED` and still writes its files.

## Where the model is left (`finish`)

| `finish` | Model afterwards | Extra run |
|---|---|---|
| `restore` | The variables' start values and units | 1 |
| `best` | The best feasible point evaluated: best value (1 objective) or best compromise of the non-dominated points (2+), resumed points included; no objectives or no feasible point: `restore`, and the line says why | 1 |
| `last` | The last evaluated point, with its results | 0 |

It applies after a cancel or an error too, once one evaluation ran; a dry run or a refused call changes nothing. The extra run goes without reinitializing first and, on errors, reinitializes and runs once more. The `Model state:` line names each variable written back, a variable that was empty before the call (not written back), a write that failed, and a reopen during the run (edits not saved before the run are gone).

## While it runs

- A progress window shows the count and the best values; Cancel or closing it stops the run (`ABORTED`) with what was evaluated. Inside a workbench program the workbench's own bar replaces it.
- A real run holds its session: the AI's other changing calls wait up to 10 s and are then refused, the workbench window's writes are refused and its programs queue; reads always pass.
- A real run first makes a restore point of the model and leaves one summary record in the change journal ([change journal](../workbench/changes.md)).
- `set_reopen_interval(N)` reopens the model file every N evaluations and writes the current point again.

Not yet verified against a live Aspen run; the speed gain of a hidden Aspen window is not measured.
