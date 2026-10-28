# Granulator: convergence

Solver settings of the growth models. Paths are under `\Data\Blocks\{name}\`; basics in [granulator.md](granulator.md).

Only the set of the chosen method reaches the run: `MAXIT` and `AREA_TOL` with `GRANULATION`; `TOL`, `INIT_STEP`, `MAX_NSTEP` and `LITSTER_Q` with `AGGLOMERATIO`.

Keep `LITSTER_Q` at or below the default 4: 5 and 6 made the agglomeration solver fail, 3 ran.

## Granulation

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Iteration limit (default 10000) |
| `Input\AREA_TOL` | AREA | Tolerance on the bed particle area (default 1e-9 sqm) |

## Agglomeration

| Path | Type | Purpose |
|---|---|---|
| `Input\TOL` | real | Solver tolerance (default 1e-4) |
| `Input\INIT_STEP` | TIME | First solver step |
| `Input\MAX_NSTEP` | int | Solver step limit (default 1000) |
| `Input\LITSTER_Q` | int | Size-grid coefficient of the population balance (default 4) |
