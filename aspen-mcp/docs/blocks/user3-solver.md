# USER3: solver settings

Parameters | Convergence and the report switch of Parameters | Control. Paths are under `\Data\Blocks\{name}\`.

## Parameters | Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\NUMJAC` | `NO`, `PARTIAL`, `FULL` | How the sparsity pattern is found: from the model (NO) or by perturbing it, in part or in full |
| `Input\PERSIZ` | real | Step used for numerical perturbation (default 1e-6) |
| `Input\CMPJAC` | `NO`, `SPAT`, `DERIV`, `ALL` | Check the model's sparsity pattern (SPAT), its derivatives (DERIV) or both against numerical ones |
| `Input\DCATOL` | real | Absolute tolerance of that derivative check (default 1e-6) |
| `Input\DCRTOL` | real | Relative tolerance of that derivative check (default 0.01) |
| `Input\ZERTOL` | real | Values below it count as zero (default 1e-12) |
| `Input\MVZERO` | `YES`, `NO` | Move variables sitting at zero before the pattern is found |
| `Input\MVZTOL` | real | How far such variables are moved (default 0.01) |

## Parameters | Control

| Path | Type | Purpose |
|---|---|---|
| `Input\SUM` | `ALL`, `VARS`, `EQNS`, `NONE` | Which results go back to the GUI: variables, equations, both (ALL, default) or none |
