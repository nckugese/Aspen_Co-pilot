# RCSTR convergence and estimates

Paths are under `\Data\Blocks\{name}\`. Defaults solve most cases; change these when the block fails.

## Convergence | Parameters

| Path | Type | Purpose |
|---|---|---|
| `Input\ALGORITHM` | `SOLVER`, `INTEGRATOR`, `MIXED` | Solve the balances directly, integrate them in time to steady state, or integrate first and then solve |
| `Input\SOLVER` | `BROYDEN`, `NEWTON` | Method for the direct solve |
| `Input\MAXIT` | int | Iteration limit |
| `Input\TOL` | real | Convergence tolerance |
| `Input\TLOWER` | TEMPERATURE | Lowest temperature tried |
| `Input\TUPPER` | TEMPERATURE | Highest temperature tried |
| `Input\RT_MAXIT` | int | Iteration limit of the residence-time loop |
| `Input\RT_TOL` | real | Tolerance of the residence-time loop |
| `Input\MB_MAXIT` | int | Iteration limit of the mass-balance loop |

A Ziegler-Natta set ([../reactions/reactions-ziegler-natta.md](../reactions/reactions-ziegler-natta.md)) in a liquid RCSTR started from no estimate ended with `BLKSTAT` 1: the mass-balance loop ran out of its 50 iterations. `MB_MAXIT` 500 or `ALGORITHM` `INTEGRATOR` brought it to `BLKSTAT` 0.

## Convergence | Estimates

| Path | Type | Purpose |
|---|---|---|
| `Input\EST_METHOD` | `EQUILIBRIUM`, `TOTAL-COMP`, `TRACE`, `SKIP` | Where the first guess of the outlet comes from |
| `Input\TEST` | TEMPERATURE | Temperature estimate |
| `Input\MOLE_EST\{comp}` | MOLE-FLOW | Outlet flow estimate per component (component-labelled rows) |
| `Input\VOL_EST` | VOLUME | Volume estimate (`RES-TIME` sizing) |

## Convergence | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\FLASH_MAXIT` | int | Flash iteration limit |
| `Input\FLASH_TOL` | real | Flash tolerance |

## Integrator and Newton options

| Path | Type | Purpose |
|---|---|---|
| `Input\INT_TOL` | real | Integration tolerance (`INTEGRATOR`, `MIXED`) |
| `Input\MAX_NSTEP` | int | Integration step limit |
| `Input\STAB_STRAT` | `DOGLEG`, `LINE-SEARCH` | Step control of the Newton solve |
| `Input\SCALING` | `COMPONENTS`, `SUBSTREAMS` | How the unknowns are scaled |
| `Input\TRACE` | real | Flow below which a component counts as a trace |
