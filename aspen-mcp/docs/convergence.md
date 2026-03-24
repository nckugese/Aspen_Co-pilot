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

## Troubleshooting Workflow

When a simulation fails, follow this order:

1. **Read PER_ERROR first** — For every block with errors, check `\Data\Blocks\{name}\Output\PER_ERROR`. It contains the specific error cause. Do not guess.
2. **Fix upstream before downstream** — Upstream block errors cascade downstream. Always fix the most upstream issue first.

## Tips

- Feed temperature drastically affects convergence, especially in cryogenic systems.
- For recycle loops, provide good initial estimates on tear streams.
- Max block name length: 8 characters.
