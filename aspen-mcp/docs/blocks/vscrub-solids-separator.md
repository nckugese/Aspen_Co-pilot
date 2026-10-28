# VScrub: solids separator

`SCRUB_TYPE` `SOLIDS-SEP`: no scrubbing model, the dust is split by two specs and the outlets are flashed. Here "vapor" is the vapor phase after mixing gas and liquid; the liquid follows the solids. Paths are under `\Data\Blocks\{name}\`; basics in [vscrub.md](vscrub.md).

## Separation

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASEP_OPT` | `SPLP`, `SPLL`, `SPSL`, `LPSL`, `LLSL` | Which two specs set the split (SP = solids share to `S(OUT)`, LP = solids load of the gas outlet, LL = vapor load of the solids outlet, SL = vapor share to `G(OUT)`); default `SPLP` |
| `Input\SOLID_SPLIT` | fraction | Share of the feed solids sent to `S(OUT)` |
| `Input\FLUID_SPLIT` | fraction | Share of the vapor sent to `G(OUT)` |
| `Input\SOLID_LOAD` | mass ratio | Solids per kg of vapor in `G(OUT)` |
| `Input\FLUID_LOAD` | mass ratio | Vapor per kg of solids in `S(OUT)` |

A load spec fixes a flow: with `SPLP` and `SOLID_LOAD` 0.0005 about a quarter of the nitrogen left with the solids, so `SPSL` suits a scrubber better.

| Path | Type | Purpose |
|---|---|---|
| `Input\CLASS_CHAR` | `SIZE`, `VELOCITY` | Classify the solids by particle size (default) or settling velocity |
| `Input\SHARPNESS` | fraction | Sharpness of that classification, 0 to 1 (0, the default, does not classify) |
| `Input\FINES_OFFSET` | fraction | Fines that bypass to `S(OUT)`; smaller than `SOLID_SPLIT` |

## Outlet flash

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES` | PRESSURE | Outlet pressure; 0 = no pressure drop (required) |
| `Input\OPT_OPERATE` | `OPT-HEATDU`, `OPT-TEMP`, `OPT-DELT` | Thermal spec: duty (default), temperature or temperature change |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty (default 0) |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\DELT` | DELTA-T | Outlet temperature change |
| `Input\TINIT` | TEMPERATURE | Temperature estimate for the duty flash |
| `Input\NPHASE` | `2`, `3` | Phases in the outlet flash (default 2) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\SOLD_RECOV` | fraction | Share of the feed solids in `S(OUT)` |
| `Output\FLUD_RECOV` | fraction | Share of the vapor in `G(OUT)` |
| `Output\FLUD_LOAD` | mass ratio | Solids per kg of vapor in `G(OUT)` |
| `Output\SOLD_LOAD` | mass ratio | Vapor per kg of solids in `S(OUT)` |

The two load results are named after the other phase: `FLUD_LOAD` matched the `SOLID_LOAD` spec.

| Path | Type | Purpose |
|---|---|---|
| `Output\D50` | LENGTH | Cut size of the classification |
