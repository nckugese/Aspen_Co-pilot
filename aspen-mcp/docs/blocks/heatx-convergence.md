# HeatX convergence and report

Paths are under `\Data\Blocks\{name}\`.

## Options | Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\ALGORITHM` | `BROYDEN`, `NEWTON` | Solver of the block |
| `Input\PMAXIT` | int | Iteration limit |
| `Input\TEMP_TOL` | DELTA-T | Temperature tolerance |
| `Input\AREA_TOL` | AREA | Area tolerance (given area) |
| `Input\PRESSURE_TOL` | PRESSURE | Pressure tolerance |
| `Input\Q_ESTIMATE` | ENTHALPY-FLO | Duty guess when an area is given |
| `Input\ALLOW_TCROSS` | `NO`, `YES` | Accept a temperature cross |
| `Input\NPOINTS` | int | Film-coefficient evaluations per section (detailed) |

## Options | Report

| Path | Type | Purpose |
|---|---|---|
| `Input\PROFILE` | `PROFILE`, `NOPROFILE` | Write the T-Q profile tables to the report |
| `Input\SHELL` | `SHELL`, `NOSHELL` | Write the zone-by-zone results to the report |
