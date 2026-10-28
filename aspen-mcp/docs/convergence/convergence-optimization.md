# Convergence blocks for optimizations

A block of your own for an optimization: SQP, COMPLEX or BOBYQA.

Root: `\Data\Convergence\Convergence\{id}`

1. `add_element` on `\Data\Convergence\Convergence` with `<ID>!SQP`, `!COMPLEX` or `!BOBYQA`, then write `Input\OPTID` with the optimization's ID.

SQP also takes tear rows (`insert_row` + `set_label` on `Input\SID_TOL`) and converges them with the optimization.

COMPLEX needed `MAXIT` 300 on the test problem; at the default 60 it stopped unconverged.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPTID` | ID | Optimization it solves |
| `Input\MAXIT` | int | Most iterations (SQP default 30, COMPLEX 60) |
| `Input\CONV_LEVEL` | int 0-10 | Detail of the block's messages in the history (default 4) |

## SQP

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXPASS` | int | Most flowsheet passes |
| `Input\OPT_TOL` | real | Optimality tolerance |
| `Input\CONST_ITER` | int | Extra iterations allowed while constraints are not met |
| `Input\SID_TOL\{stream}` | real | Tolerance of a tear stream solved with the optimization |
| `Input\OPT_METHOD` | `SQP`, `BIEGLER`, `SLP` | Algorithm |
| `Input\DERIVATIVE` | `FORWARD`, `CENTRAL` | Finite differences for the gradients |

## COMPLEX

| Path | Type | Purpose |
|---|---|---|
| `Input\NPOINT` | int | Points of the complex |
| `Input\RTOL` | real | Relative tolerance on the objective (default 1e-4) |
| `Input\ATOL` | real | Absolute tolerance on the objective (default 1e-4) |

## BOBYQA

| Path | Type | Purpose |
|---|---|---|
| `Input\INIT_REGION` | real | Starting radius of the trust region |
| `Input\FINAL_REGION` | real | Radius at which it stops |
| `Input\NCONDITIONS` | int | Interpolation points of the model |
| `Input\EQPENTYP` | `LINEAR`, `QUADRATIC` | Penalty form for equality constraints (`INEQPENTYP`: inequality) |

## Defaults of Aspen's optimization blocks

| Path | Type | Purpose |
|---|---|---|
| `\Data\Convergence\Conv-Options\Input\SQP_MAXIT` | int | SQP: most iterations (default 30) |
| `\Data\Convergence\Conv-Options\Input\SQP_TOL` | real | SQP: optimality tolerance (default 1e-3) |
| `\Data\Convergence\Conv-Options\Input\SQP_OPT_METH` | `SQP`, `BIEGLER`, `SLP` | SQP: algorithm |
| `\Data\Convergence\Conv-Options\Input\BOBY_MAXIT` | int | BOBYQA: most iterations |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TOT_ITER` | int | Iterations used |
| `Output\VAR_VAL\{n}` | real | Final value of varied input n |
| `Output\VAR_VAL2` | real | Final objective value |
| `Output\INIT_VAL\{n}` | real | First value of defined variable n of the objective |
| `Output\FINAL_VAL\{n}` | real | Its final value |
