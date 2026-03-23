# GA Optimization (NSGA-II)

External multi-objective optimization using DEAP's NSGA-II algorithm. Unlike the [built-in SQP optimization](built-in.md), this tool supports multiple objectives and finds the Pareto-optimal front.

## Tool

```
optimize(session_name, variables, objectives, constraints?, pop_size?, n_gen?, crossover_prob?, mutation_prob?, output_dir?)
```

## Decision Variables

Each variable is a dict with:

| Key | Required | Description |
|-----|----------|-------------|
| `aspen_path` | Yes | Aspen tree path to the manipulated variable |
| `lower` | Yes | Lower bound |
| `upper` | Yes | Upper bound |
| `type` | No | `"int"` for integer variables (default: float) |

```json
{"aspen_path": "\\Data\\Blocks\\B1\\Input\\NSTAGE", "lower": 10, "upper": 60, "type": "int"}
```

## Objectives

Each objective is a dict. Two forms are supported:

### Single path
```json
{"aspen_path": "\\Data\\Blocks\\B1\\Output\\REB_DUTY", "direction": "minimize"}
```

### Multi-path with expression
Use `aspen_paths` (list) + optional `expression` to combine multiple values. Values are referenced as `v0, v1, v2...` in order.

```json
{
  "aspen_paths": [
    "\\Data\\Blocks\\B1\\Output\\REB_DUTY",
    "\\Data\\Blocks\\B1\\Output\\COND_DUTY"
  ],
  "expression": "abs(v0) + abs(v1)",
  "direction": "minimize"
}
```

If `expression` is omitted, values are summed (`v0 + v1 + ...`).

### Available functions in expressions

`sqrt`, `log`, `log10`, `exp`, `sin`, `cos`, `tan`, `abs`, `pow`, `max`, `min`, `floor`, `ceil`, `pi`, `e`

### Expression examples

| Purpose | Expression |
|---------|-----------|
| Ratio | `"v0 / v1"` |
| Difference | `"v0 - v1"` |
| Weighted sum | `"0.7*v0 + 0.3*v1"` |
| Efficiency | `"v0 / (v1 + v2)"` |
| Euclidean norm | `"sqrt(v0**2 + v1**2)"` |
| Logarithmic | `"log10(v0) - v1"` |

## Constraints

Optional list. Each constraint reads a value and checks bounds.

| Key | Required | Description |
|-----|----------|-------------|
| `aspen_path` | Yes | Path to read |
| `lower` | No | Minimum allowed value |
| `upper` | No | Maximum allowed value |

```json
{"aspen_path": "\\Data\\Streams\\PRODUCT\\Output\\MOLEFRAC\\MIXED\\ETHANOL", "lower": 0.995}
```

## GA Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pop_size` | 50 | Population size per generation |
| `n_gen` | 30 | Number of generations |
| `crossover_prob` | 0.8 | Crossover probability (SBX, eta=20) |
| `mutation_prob` | 0.2 | Mutation probability (polynomial, eta=20) |

## Penalty

When any of these occur, the individual receives a penalty of `1e10` (infeasible):
- `set_value` fails (invalid path)
- Simulation fails to converge
- Objective value cannot be read
- Expression evaluation fails
- Constraint violated (value outside lower/upper bounds)

Penalized individuals are marked `feasible=0` in the CSV log and excluded from best-objective tracking.

## Outputs

### Return value
Text summary with Pareto front solutions and best compromise (marked with `<<<`).

### Files (when `output_dir` is set)
Saved to `{output_dir}/opt_{session}_{timestamp}/`:

| File | Content |
|------|---------|
| `report.md` | Settings, variables, objectives, constraints, Pareto table, generation log |
| `evaluations.csv` | Every evaluation: gen, variable values, objective values, feasibility |

## Best Compromise Selection

From the Pareto front, the "best compromise" is selected by:
1. Normalize each objective to [0, 1] across the Pareto front
2. Compute ideal point (min for minimize, max for maximize objectives)
3. Select the solution with smallest Euclidean distance to the ideal point

## Progress Window

A tkinter window launches as an independent process (`progress_window.py`) during optimization, showing:
- Current generation / total
- Progress bar
- Current best objective values
- Evaluation status

Communication is via a temporary JSON file that the optimizer writes and the window polls every 500ms. The window auto-closes 2 seconds after completion. Works in both terminal and web MCP clients.

## Recommended Workflow

Always run a small test optimization first (e.g., `pop_size=5, n_gen=2`) to verify that the simulation converges and all paths are correct before launching the full optimization with production parameters.

## Full Example

```python
optimize(
    session_name="my_sim",
    variables=[
        {"aspen_path": "\\Data\\Blocks\\DC1\\Input\\NSTAGE", "lower": 10, "upper": 60, "type": "int"},
        {"aspen_path": "\\Data\\Blocks\\DC1\\Input\\FEED_STAGE\\FEED", "lower": 5, "upper": 55, "type": "int"},
        {"aspen_path": "\\Data\\Blocks\\DC1\\Input\\RR", "lower": 0.5, "upper": 5.0},
    ],
    objectives=[
        {"aspen_path": "\\Data\\Blocks\\DC1\\Output\\REB_DUTY", "direction": "minimize"},
        {
            "aspen_paths": [
                "\\Data\\Streams\\DIST\\Output\\MOLEFRAC\\MIXED\\ETHANOL",
                "\\Data\\Streams\\BOT\\Output\\MOLEFRAC\\MIXED\\WATER"
            ],
            "expression": "v0 * v1",
            "direction": "maximize"
        },
    ],
    constraints=[
        {"aspen_path": "\\Data\\Streams\\DIST\\Output\\MOLEFRAC\\MIXED\\ETHANOL", "lower": 0.99},
    ],
    pop_size=40,
    n_gen=20,
    output_dir="C:\\results"
)
```
