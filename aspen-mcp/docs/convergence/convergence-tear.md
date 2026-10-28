# Tear streams

Which streams Aspen tears and how closely a tear stream must repeat itself, for every recycle loop.

Root: `\Data\Convergence\Tear`

## Choosing tear streams

1. `insert_row` on `Input\TOL`, then `set_label` with the stream ID: one row per stream to tear.

`STATE`, `COMPS` and `TRACE` get the same row.

| Path | Type | Purpose |
|---|---|---|
| `Input\TOL\{stream}` | real | Tolerance for this tear stream |
| `Input\STATE\{stream}` | `PH`, `P`, `H`, `NONE` | State variables checked besides the flows |
| `Input\TRACE\{stream}` | real | Mole fraction below which a component is not checked |

Aspen then tears the named stream: a row for the Mixer outlet made its block tear that stream instead of the recycle, in 10 iterations against 3.

## Tolerance for every loop

| Path | Type | Purpose |
|---|---|---|
| `\Data\Convergence\Conv-Options\Input\TOL` | real | Tear tolerance of every loop (default 1e-4) |
| `\Data\Convergence\Conv-Options\Input\STATE` | `PH`, `P`, `H`, `NONE` | State variables checked besides the flows |
| `\Data\Convergence\Conv-Options\Input\TRACE` | real | Mole fraction below which a component is not checked |
| `\Data\Convergence\Conv-Options\Input\TRACEOPT` | `CUTOFF`, `GRADUAL` | How components below `TRACE` drop out of the test: at once or gradually |
| `\Data\Convergence\Conv-Options\Input\VARITERHIST` | `NO`, `YES`, `ALL` | Iteration history kept: the largest error only, accelerated variables, or all variables |

## Defaults of Aspen's tear blocks

Each method's settings have defaults here under its prefix: `WEG_` Wegstein, `DIR_` Direct, `BR_` Broyden, `NEW_` Newton, with the meaning of the block field ([convergence-blocks.md](convergence-blocks.md)). They hold for every block of that method, Aspen's or yours, unless the field is written on the block: with `WEG_MAXIT` 2 both stopped after 2 iterations, and a block with `MAXIT` 30 written converged.

| Path | Type | Purpose |
|---|---|---|
| `\Data\Convergence\Conv-Options\Input\WEG_MAXIT` | int | Wegstein: most iterations (default 30) |
| `\Data\Convergence\Conv-Options\Input\WEG_WAIT` | int | Wegstein: direct steps before the first acceleration |
| `\Data\Convergence\Conv-Options\Input\DIR_MAXIT` | int | Direct: most iterations (default 30) |
| `\Data\Convergence\Conv-Options\Input\BR_MAXIT` | int | Broyden: most iterations (default 30) |
| `\Data\Convergence\Conv-Options\Input\BR_TTOL` | real | Broyden: tolerance of a first tears-only pass (`OPT_B_TTOL` `TEAR-TOL`, as `OPT_TTOL`) |
| `\Data\Convergence\Conv-Options\Input\NEW_MAXIT` | int | Newton: most Newton steps (default 30) |
| `\Data\Convergence\Conv-Options\Input\N_TTOL` | real | Newton: the same (`OPT_N_TTOL` `TEAR-TOL`) |
