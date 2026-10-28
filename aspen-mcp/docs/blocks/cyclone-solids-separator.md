# Cyclone: solids separator

`MODEL` = `SOLIDS-SEP`: the solids and gas are split by two given specs, no geometry. Paths are under `\Data\Blocks\{name}\`; basics in [cyclone.md](cyclone.md).

It needs `PRES` plus the two specs that `PHASEP_OPT` names.

Mind the result names: `Output\FLUD_LOAD` is the solids load of `G(OUT)` (what `SOLID_LOAD` sets) and `Output\SOLD_LOAD` the gas load of `S(OUT)` (what `FLUID_LOAD` sets).

With `SPLP`, a `SOLID_LOAD` below what `SOLID_SPLIT` already leaves in the gas is raised to that minimum, with a warning.

`PRES` above 0 is the outlet pressure; 0 or below is a drop from the feed.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASEP_OPT` | `SPLP`, `SPLL`, `SPSL`, `LPSL`, `LLSL` | Which two specs set the split: SP = solids fraction to `S(OUT)`, LP = solids load of `G(OUT)`, LL = gas load of `S(OUT)`, SL = gas fraction to `G(OUT)` |
| `Input\SOLID_SPLIT` | fraction | Share of the feed solids sent to `S(OUT)` |
| `Input\FLUID_SPLIT` | fraction | Share of the feed gas sent to `G(OUT)` |
| `Input\SOLID_LOAD` | mass ratio | kg solids per kg gas in `G(OUT)` |
| `Input\FLUID_LOAD` | mass ratio | kg gas per kg solids in `S(OUT)` |
| `Input\PRES` | PRESSURE | Outlet pressure, or a drop when 0 or below |

## Outlet flash

`OPT_OPERATE` picks the thermal spec; `TEMP` and `DELT` act as their names say.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_OPERATE` | `OPT-HEATDU`, `OPT-TEMP`, `OPT-DELT` | Thermal spec: duty (default, 0), temperature or temperature change |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\DELT` | DELTA-T | Outlet temperature change |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash (default 2) |
| `Input\PHASE` | `V` | The phase when `NPHASE` is 1 |

## Classification

| Path | Type | Purpose |
|---|---|---|
| `Input\CLASS_CHAR` | `SIZE`, `VELOCITY` | Spread the split over the solids by particle size or settling velocity |
| `Input\SHARPNESS` | real | Sharpness of that split |
| `Input\FINES_OFFSET` | fraction | Fines that bypass to `S(OUT)`; smaller than `SOLID_SPLIT` |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\SOLD_RECOV` | fraction | Share of the feed solids in `S(OUT)` |
| `Output\FLUD_RECOV` | fraction | Share of the feed gas in `G(OUT)` |
| `Output\D50` | LENGTH or VELOCITY | Cut size (or cut velocity) of the classification |
