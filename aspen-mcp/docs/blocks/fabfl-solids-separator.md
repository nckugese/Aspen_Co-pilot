# FabFl: solids separator

`METHOD` `SOLIDS-SEP`: no filter model; two specs split the dust and the gas, and the outlets are flashed. Paths are under `\Data\Blocks\{name}\`; basics in [fabfl.md](fabfl.md).

With `SPSL`, `S(OUT)` got 98 % of the dust and `G(OUT)` 99 % of the nitrogen.

## Separation

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASEP_OPT` | `SPLP`, `SPLL`, `SPSL`, `LPSL`, `LLSL` | Which two specs set the split (SP = dust share to `S(OUT)`, LP = dust load of the gas outlet, LL = gas load of the dust outlet, SL = gas share to `G(OUT)`); default `SPLP` |
| `Input\SOLID_SPLIT` | fraction | Share of the feed dust sent to `S(OUT)` |
| `Input\FLUID_SPLIT` | fraction | Share of the gas sent to `G(OUT)` |
| `Input\SOLID_LOAD` | mass ratio | Dust per kg of gas in `G(OUT)` |
| `Input\FLUID_LOAD` | mass ratio | Gas per kg of dust in `S(OUT)` |

A load spec fixes a flow: with `SPLP` and `SOLID_LOAD` 0.0005, about three quarters of the nitrogen left with the dust.

A `FLUID_LOAD` below the least gas the dust must carry (its value depends on the feed) ends with a warning, and that least value is used.

| Path | Type | Purpose |
|---|---|---|
| `Input\CLASS_CHAR` | `SIZE`, `VELOCITY` | Classify the dust by particle size (default) or settling velocity |
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
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash (default 2) |
| `Input\PHASE` | `V`, `L`, `S` | The phase when `NPHASE` is 1 (default `V`) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\SOLD_RECOV` | fraction | Share of the feed dust in `S(OUT)` |
| `Output\FLUD_RECOV` | fraction | Share of the gas in `G(OUT)` |
| `Output\FLUD_LOAD` | mass ratio | Dust per kg of gas in `G(OUT)` |
| `Output\SOLD_LOAD` | mass ratio | Gas per kg of dust in `S(OUT)` |

The two load results are named after the other phase: `FLUD_LOAD` matched the `SOLID_LOAD` spec.

| Path | Type | Purpose |
|---|---|---|
| `Output\D50` | LENGTH | Cut size of the classification |
