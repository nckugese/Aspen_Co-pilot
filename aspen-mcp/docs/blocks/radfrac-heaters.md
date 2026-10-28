# RadFrac heaters, heat streams, utilities

Paths are under `\Data\Blocks\{name}\`.

## Side heaters and heat streams

| Path | Type | Purpose |
|---|---|---|
| `Input\HEATER_DUTY\{stage}` | ENTHALPY-FLO | Duty on a stage (row: `insert_row` + `set_label` the stage) |

A side duty on a middle stage runs with the two operating specs unchanged.

| Path | Type | Purpose |
|---|---|---|
| `Input\H_FEED_STAGE\{heat}` | int | Stage a heat stream enters; the entry appears once the stream is on `HS(IN)` |

Give the heat stream its duty at `\Data\Streams\{heat}\Input\DUTY`.

A heat stream on the top or bottom stage counts as an operating spec: with two specs set it is refused there.

## Heat loss

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_HTLS` | `COLUMN` | Heat loss given for the whole column |
| `Input\HTLOSS_LIQ_C` | ENTHALPY-FLO | Column heat loss on the liquid |
| `Input\HTLOSS_VAP_C` | ENTHALPY-FLO | Column heat loss on the vapor |

## Thermosyphon reboiler (`REBOILER=THERMOSYPHON`)

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_TH_REB` | `FLOW`, `OUTLET` | What is given for the circulation |
| `Input\TH_FLOW` | MOLE-FLOW | Circulation rate |
| `Input\TH_TEMP` | TEMPERATURE | Reboiler outlet temperature |
| `Input\TH_VFRAC` | fraction | Vapor fraction leaving the thermosyphon |

## Utilities (instead of the common `UTILITY_ID`)

A `WATER` or `STEAM` utility needs component WATER in the component list, even when no stream carries water; without it the run stops in input translation (`UTLCHK.1`).

Give each utility (`\Data\Utilities\{id}\Input`) `CALCCO2` `NO`, `CALOPT` `FLASH` and both end states: water `TIN`, `PRES`, `TOUT`, `PRES_OUT`; steam `PRES` with `VFRAC` 1 and `PRES_OUT` with `VFRAC_OUT` 0. `CALCCO2` left on stops the run in input translation (`UTLCHK.2`); `CALOPT` left at its default ends in a warning with no usage or cost. More in [utilities.md](../utilities/utilities.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\COND_UTIL` | ID | Utility on the condenser |
| `Input\REB_UTIL` | ID | Utility on the reboiler |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\COND_USAGE` | flow | Condenser utility usage |
| `Output\REB_USAGE` | flow | Reboiler utility usage |
| `Output\COND_COST` | cost rate | Condenser utility cost |
| `Output\REB_COST` | cost rate | Reboiler utility cost |
| `Output\CON_UTL_DUTY` | ENTHALPY-FLO | Condenser duty the utility serves |
| `Output\REB_UTL_DUTY` | ENTHALPY-FLO | Reboiler duty the utility serves |
