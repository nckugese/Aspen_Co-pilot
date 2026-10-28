# RPlug convergence

Paths are under `\Data\Blocks\{name}\`. The block integrates its balances along the tube; change these when it stops early or runs slowly.

## Convergence | Integration Loop

| Path | Type | Purpose |
|---|---|---|
| `Input\INT_TOL` | real | Integration tolerance |
| `Input\HINIT` | real | First step, as a share of the length |
| `Input\MAXSTEP` | real | Largest step, as a share of the length |
| `Input\MAX_NSTEP` | int | Step limit |
| `Input\CORR_METHOD` | `NEWTON`, `DIRECT` | How each step's corrector is solved |
| `Input\CORR_TOL_RAT` | real | Corrector tolerance relative to `INT_TOL` |
| `Input\ERR_METHOD` | `DYNAMIC`, `STATIC`, `HYBRID` | How the step error is scaled |
| `Input\CUTOFF` | real | Value below which a variable is left out of the error test |
| `Input\EB_TOL_RATIO` | real | Ratio of the heat-balance tolerance to `INT_TOL` |
| `Input\NONNEG` | `NO`, `YES` | Keep component flows from going negative |

## Convergence | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\FLASH` | `NO`, `YES` | Run a full flash at every step |
| `Input\MAXIT` | int | Flash iteration limit |
| `Input\TOL` | real | Flash tolerance |
| `Input\MIX` | `YES`, `NO` | Mix the feeds by a flash at the inlet |
