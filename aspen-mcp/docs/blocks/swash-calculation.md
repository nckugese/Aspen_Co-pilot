# SWASH: calculation options and heat streams

Phases of the outlet flash, iteration limits, and heat streams. Paths are under `\Data\Blocks\{name}\`; basics in [swash.md](swash.md).

## Input | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash (default 2) |
| `Input\PHASE` | `L`, `V` | The single phase when `NPHASE` is 1 |
| `Input\MAX_ITER` | int | Iterations of the block's own loop (default 30) |
| `Input\CONV_TOL` | real | Tolerance of that loop (default 1e-4) |
| `Input\FLASH_MAXIT` | int | Flash iterations (default 30) |
| `Input\FLASH_TOL` | real | Flash tolerance (default 1e-4) |

`PHASE` V needs a `TEMP` that really leaves the outlets as vapor: `TEMP` 150 C at 1 atm converged; left adiabatic, the 25 C feeds drove the outlets to -173 C and the block failed.

`PHASE` S can be written to the tree, but the engine rejects that value when it reads the input and the run never starts; use `L` or `V`.

## Heat streams

`HS(OUT)` carries the block duty with the opposite sign (`DUTY` 50 kW gave -50 kW on the heat stream).

With `HS(IN)` alone, `TEMP` and `DUTY` are refused, and its duty did not reach the outlets: the run gave the adiabatic temperature, `QCALC` 0 and `QNET` -50 kW.

With both heat streams `TEMP` is allowed; `HS(OUT)` then carries the inlet heat stream minus `QCALC`.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Duty the outlet conditions needed |
| `Output\QNET` | ENTHALPY-FLO | Block duty minus the duty brought in on `HS(IN)` |
