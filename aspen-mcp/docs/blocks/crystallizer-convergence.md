# Crystallizer: convergence and flash options

Paths are under `\Data\Blocks\{name}\`; basics in [crystallizer.md](crystallizer.md).

## Advanced | Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Iterations of the balance loop |
| `Input\TOL` | real | Tolerance of the balance loop |
| `Input\TOL_RATIO` | real | Inner to outer loop tolerance ratio |
| `Input\TLOWER` | TEMPERATURE | Lowest temperature the solver may try |
| `Input\TUPPER` | TEMPERATURE | Highest temperature the solver may try |
| `Input\MAX_TSTEP` | DELTA-T | Largest temperature step |
| `Input\TEAR_METHOD` | `BROYDEN`, `WEGSTEIN`, `DIRECT` | Method for the recirculation loop |
| `Input\DS_ITERS` | int | Direct substitution steps before acceleration; not with `DIRECT` |
| `Input\QMIN` | real | Lower bound of the acceleration factor; `WEGSTEIN` only |
| `Input\QMAX` | real | Upper bound of the acceleration factor; `WEGSTEIN` only |

## Setup | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\T_EST` | TEMPERATURE | Temperature estimate |
| `Input\P_EST` | PRESSURE | Pressure estimate |
| `Input\FLASH_MAXIT` | int | Flash iterations |
| `Input\FLASH_TOL` | real | Flash tolerance |
