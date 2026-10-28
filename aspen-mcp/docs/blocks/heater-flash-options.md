# Heater: flash options

Starting guesses and limits of the outlet flash. Paths are under `\Data\Blocks\{name}\`.

## Input | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\T_EST` | TEMPERATURE | Starting guess for the temperature when it is not specified |
| `Input\P_EST` | PRESSURE | Starting guess for the pressure when it is not specified |
| `Input\MAXIT` | int | Flash iteration limit (default 30) |
| `Input\TOL` | tolerance | Flash tolerance (default 1e-4) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
