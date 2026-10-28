# HyCyc: solids separator

`MODEL` = `SOLIDS-SEP`: a split set by specs, with no cyclone sizing. Paths are under `\Data\Blocks\{name}\`; basics in [hycyc.md](hycyc.md).

It needs `PRES` plus the two specs that `PHASEP_OPT` names. `L(OUT)` gets the `FLUID_SPLIT` share of the feed liquid, `S(OUT)` the `SOLID_SPLIT` share of the feed solids.

## Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASEP_OPT` | `SPLP`, `SPLL`, `SPSL`, `LPSL`, `LLSL` | Which two specs set the split (SP = solids fraction to `S(OUT)`, LP = solids load of `L(OUT)`, LL = liquid load of `S(OUT)`, SL = liquid fraction to `L(OUT)`) |
| `Input\SOLID_SPLIT` | fraction | Share of feed solids sent to `S(OUT)` |
| `Input\FLUID_SPLIT` | fraction | Share of feed liquid sent to `L(OUT)` |
| `Input\SOLID_LOAD` | mass ratio | Solids carried in `L(OUT)`, kg per kg liquid |
| `Input\FLUID_LOAD` | mass ratio | Liquid carried in `S(OUT)`, kg per kg solids |

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
| `Input\FINES_OFFSET` | fraction | Fines that bypass to `S(OUT)`; smaller than `SOLID_SPLIT` |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\SFRAC` | fraction | Share of feed solids in `S(OUT)` |
| `Output\LFRAC` | fraction | Share of feed liquid in `L(OUT)` |
| `Output\SOLD_LOAD` | mass ratio | Solids carried in `L(OUT)` |
| `Output\FLUD_LOAD` | mass ratio | Liquid carried in `S(OUT)` |
| `Output\D50` | LENGTH | Size split half and half (classification) |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
