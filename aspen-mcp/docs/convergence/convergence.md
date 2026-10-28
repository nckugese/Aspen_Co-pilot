# Convergence

How Aspen solves recycle loops, design specs and optimizations, and which methods its own convergence blocks use.

Root: `\Data\Convergence\Conv-Options`

At run time Aspen tears each recycle loop and adds its own convergence blocks under `\Data\Convergence\Convergence`, named `$OLVER01`, `$OLVER02`, ...; there are none before the first run.

A convergence block you add takes over the tear streams, specs or optimization it names, and Aspen adds none for them ([convergence-blocks.md](convergence-blocks.md)).

## Default methods

| Path | Type | Purpose |
|---|---|---|
| `Input\TEAR_METHOD` | `WEGSTEIN`, `DIRECT`, `BROYDEN`, `NEWTON` | Method of Aspen's blocks for tear streams |
| `Input\SPEC_METHOD` | `SECANT`, `BROYDEN`, `NEWTON` | Method for a design spec solved on its own |
| `Input\MSPEC_METHOD` | `BROYDEN`, `NEWTON` | Method for several specs solved together (`IN-SIMUL`, `OUT-SIMUL`) |
| `Input\COMB_METHOD` | `BROYDEN`, `NEWTON` | Method for tears and specs solved together (`WITH-TEARS`) |
| `Input\OPT_METHOD` | `SQP`, `BOBYQA` | Method for an optimization |
| `Input\SPEC_LOOP` | `INSIDE`, `OUTSIDE`, `IN-SIMUL`, `OUT-SIMUL`, `WITH-TEARS` | Where design-spec loops sit against the tear loops |

`INSIDE` (default) and `OUTSIDE` give each spec a block of its own, solved within or around the tear loop.

`IN-SIMUL` and `OUT-SIMUL` solve all the specs in one block; `WITH-TEARS` puts the tears and the specs in one block.

`SPEC_LOOP` also places a spec block you add yourself.

Aspen's SQP block converges the loop's tear streams itself; with BOBYQA a tear block runs inside the optimization.

On the test loop Wegstein needed 3 iterations, Direct 14, Broyden 6 and Newton 2.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Convergence\Convergence\$OLVER01\Output\BLKSTAT` | int | 0 when the block converged |
| `\Data\Convergence\Convergence\$OLVER01\Output\TOT_ITER` | int | Iterations it used |
| `\Data\Convergence\Convergence\$OLVER01\Output\ERR_TOL2\{n}` | real | Largest error over tolerance at iteration n: the convergence history |

More: [tear streams](convergence-tear.md), [your own blocks for tears](convergence-blocks.md), [blocks for design specs](convergence-specs.md), [blocks for optimizations](convergence-optimization.md), [sequence and nesting order](convergence-sequence.md).

Not covered: Broyden and SQP tear variables of Calculator blocks (`LOWER`, `UPPER`, `SCALE`, ...) (not checked); `OPT_METHOD` `COMPLEX` as the default (did not converge).
