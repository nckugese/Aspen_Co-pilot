# PetroFrac condenser, free water and utilities

Paths are under `\Data\Blocks\{name}\`. Options of the `SUBCOOLED` and `PARTIAL-VL` condensers (`CTYPE`, [petrofrac.md](petrofrac.md)), free water, and utilities on the condenser and reboiler.

## Setup | Condenser

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_SUBCOOL` | `SUBCOOL`, `TEMP` | `SUBCOOLED`: set by degrees of subcooling or by the liquid temperature |
| `Input\DEGSUB` | DELTA-T | Degrees of subcooling |
| `Input\SC_TEMP` | TEMPERATURE | Liquid outlet temperature (`TEMP`) |
| `Input\OPT_COND_SPC` | `RDV`, `TEMP` | `PARTIAL-VL`: set by the vapor share of the distillate or by the condenser temperature |
| `Input\BASIS_DV:D` | fraction | Vapor distillate over total distillate |
| `Input\T_COND` | TEMPERATURE | Condenser temperature |

## Free water

| Path | Type | Purpose |
|---|---|---|
| `Input\BLKOPFREWAT` | `NO`, `YES` | Free water: `YES` decants a water phase from the condenser to `WD(OUT)` |

`DIRTY` can be written but PetroFrac cannot run with it: the input translator stops.

## Utilities

A condenser or reboiler utility needs `WATER` in the component list, even when no stream carries it; without it the run stops in input translation.

Create each utility with `add_element` on `\Data\Utilities`, then set under its `Input`: `UTILITY_TYPE`, `CALCCO2` `NO` (left at its default, the run stops asking for a CO2 factor or a fuel composition), `CALOPT` `FLASH` and both end states. The run here: CW `WATER`, `TIN` 20 C to `TOUT` 30 C, `PRES` and `PRES_OUT` 4 bar; LPS `STEAM`, `PRES` and `PRES_OUT` 10 bar, `VFRAC` 1 to `VFRAC_OUT` 0. More in [utilities](../utilities/utilities.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\COND_UTIL` | ID | Utility on the condenser |
| `Input\REB_UTIL` | ID | Utility on the reboiler |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\MOLE_DW` | MOLE-FLOW | Free water decanted |
| `Output\COND_USAGE` | MASS-FLOW | Utility rate on the condenser |
| `Output\REB_USAGE` | MASS-FLOW | Utility rate on the reboiler |
| `Output\COND_COST` | cost rate | Utility cost of the condenser |
| `Output\REB_COST` | cost rate | Utility cost of the reboiler |
