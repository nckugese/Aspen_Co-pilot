# Classifier: outlet conditions

Thermal spec, pressure and flash of the outlets. Paths are under `\Data\Blocks\{name}\`; basics in [classifier.md](classifier.md).

`PRES` above 0 is the outlet pressure; 0 (default) or below is a drop from the feed.

Sifters do not use `PRES`: their outlet pressure follows `PDROP` ([sifters](classifier-sifter.md)).

## Outlet flash

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_OPERATE` | `OPT-DELT`, `OPT-TEMP`, `OPT-HEATDU` | Thermal spec: temperature change (default, `DELT` 0), temperature, or duty |
| `Input\DELT` | DELTA-T | Temperature change |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty |
| `Input\PRES` | PRESSURE | Outlet pressure, or a drop when 0 or below |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash |
| `Input\PHASE` | `L`, `V`, `S` | The phase when `NPHASE` is 1 |
| `Input\FLASH_MAXIT` | int | Flash iteration limit (default 30) |
| `Input\FLASH_TOL` | real | Flash tolerance (default 1e-4) |
| `Input\TINIT` | TEMPERATURE | Temperature estimate for the flash |
| `Input\PINIT` | PRESSURE | Pressure estimate for the flash |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
