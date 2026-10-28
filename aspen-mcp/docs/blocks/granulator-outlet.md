# Granulator: outlet flash

Thermal spec, pressure and flash of the outlets. Paths are under `\Data\Blocks\{name}\`; basics in [granulator.md](granulator.md).

Default: adiabatic (`OPT-HEATDU` with `DUTY` 0) at the feed pressure (`PRES` 0).

`PRES` above 0 is the outlet pressure; 0 or below is a drop from the feed.

## Outlet flash

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_OPERATE` | `OPT-HEATDU`, `OPT-TEMP`, `OPT-DELT` | Thermal spec: duty, temperature, or temperature change |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\DELT` | DELTA-T | Temperature change |
| `Input\PRES` | PRESSURE | Outlet pressure, or a drop when 0 or below |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash |
| `Input\PHASE` | `L` | The phase when `NPHASE` is 1 |
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
