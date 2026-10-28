# Filter: solids separator

`TYPE` = `SOLIDS-SEP`: a split set by specs, without rating a filter. Paths are under `\Data\Blocks\{name}\`; basics in [filter.md](filter.md).

## Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASEP_OPT` | `SPLP`, `SPLL`, `SPSL`, `LPSL`, `LLSL` | Which two specs set the split (SP = solids fraction to `S(OUT)`, LP = solids load of the filtrate, LL = liquid load of the cake, SL = liquid fraction to `L(OUT)`) |
| `Input\SOLID_SPLIT` | fraction | Share of feed solids sent to `S(OUT)` |
| `Input\FLUID_SPLIT` | fraction | Share of feed liquid sent to `L(OUT)` |
| `Input\SOLID_LOAD` | mass ratio | Solids carried in the filtrate, kg per kg |
| `Input\FLUID_LOAD` | mass ratio | Liquid carried in the cake, kg per kg |
| `Input\PRES` | PRESSURE | Outlet pressure |
| `Input\OPT_OPERATE` | `OPT-HEATDU`, `OPT-TEMP`, `OPT-DELT` | Outlet thermal spec: duty (default), temperature or temperature change |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty (default 0, adiabatic) |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\DELT` | DELTA-T | Outlet temperature change |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash |
| `Input\PHASE` | `L`, `V`, `S` | The phase when `NPHASE` is 1 |
| `Input\CLASS_CHAR` | `SIZE`, `VELOCITY` | Classify the solids by particle size or by settling velocity |
| `Input\SHARPNESS` | real | Sharpness of that classification |
| `Input\FINES_OFFSET` | fraction | Fines that bypass to the cake; smaller than `SOLID_SPLIT` |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\CALSOLIDLD` | mass ratio | Solids carried in the filtrate |
| `Output\SEP_D50` | LENGTH | Size split half and half (classification) |
