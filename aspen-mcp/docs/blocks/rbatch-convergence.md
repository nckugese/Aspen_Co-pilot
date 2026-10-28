# RBatch convergence

Paths are under `\Data\Blocks\{name}\`. Integrator, flash and pressure-solver settings (Convergence form).

## Integration

| Path | Type | Purpose |
|---|---|---|
| `Input\INT_TOL` | real | Integration tolerance |
| `Input\MAXSTEP` | TIME | Largest integration step |
| `Input\INTEG_MAXIT` | int | Corrector iteration limit per step |
| `Input\CORR_METHOD` | `NEWTON`, `DIRECT` | Corrector method |
| `Input\ERR_METHOD` | `DYNAMIC`, `STATIC`, `HYBRID` | Error scaling |

## Flash

| Path | Type | Purpose |
|---|---|---|
| `Input\FLASH_TOL` | real | Flash tolerance |
| `Input\FLASH_MAXIT` | int | Flash iteration limit |

## Pressure (`CALCULATE`)

| Path | Type | Purpose |
|---|---|---|
| `Input\SOLVER` | `NEWTON`, `ROOT1N`, `ARCONS` | Solver for the computed pressure |
| `Input\MAXIT` | int | Iteration limit of that solver |
| `Input\PRES_LOWER` | PRESSURE | Smallest pressure the solver may try |
| `Input\PRES_UPPER` | PRESSURE | Largest pressure the solver may try |
