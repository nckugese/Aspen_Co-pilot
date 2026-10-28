# CfFilter: solids separator

`TYPE` = `SOLIDS-SEP`: a split set by specs, without rating a membrane. Paths are under `\Data\Blocks\{name}\`; basics in [cffilter.md](cffilter.md).

It needs `PRES` plus the two specs that `PHASEP_OPT` names. `P(OUT)` gets the `FLUID_SPLIT` share of the feed liquid, `R(OUT)` the `SOLID_SPLIT` share of the feed solids.

## Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASEP_OPT` | `SPLP`, `SPLL`, `SPSL`, `LPSL`, `LLSL` | Which two specs set the split (SP = solids fraction to `R(OUT)`, LP = solids load of the permeate, LL = liquid load of the retentate, SL = liquid fraction to `P(OUT)`) |
| `Input\SOLID_SPLIT` | fraction | Share of feed solids sent to `R(OUT)` |
| `Input\FLUID_SPLIT` | fraction | Share of feed liquid sent to `P(OUT)` |
| `Input\SOLID_LOAD` | mass ratio | Solids carried in the permeate, kg per kg |
| `Input\FLUID_LOAD` | mass ratio | Liquid carried in the retentate, kg per kg |

## Outlet flash

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES` | PRESSURE | Outlet pressure |
| `Input\OPT_OPERATE` | `OPT-HEATDU`, `OPT-TEMP`, `OPT-DELT` | Thermal spec: duty (default), temperature or temperature change |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty (default 0, adiabatic) |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\DELT` | DELTA-T | Outlet temperature change |
| `Input\TINIT` | TEMPERATURE | Starting guess for the outlet temperature (duty spec) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash |
| `Input\PHASE` | `L`, `V`, `S` | The phase when `NPHASE` is 1 |

## Classification

| Path | Type | Purpose |
|---|---|---|
| `Input\CLASS_CHAR` | `SIZE`, `VELOCITY` | Classify the solids by particle size or by settling velocity |
| `Input\SHARPNESS` | real | Sharpness of that classification |
| `Input\FINES_OFFSET` | fraction | Fines that bypass to `R(OUT)`; smaller than `SOLID_SPLIT` |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\SFRAC` | fraction | Share of feed solids in `R(OUT)` |
| `Output\LFRAC` | fraction | Share of feed liquid in `P(OUT)` |
| `Output\SOLD_LOAD` | mass ratio | Solids carried in the permeate |
| `Output\FLUD_LOAD` | mass ratio | Liquid carried in the retentate |
| `Output\D50` | LENGTH | Size split half and half (classification) |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
