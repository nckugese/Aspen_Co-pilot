# Convergence blocks for tear streams

A block of your own for chosen tear streams, with its method and settings.

Root: `\Data\Convergence\Convergence\{id}`

1. `add_element` on `\Data\Convergence\Convergence` with `<ID>!<METHOD>`: `WEGSTEIN`, `DIRECT`, `BROYDEN` or `NEWTON`.
2. `insert_row` + `set_label` with the stream ID on `Input\TOL` (Wegstein, Direct) or `Input\SID_TOL` (Broyden, Newton), one row per tear stream.

A stream can be on the tear list of one convergence block only; a second block refuses it. The same holds for a design spec and an optimization.

A tear stream must run between two blocks: a feed or product stream is refused.

`STATE`, `COMPS` and `TRACE` get the same row.

## Tear streams

| Path | Type | Purpose |
|---|---|---|
| `Input\TOL\{stream}` | real | Wegstein, Direct: tolerance for this stream |
| `Input\SID_TOL\{stream}` | real | Broyden, Newton: tolerance for this stream |
| `Input\STATE\{stream}` | `PH`, `P`, `H`, `NONE` | State variables checked besides the flows |
| `Input\TRACE\{stream}` | real | Mole fraction below which a component is not checked |

## Parameters

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Most iterations (default 30; Newton: Newton steps) |
| `Input\WAIT` | int | Wegstein, Broyden, Newton: direct steps before the first acceleration |
| `Input\QMIN` | real | Wegstein, Broyden: lower bound of the acceleration factor (default -5) |
| `Input\QMAX` | real | Wegstein, Broyden: upper bound of the acceleration factor (default 0) |
| `Input\ACCELERATE` | int | Wegstein: direct steps between accelerations (default 0) |
| `Input\NACCELERATE` | int | Wegstein: accelerated steps in a row (default 1) |
| `Input\RESTART` | `NO`, `YES` | Start from the result of the previous run |
| `Input\XTOL` | real | Broyden, Newton: tolerance on the change of the variables |
| `Input\MAXPASS` | int | Newton: most flowsheet passes |
| `Input\OPT_JAC` | `RED-FACTOR`, `REUSE-ITNS` | Newton: rebuild the Jacobian when the error falls by less than `RED_FACTOR`, or every `REINIT` steps |
| `Input\RED_FACTOR` | real | Newton: error reduction a step must reach to keep the Jacobian (default 0.2) |
| `Input\REINIT` | int | Newton: steps a Jacobian is kept (`REUSE-ITNS`) |

## Diagnostics

| Path | Type | Purpose |
|---|---|---|
| `Input\CONV_LEVEL` | int 0-10 | Detail of the block's messages in the history (default 4) |
| `Input\VARITERHIST` | `NO`, `YES` | Keep the history of every tear variable |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BLKSTAT` | int | 0 when converged |
| `Output\TOT_ITER` | int | Iterations used |
| `Output\ERR_TOL2\{n}` | real | Largest error over tolerance at iteration n |
| `Output\VARID2\{n}` | string | Variable that had it |
| `Output\STRMID\{n}` | ID | Tear stream of tear variable n |
| `Output\VARID\{n}` | string | Tear variable n: total flow, a component flow, pressure, enthalpy |
| `Output\VAR_VAL\{n}` | real | Its final value |
| `Output\ERR_TOL\{n}` | real | Its final error over tolerance (below 1 when converged) |
