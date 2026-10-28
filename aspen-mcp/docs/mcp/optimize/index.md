# optimize tool

`optimize` drives a live session as a black box with one external algorithm: it writes the decision variables, runs Aspen, reads the results and repeats. Aspen's own optimizer, an object inside the flowsheet, is documented separately: [analysis/optimization.md](../../analysis/optimization.md).

```
optimize(session_name, algorithm, variables, objectives, constraints=None, eval_budget=None,
         options=None, seed=None, max_retries=1, dry_run=True, output_dir=None,
         resume_from=None, finish="restore")
```

`dry_run=True` (the default) only previews; call again with `dry_run=False` to run. Arguments, files and where the model is left: [common.md](common.md).

## Methods

| `algorithm` | Method | Objectives | Engine | Doc |
|---|---|---|---|---|
| `nsga2` | NSGA-II | 1+ | pymoo | [population.md](population.md#nsga-ii-nsga2) |
| `nsga3` | NSGA-III | 2+, meant for 3+ | pymoo | [population.md](population.md#nsga-iii-nsga3) |
| `de` | DE for 1 objective, GDE3 for 2+ | 1+ | pymoo | [population.md](population.md#de--gde3-de-gde3) |
| `gde3` | GDE3 | 2+ | pymoo | [population.md](population.md#de--gde3-de-gde3) |
| `pso` | PSO for 1 objective, MOPSO for 2+ | 1+ | pymoo, MOPSO the server's own | [population.md](population.md#pso--mopso-pso-mopso) |
| `mopso` | MOPSO | 2+ | the server's own | [population.md](population.md#pso--mopso-pso-mopso) |
| `bo` | Bayesian optimization, failed points penalized | 1+ | scikit-optimize (1), BoTorch (2+) | [bayesian.md](bayesian.md) |
| `cbo` | Bayesian optimization with a feasibility GP | 1+ | BoTorch | [bayesian.md](bayesian.md) |
| `afmcbo` | `cbo` with one feasibility GP per crash mechanism and one GP per constraint | 1+ | BoTorch | [bayesian.md](bayesian.md#afm-cbo-roster) |
| `gradient` | SLSQP from one start point | 1+, as a weighted sum | scipy | [gradient.md](gradient.md) |
| `grid` | Full sweep that maps feasibility; finds no optimum | 0+ | none | [grid.md](grid.md) |

Keys ignore case, `-`, `_` and spaces; `nsgaii`, `nsgaiii`, `gridsearch` and `slsqp` are aliases.

## Which one

- Expensive runs that rarely crash: `bo`.
- Optimum near a crash boundary, or many runs crash: `cbo`; crashes of several kinds (different blocks or messages): `afmcbo`.
- 1–2 objectives and a generous budget: `nsga2`; 3+ objectives: `nsga3`.
- Rugged or noisy response: `de` or `pso`.
- Smooth response and a good start point: `gradient`.
- Where the model fails, over 2–3 variables: `grid`.

## Dependencies

Extra `aspen-mcp[opt]` (pymoo, scikit-optimize, scipy) covers `nsga2`, `nsga3`, `de`, `gde3`, `pso`, `mopso`, `bo` with one objective and `gradient`; `aspen-mcp[bo]` (BoTorch, pulls torch) covers `bo` with 2+ objectives, `cbo` and `afmcbo`; `aspen-mcp[all]` both. A missing package ends the call with an error naming the `pip install`.

Not covered: run times and memory of long runs (not measurable offline).
