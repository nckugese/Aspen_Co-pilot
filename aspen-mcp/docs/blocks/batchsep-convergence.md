# BatchSep convergence

Paths are under `\Data\Blocks\{name}\`. Integrator and solver settings of the dynamic model (Convergence form, Block Options | Simulation Options).

## Main

| Path | Type | Purpose |
|---|---|---|
| `Input\INTEG_METHOD` | `IMPLICIT`, `GEAR` | Integrator |
| `Input\RELTOLINTEG` | real | Relative integration tolerance |
| `Input\ABSTOLINTEG` | real | Absolute integration tolerance |
| `Input\MAXVARSIZE` | real | Largest integration step |
| `Input\MINVARSIZE` | real | Smallest integration step |
| `Input\COM_INTERVAL` | TIME | Interval between reported time points |
| `Input\NLA_ITER` | int | Iteration limit of the nonlinear solver per step |

## Advanced

| Path | Type | Purpose |
|---|---|---|
| `Input\INITABSTOL` | real | Absolute tolerance of the initialization |
| `Input\INITRELTOL` | real | Relative tolerance of the initialization |
| `Input\PROPERTYMODE` | `MIXED`, `LOCAL`, `RIGOROUS` | Property evaluation: local models, rigorous, or mixed |

## Simulation options

| Path | Type | Purpose |
|---|---|---|
| `Input\AE_METHOD` | `DSPARSE`, `SPARSE` | Linear-algebra solver of the equation set |
