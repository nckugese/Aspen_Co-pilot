# Utilities

A utility is a heating or cooling medium or electricity with a price: Aspen sizes its flow from the duty or power of each block that uses it and reports the cost.

Root: `\Data\Utilities\{id}`

1. `add_element` on `\Data\Utilities` with a new ID: at most 8 characters, letters, digits and `-`.
2. Write `UTILITY_TYPE`, `CALOPT` with the fields that mode needs, and a price.
3. Put the ID in the block's utility field: `Input\UTILITY_ID` on single-duty blocks ([blocks/common.md](../blocks/common.md#utility)), `COND_UTIL` / `REB_UTIL` on a column.

`CALCCO2` starts as `YES`, and then the run needs `CO2FACTOR`: without it the run does not start. Write `NO` when emissions are not wanted.

`STEAM` and `WATER` in `FLASH` mode need `WATER` in the component list, or the run does not start.

In `FLASH` mode give each end a pair of states: T with P, P with vapor fraction (steam; both temperatures then come out at saturation), or P with superheat. A temperature with no pressure fails.

`REFRIGERATIO` and `GENERAL` in `FLASH` mode take their fluid from `FRAC`.

`DUTY` mode needs `COOLING_VALU`, positive for heating and negative for cooling. Without it, or with the wrong sign, the block ends with a warning and no utility rate.

A heater outlet hotter than its steam ends the block with an error: match the utility temperature to the duty.

## Input

| Path | Type | Purpose |
|---|---|---|
| `Input\UTILITY_TYPE` | `STEAM`, `WATER`, `ELECTRICITY`, `REFRIGERATIO`, `GENERAL`, `GAS`, `OIL`, `COAL` | Kind of utility; `REFRIGERATIO` is refrigeration (the code has 12 letters) |
| `Input\CALOPT` | `DUTY`, `FLASH` | How the amount is found: a heating value (`DUTY`, the default) or the states at inlet and outlet (`FLASH`) |
| `Input\COOLING_VALU` | MASS-ENTHALP | Heat given (+) or taken (-) per mass; `DUTY` mode |
| `Input\TIN` | TEMPERATURE | Inlet temperature |
| `Input\TOUT` | TEMPERATURE | Outlet temperature |
| `Input\PRES` | PRESSURE | Inlet pressure |
| `Input\PRES_OUT` | PRESSURE | Outlet pressure |
| `Input\VFRAC` | real | Inlet vapor fraction |
| `Input\VFRAC_OUT` | real | Outlet vapor fraction |
| `Input\DEGSUP_IN` | DELTA-T | Superheat of steam at the inlet |
| `Input\FRAC\{comp}` | real | Fluid composition (`FLASH` mode, types other than steam and water) |
| `Input\OPT_UTI_COST` | `PURCH-PRICE`, `ENERG-PRICE` | Price per mass (`PRICE`) or per energy (`ENERGY_PRICE`) |
| `Input\PRICE` | UNIT-PRICE | Price per mass of utility |
| `Input\ENERGY_PRICE` | ENERGY-PRICE | Price per energy delivered |
| `Input\ELEC_PRICE` | ELEC-PRICE | Electricity price; used by `ELECTRICITY` whatever `OPT_UTI_COST` says |
| `Input\CALCCO2` | `YES`, `NO` | Track the CO2 the utility emits |
| `Input\CO2FACTOR` | mass per energy | CO2 emitted per energy delivered |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\UTL_TCOST` | COST-RATE | Cost over every block that uses it |
| `Output\UTL_TRATE` | MASS-FLOW | Utility flow over every block |
| `Output\UTL_IN_TEMP` | TEMPERATURE | Inlet temperature used (computed in `FLASH` mode) |
| `Output\UTL_OUT_TEMP` | TEMPERATURE | Outlet temperature used |
| `Output\ENERGY_PRICE` | ENERGY-PRICE | Price per energy worked out from a mass price |
| `Output\UTL_EPOWER` | POWER | Electric power drawn (`ELECTRICITY`) |
| `Output\CO2RATE` | MASS-FLOW | CO2 emitted (`CALCCO2` `YES`) |
| `\Data\Blocks\{blk}\Output\UTIL_COST` | COST-RATE | Utility cost of one block |
| `\Data\Blocks\{blk}\Output\UTIL_DUTY` | ENTHALPY-FLO | Duty the utility serves in that block |
| `\Data\Blocks\{blk}\Output\UTL_USAGE` | MASS-FLOW | Utility flow of that block (kW for electricity) |

A column reports `Output\COND_COST` and `Output\REB_COST` instead of `UTIL_COST`.
