# Tear stream estimates

Inputs on a stream inside a recycle loop are a first guess for the solver, not a fixed feed.

Write the guess as a feed's inputs ([streams.md](streams.md)): temperature, pressure and component flows.

The run ends at the same state with or without a guess, and the guess stays in `Input`.

Aspen tears a loop stream that has inputs: with inputs on the Mixer outlet it tore that stream, not the recycle.

A guess does not always save iterations: this loop took 3 without one and 7 with it.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Convergence\Convergence\$OLVER01\Output\STRMID\1` | ID | Stream the loop's convergence block tore |
| `\Data\Convergence\Convergence\$OLVER01\Output\TOT_ITER` | int | Iterations the loop took |
