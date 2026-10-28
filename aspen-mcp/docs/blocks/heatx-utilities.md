# HeatX utility on one side

Paths are under `\Data\Blocks\{name}\`. A utility ([utilities.md](../utilities/utilities.md)) can stand in for the hot or the cold stream.

1. Create the utility as utilities.md says.
2. Connect only the stream side: `H(IN)` and `H(OUT)` for a cold utility, `C(IN)` and `C(OUT)` for a hot one.
3. Set `SPEC` and `VALUE` for the stream side (e.g. `T-HOT` 60 C), then the utility ID in `COLD_UTIL` (`HOT_UTIL` for a utility on the hot side).

A side's utility field is closed while `SPEC` fixes that side: `COLD_UTIL` under `T-COLD`, `HOT_UTIL` under `T-HOT`.

check_inputs still lists the open ports as required; run_simulation runs the block all the same.

## Setup | Utility

| Path | Type | Purpose |
|---|---|---|
| `Input\HOT_UTIL` | utility ID | ID of the utility that stands in for the hot side |
| `Input\COLD_UTIL` | utility ID | ID of the utility that stands in for the cold side |
| `Input\FAN_UTIL` | utility ID | Electricity utility for fan power; a shortcut run reports no usage for it |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\UTL_USAGE` | MASS-FLOW | Utility flow |
| `Output\UTIL_DUTY` | ENTHALPY-FLO | Duty on the utility (negative when it takes heat) |
| `Output\UTL_COST` | COST-RATE | Utility cost |
