# Convergence & Simulation

## Pre-run Checklist

1. `check_inputs(session)` — find incomplete blocks/streams
2. `save_simulation(session)` — save before running (Aspen can crash)
3. `run_simulation(session)` — run and check results

## Tear Methods

Path: `\Data\Convergence\Conv-Options\Input\TEAR_METHOD`

| Method | Description | When to Use |
|--------|-------------|-------------|
| `WEGSTEIN` | Default acceleration method | Most cases |
| `DIRECT` | Direct substitution (no acceleration) | Simple loops |
| `BROYDEN` | Quasi-Newton with Broyden update | When Wegstein oscillates |
| `NEWTON` | Full Newton's method | Difficult convergence |

**Switch from Wegstein** when you see oscillating ERR_TOL2 values that don't converge.

### Configuration Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Convergence\Conv-Options\Input\TEAR_METHOD` | string | Tear method: `WEGSTEIN`, `DIRECT`, `BROYDEN`, `NEWTON` |
| `\Data\Convergence\Conv-Options\Input\WEG_MAXIT` | int | Max iterations for Wegstein (default 30) |
| `\Data\Convergence\Conv-Options\Input\BR_MAXIT` | int | Max iterations for Broyden (default 30) |
| `\Data\Convergence\Conv-Options\Input\DIR_MAXIT` | int | Max iterations for Direct (default 30) |
| `\Data\Convergence\Conv-Options\Input\TOL` | float | Convergence tolerance (default 0.0001) |

> **Do not confuse** `TEAR_METHOD` with `COMB_METHOD`. `COMB_METHOD` controls the **combined convergence** method (default `BROYDEN`) — it is a different setting. To change the recycle tear stream method, always use `TEAR_METHOD`.

Example — switch to Broyden with 100 iterations:
```
set_value(session, items=[
    {"path": "\\Data\\Convergence\\Conv-Options\\Input\\TEAR_METHOD", "value": "BROYDEN"},
    {"path": "\\Data\\Convergence\\Conv-Options\\Input\\BR_MAXIT", "value": "100"}
])
```

### Method Selection Guide

- **Wegstein** (default): Good for simple single recycle loops. Fast when it works, but can oscillate on complex systems.
- **Broyden**: Best first choice when Wegstein fails. Handles complex multi-loop systems well. Often converges in fewer iterations.
- **Direct**: Most robust but slowest. No acceleration — uses pure substitution. Good for very unstable systems.
- **Newton**: Full Jacobian update. Most powerful but expensive per iteration. Use as last resort.

## Diagnostics

### Simulation Status
```
get_value(session, aspen_path='\Data\Results Summary\Run-Status\Output\PER_ERROR')
```

### Block Status
| Path | Description |
|------|-------------|
| `\Data\Blocks\{name}\Output\BLKSTAT` | 0 = OK, 1 = error |
| `\Data\Blocks\{name}\Output\BLKMSG` | Short error summary |
| `\Data\Blocks\{name}\Output\PER_ERROR` | Full error details |

### Loop Convergence History
```
list_elements(session, '\Data\Convergence\Convergence\{solver}\Output\ERR_TOL2')
```
Each element = one iteration. Values should trend toward zero.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "COLUMN DRIES UP" | Wrong feed conditions or impossible specs | Check feed T/P/composition, relax column specs |
| Block incomplete | Missing required inputs | Run `check_inputs`, read block doc |
| Oscillating convergence | Wegstein struggling | Switch to `NEWTON` or `BROYDEN` |
| No convergence | Bad initial estimates | Provide tear stream estimates, reduce specs |
| "Petroleum/Wide-boiling not allowed with VLL" | RadFrac ALGORITHM incompatible with 3-phase | Set `ALGORITHM=STANDARD` on the column |
| "COLUMN NOT IN MASS BALANCE" | Product flows exceed feed | Check D + Side draw + B = Feed |
| Recycle loop not converging | Tear method or max iterations insufficient | Switch to `BROYDEN`, increase `BR_MAXIT` to 100 |

## Troubleshooting Workflow

When a simulation fails, follow this order:

1. **Fix upstream before downstream** — Upstream block errors cascade downstream. Always fix the most upstream issue first.

## Tips

- Feed temperature drastically affects convergence, especially in cryogenic systems.
- For recycle loops, provide good initial estimates on tear streams.
- Max block name length: 8 characters.
