# Bayesian methods: BO, CBO, AFM-CBO

Shared arguments, budget split and files: [common.md](common.md). Each method first evaluates `n_initial` Latin-hypercube points, then `n_iterations` proposals of `q` points each (`q` only with 2+ objectives): evaluations = `n_initial` + `n_iterations` × `q`.

| `algorithm` | 1 objective | 2+ objectives | Failed points |
|---|---|---|---|
| `bo` | scikit-optimize GP | BoTorch qLogNEHVI | Their penalty values train the objective GP |
| `cbo` | BoTorch log constrained EI | qLogNEHVI with a feasibility constraint | Left out of the objective GPs; a feasibility GP learns 0/1 over all points |
| `afmcbo` | as `cbo` | as `cbo` | Crashes split by mechanism; each bounded constraint gets a GP on its value |

With heavy penalties a `bo` GP stops modelling the objective well; `cbo` avoids that. `cbo` and `afmcbo` take random Latin-hypercube points instead of a proposal while fewer than 2 feasible points exist, and when a proposal fails; `bo` with 2+ objectives does the same when a proposal fails.

## Options

| Option | Type | Default | Methods | Purpose |
|---|---|---|---|---|
| `n_initial` | int ≥ 2 | 10 | all | Latin-hypercube points before the first proposal |
| `n_iterations` | int | 40 | all | Proposals after the initial points |
| `q` | int | 1 | all, 2+ objectives | Points per proposal |
| `acquisition` | `auto`, `EI`, `LCB`, `PI` | `auto` | `bo`, 1 objective | Acquisition function; `auto` and any other text mean `EI` |
| `min_count` | int ≥ 1 | 3 | `afmcbo` | Crashes a mechanism needs of its own to get a GP; the threshold used is max(`min_count`, 2 × variables) |

## AFM-CBO roster

- Each crash gets tags: `block:<name>:<kind>` per failing block from its message (`flash`, `dry_up`, `flooding`, `not_in_mass_balance`, ...; `unknown` when no pattern matches), `not_converged` when the run status names no block, else the reason itself (`set_fail`, `run_fail`, `com_error`, `obj_read_fail`). One crash can carry several tags.
- Backstop GP: every crash against every clean point, the same boundary `cbo` learns; present once both kinds of point exist.
- Sharpener GP: one per tag with at least the `min_count` threshold of crashes.
- Gate: with 20 or more crashes and one tag on at least 70 % of them, only the backstop is kept; the sharpeners return once that share falls below 60 %.
- 2+ objectives: the binary GPs form one condition, the product of their predictions ≥ 0.5. One objective: each binary GP is a separate constraint of the constrained EI.
- Out-of-range constraints are not crash tags: each constraint with a bound gets a regression GP on its value once 2 evaluations have read it, and its bounds apply to that GP's prediction.
- The answer lists the final GP roster and a count per tag; `report.md` lists the mechanisms in its settings.

## Resume

`resume_from` takes an earlier run folder or its `evaluations.csv`. Its rows go into the GPs without running Aspen.

- A `config.json` beside the CSV restores `variables`, `objectives` and `constraints`, so the call may leave them out (constraints are taken only when the call passes none).
- The CSV needs a column for every variable and objective name ([common.md](common.md#variables-objectives-constraints)) and `feasible`. The dry run loads it and states the rows found and the projected total; a missing column is an error.
- With `eval_budget` the resumed rows count: 1000 resumed and a budget of 1500 add 500; a budget already met is refused.
- Without it: the initial points still missing (`n_initial` − resumed, none once enough rows exist), then `n_iterations` × `q` more.
- The run writes a new folder with the resumed and the new rows; `time_s` continues from the largest resumed value.
- `afmcbo`: resumed rows carry no constraint values, so the constraint GPs learn from new evaluations only.

## Checkpoints and timing

With `output_dir`, `cbo` and `afmcbo` rewrite `opt_cbo-checkpoint_<session>_<time>/evaluations.csv` (`opt_afm-cbo-checkpoint_...`) every 50 evaluations, resumed rows counted. It has no `config.json`: resume from it with `variables` and `objectives` in the call. With 2+ objectives they also write `timing_<session>_<time>.log` (`timing_afm-cbo_...`) into `output_dir`: per iteration the training-set sizes and the seconds spent on the GPs, the acquisition and Aspen.

## Threads

Loading the BoTorch methods sets the compute threads to min(8, CPU count). `ASPEN_MCP_BO_THREADS=<n>` sets another count; an inherited `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS` or `NUMEXPR_NUM_THREADS` leaves the setting alone. Runs repeat point for point only with the same thread count. The acquisition search stops after 200 L-BFGS steps.

Not covered: memory growth of long runs with 3+ objectives (not measurable offline); speed per thread count (not benchmarked).
