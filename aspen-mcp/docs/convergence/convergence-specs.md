# Convergence blocks for design specs

A block of your own for one or more design specs: Secant for one, Broyden or Newton for several, with tears if wanted.

Root: `\Data\Convergence\Convergence\{id}`

1. `add_element` on `\Data\Convergence\Convergence` with `<ID>!SECANT`, then write `Input\SPECID` with the design spec's ID.
2. Broyden or Newton: `insert_row` + `set_label` with the spec ID on `Input\SPEC`, one row per spec; `STEP_SIZE` and `MAX_STEP_SIZ` get the same row.

Tear rows (`SID_TOL`, [convergence-blocks.md](convergence-blocks.md)) in the same Broyden or Newton block are solved together with its specs; without them Aspen keeps its own tear block.

## Secant

| Path | Type | Purpose |
|---|---|---|
| `Input\SPECID` | ID | Design spec it solves |
| `Input\TOL` | real | Tolerance on the spec (default: the spec's own) |
| `Input\STEP_SIZE` | real | First step, as a fraction of the vary range (default 0.01) |
| `Input\MAX_STEP_SIZ` | real | Largest step, as a fraction of the vary range (default 1) |
| `Input\MAXIT` | int | Most iterations (default 30) |
| `Input\XTOL` | real | Tolerance on the change of the varied input (default 1e-8) |
| `Input\BRACKET` | `NO`, `YES`, `CHKBNDS` | Bracket the solution between the vary limits |
| `Input\XFINAL` | `XLAST`, `XINIT`, `FMIN`, `LB`, `UB` | Value the varied input keeps when the spec fails: last, initial, best, lower or upper limit |

## Broyden and Newton

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC\{spec}` | real | Tolerance on this spec, in place of the spec's own |
| `Input\STEP_SIZE\{spec}` | real | First step for this spec, as a fraction of its vary range |
| `Input\MAX_STEP_SIZ\{spec}` | real | Largest step for this spec |

With specs and tears in one block (Broyden, Newton):

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_TTOL` | `NO`, `TEAR-TOL`, `TOL-RATIO` | First converge the tears alone, to `TEAR_TOL` or to `TEAR_RATIO` times their tolerance |
| `Input\TEAR_TOL` | real | Tolerance of that first pass (`TEAR-TOL`) |
| `Input\TEAR_RATIO` | real | Its tolerance as a multiple of the tear tolerance (`TOL-RATIO`) |
| `Input\TEAR_MAXIT` | int | Most iterations of that first pass |

`OPT_TTOL` other than `NO` is refused on a block that does not hold both a spec and a tear.

Other fields as for tears: [convergence-blocks.md](convergence-blocks.md).

## Defaults of Aspen's Secant blocks

| Path | Type | Purpose |
|---|---|---|
| `\Data\Convergence\Conv-Options\Input\SEC_MAXIT` | int | Most iterations (default 30) |
| `\Data\Convergence\Conv-Options\Input\SEC_XTOL` | real | Tolerance on the change of the varied input |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TOT_ITER` | int | Iterations used |
| `Output\VAR_DSPDS\{n}` | string | Input it varies (`block.sentence.variable`) |
| `Output\VAR_VALDS\{n}` | real | Final value of that input |
| `Output\ERR_TOLDS\{n}` | real | Final spec error over tolerance |
