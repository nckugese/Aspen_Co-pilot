# Gradient: SLSQP (`gradient`)

scipy's SLSQP from one start point, with a finite-difference gradient: a local method. Several objectives become one, the sum of each weight × value (a maximized objective enters negated). Shared arguments: [common.md](common.md).

| Option | Type | Default | Purpose |
|---|---|---|---|
| `x0` | list | the bounds' midpoints | Start point, one value per variable |
| `obj_weights` | list | 1/M each | Weight per objective, one per objective |
| `maxiter` | int | 50 | SLSQP iterations |
| `ftol` | float | 1e-6 | Stop tolerance on the objective |
| `finite_diff_eps` | float | 1e-4 | Finite-difference step, in each variable's own unit |

- An iteration costs about variables + 1 evaluations and line searches add more, so `eval_budget` is approximate; a point already evaluated is taken from a cache, not rerun.
- An `int` variable stays at its rounded start value: the step rounds back to it.
- Each constraint bound, `aspen_path` or `aspen_paths`, becomes a scipy inequality on the value read after a converged run.
- A crashed point scores 1e10; 5 crashed points in a row stop the run (`ABORTED`).
- A point out of a constraint's range is `feasible` 0 with reason `constraint`; its objective columns hold the real values, which SLSQP keeps following. `finish="best"` picks among feasible points only.
- The answer gives SLSQP's final point, or the best feasible point seen when that one crashed or is out of range, and scipy's message on its `Convergence:` line.
- `seed` has no effect.

Not yet verified against a live Aspen run.
