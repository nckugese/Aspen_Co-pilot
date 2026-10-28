# Dryer: convective

`DRYER_TYPE` = `CONVECTIVE`: hot gas on `GAS(IN)` dries the solids along the dryer, with a drying curve ([drying curve](dryer-curve.md)) and transfer coefficients ([transfer](dryer-transfer.md)). Paths are under `\Data\Blocks\{name}\`; basics in [dryer.md](dryer.md).

Counter- and co-current dryers need `LENGTH` plus one more geometry value: `VL`, `LA`, `LST` or `LSV`. `ST`, `SH`, `AST` and `VST` stop the run with an invalid-geometry input error; with `CROSSFLOW` `ST`, `SH` and `AST` run.

`VL` also needs `FILL_GRADE`, else the run stops before it starts.

`FILL_GRADE` is a percentage: 10 m³ at 0.2 with `BED_POROSITY` 0.4 holds 0.012 m³ of solids.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\FLOW_DIR` | `COUNTERCURRE`, `COCURRENT`, `CROSSFLOW` | Gas flow relative to the solids |
| `Input\SOLIDS_FLOW` | `MIXED`, `PLUG-FLOW` | Solids well mixed (default) or in plug flow |
| `Input\SPEC_OPT` | `VL`, `LA`, `LST`, `LSV`, `ST`, `SH`, `AST` | The two (or one) geometry values given: V volume, L length, A area, ST residence time, SV solids velocity, SH holdup (default `VL`) |
| `Input\LENGTH` | LENGTH | Dryer length |
| `Input\VOLUME` | VOLUME | Dryer volume |
| `Input\AREA` | AREA | Cross-section area |
| `Input\SOL_RES_TIME` | TIME | Solids residence time |
| `Input\SOL_VELOCITY` | VELOCITY | Solids velocity |
| `Input\SOL_HOLDUP` | MASS | Solids held in the dryer |
| `Input\FILL_GRADE` | percent | Share of the volume taken by the solids bed |
| `Input\BED_POROSITY` | fraction | Void share of the bed (default 0.4) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EVAP_RATE2` | MASS-FLOW | Moisture evaporated |
| `Output\INSOL_MO_CON` | ratio | Feed moisture, kg per kg dry solids |
| `Output\OUSOL_MO_CON` | ratio | Product moisture, kg per kg dry solids |
| `Output\OUVAP_MO_CON` | ratio | Exhaust moisture, kg per kg dry gas |
| `Output\SOL_RES_TIME` | TIME | Solids residence time |
| `Output\SOL_VELOCITY` | VELOCITY | Solids velocity |

Feed 90 kg/hr water on 1001 kg/hr calcite reads `INSOL_MO_CON` 0.09; `OUVAP_MO_CON` is `EVAP_RATE2` over the dry gas flow.
