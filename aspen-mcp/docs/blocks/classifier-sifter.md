# Classifier: sifters

`METHOD` = `SIFTER`: gravity or impeller-wheel air classifiers for solids carried by a gas (for example calcite in nitrogen). Paths are under `\Data\Blocks\{name}\`; basics in [classifier.md](classifier.md).

All the gas leaves with the fines on `P(OUT)`. A gas stream on `G(IN)` joins the sifting gas.

Give a pressure drop: with the default of 0 every sifter run ends with a warning.

`SIFT_INP` codes per type: `COUNTER-CURR` `CUT-VEL`, `DENS-SIZ`, `CROS-SEC`, `SEPA-EFF`; `CROSS-CURREN` `CUT-VEL`, `DENS-SIZ`, `SEPA-EFF`, `LEN-WIDTH`; `IMP-SHORTCUT` the six wheel codes; `IMP-HUSEMANN` none ([impeller wheels](classifier-impeller.md)).

`CROSS-CURREN` with `CROS-SEC` passes the input check, but then the run does not start at all and no block of the flowsheet gets results.

`CROSS-CURREN` needs `L_W_RATIO` with every code but `LEN-WIDTH`.

## Model

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `COUNTER-CURR`, `CROSS-CURREN`, `IMP-SHORTCUT`, `IMP-HUSEMANN` | Gravity counter-current, gravity cross-current, impeller wheel (short-cut) or impeller wheel (Husemann) |
| `Input\SIFT_INP` | `CUT-VEL`, `DENS-SIZ`, `CROS-SEC`, `SEPA-EFF`, `LEN-WIDTH`, `HERA-SPED`, `CVHE-SPED`, `CVRA-SPED`, `SPHE-SPED`, `SPRA-SPED`, `SPRA-HE` | What is given: CV cut velocity, DENS-SIZ cut size and density, CROS-SEC area, SP or SEPA-EFF separation efficiency, LEN-WIDTH length and width, HE wheel height, RA wheel radius, SPED wheel speed |
| `Input\CUT_VELOCITY` | VELOCITY | Cut velocity |
| `Input\CUT_SIZE` | LENGTH | `DENS-SIZ`: cut size |
| `Input\CUT_DENSITY` | DENSITY | `DENS-SIZ`: particle density |
| `Input\AREA` | AREA | `CROS-SEC`: cross-sectional area |
| `Input\EFF` | fraction | Separation efficiency: share of the feed solids to `S(OUT)` |
| `Input\LENGTH` | LENGTH | `LEN-WIDTH`: sifter length |
| `Input\WIDTH` | LENGTH | `LEN-WIDTH`: sifter width |
| `Input\L_W_RATIO` | ratio | `CROSS-CURREN`: length over width |
| `Input\SHARPNESS` | real | Sharpness of the cut |

## Pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\PDROP_OPT` | `CONSTANT`, `VEL-FUNCTION` | Pressure drop: constant, or a function of gas velocity |
| `Input\PDROP` | PDROP | `CONSTANT`: the drop |

`VEL-FUNCTION`: drop = `PDROP_A` + `PDROP_B`·v + `PDROP_C`·v², v the gas velocity, in `PDROP_UNITS` and `VEL_UNITS` (the runs: `N/sqm`, `m/sec`).

| Path | Type | Purpose |
|---|---|---|
| `Input\PDROP_A` | real | Constant term |
| `Input\PDROP_B` | real | Linear term |
| `Input\PDROP_C` | real | Quadratic term |
| `Input\PDROP_UNITS` | `N/sqm`, `bar`, `psi` | Pressure unit of the function |
| `Input\VEL_UNITS` | `m/sec`, `ft/sec` | Velocity unit of the function |
| `Input\SOLIDP_OPT` | `PDROP`, `INLET`, `AMBIENT`, `USER` | Pressure of `S(OUT)`: after the drop (default), the feed pressure, 1 atm, or `SOLID_PRES` |
| `Input\SOLID_PRES` | PRESSURE | `USER`: pressure of `S(OUT)` |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\VELOCITY2` | VELOCITY | Cut velocity found |
| `Output\AREA_CALC` | AREA | Flow area the model computed |
| `Output\LENGTH` | LENGTH | `CROSS-CURREN`: sifter length found |
| `Output\WIDTH` | LENGTH | `CROSS-CURREN`: sifter width found |
| `Output\LOAD_IN` | MASS-DENSITY | Solids per volume of feed gas |
| `Output\LOAD_OUT` | MASS-DENSITY | Solids per volume of gas in `P(OUT)` |
| `Output\PDROP` | PDROP | Pressure drop |
