# MultiFrac condenser options

Paths are under `\Data\Blocks\{name}\`. The fields without a `{col}` index belong to column 1's condenser.

## Two-product condenser (`CONDENSER\1=PARTIAL-V-L`)

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_COND_SPC` | `RDV`, `TEMP` | Second condenser spec: distillate vapor fraction or temperature |
| `Input\BASIS_RDV` | fraction | Share of the distillate leaving as vapor (`RDV`) |
| `Input\T1` | TEMPERATURE | Condenser temperature (`TEMP`) |
| `Input\RDV_EST` | fraction | Starting guess of that vapor fraction (`TEMP`) |

## Subcooling

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_SUBCOOL` | `SUBCOOL`, `TEMP` | Subcooling given in degrees or as a temperature |
| `Input\DEGSUB` | DELTA-T | Degrees of subcooling |
| `Input\SC_TEMP` | TEMPERATURE | Subcooled temperature |
| `Input\SC_OPTION` | `REFLUX-AND-DISTILLATE`, `REFLUX-ONLY` | Which liquid is subcooled |

## Utilities

A cooling-water (`WATER`) or `STEAM` utility needs component WATER in the components list, even when no stream carries water; without it the run stops in input translation (UTLCHK.1).

Create each utility with `add_element` on `\Data\Utilities`, then set under its `Input`: `UTILITY_TYPE`, `CALCCO2` `NO` (left at its default, the run stops in input translation, UTLCHK.2), `CALOPT` `FLASH` and both end states (left at its default `CALOPT`, the block ends with BLKSTAT 2 and no results). The run here: CW `WATER`, `TIN` 20 C to `TOUT` 30 C, `PRES` and `PRES_OUT` 4 bar; ST `STEAM`, `PRES` and `PRES_OUT` 10 bar, `VFRAC` 1 to `VFRAC_OUT` 0. More in [utilities](../utilities/utilities.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\COND_UTIL\{col}` | ID | Utility on the condenser |
| `Input\REB_UTIL\{col}` | ID | Utility on the reboiler |

| Path | Type | Purpose |
|---|---|---|
| `Output\CON_UTL_DUTY\{col}` | ENTHALPY-FLO | Duty the condenser utility takes |
| `Output\COND_COST\{col}` | cost rate | Condenser utility cost |
| `Output\REB_UTL_DUTY\{col}` | ENTHALPY-FLO | Duty the reboiler utility gives (column 2) |
| `Output\REB_COST\{col}` | cost rate | Reboiler utility cost (column 2) |
