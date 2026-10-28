# Grid sweep (`grid`)

Evaluates every point of a regular grid and records each one's feasibility and failure reason: a map of where the model works, not an optimizer. `objectives` may be left out for a feasibility map only. Shared arguments: [common.md](common.md).

| Option | Type | Default | Purpose |
|---|---|---|---|
| `points_per_dim` | int | 10 | Points per axis, both bounds included |
| `max_points` | int | 20000 | A larger grid is refused; raise it to run anyway |

- A variable's `points` key sets its own axis; 1 point is the midpoint.
- `int` axes are rounded and repeats dropped: 1–5 with 3 points gives 1, 3, 5.
- The grid is every combination of the axes; the last variable changes fastest. The preview shows each axis and the total.
- The files are always written; without `output_dir` into the server's working directory. `pareto.csv` stays empty.
- The answer counts feasible and infeasible points and breaks the failures down by `reason`.
- `seed` is ignored.

Not yet verified against a live Aspen run.
