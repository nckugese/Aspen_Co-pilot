# HXFlux: radiant section

`HEAT_TR_MODE` = `RADIANT`: the cold side is the process fluid in the furnace tubes, the hot side the flue gas. Paths are under `\Data\Blocks\{name}\`; basics in [hxflux.md](hxflux.md).

It needs `TCOLD_IN` plus five of `TCOLD_OUT`, `T_FLUE_GAS`, `DUTY`, `H_CONV`, `TUBE_AREA` and `COLD_PL_AREA`; the one left blank is computed. With four of them the block stays incomplete.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\TCOLD_IN` | TEMPERATURE | Process inlet temperature |
| `Input\TCOLD_OUT` | TEMPERATURE | Process outlet temperature |
| `Input\OPT_FLUE` | `TEMPERATURE`, `STREAM` | Flue gas temperature as a value or from a stream |
| `Input\T_FLUE_GAS` | TEMPERATURE | Flue gas temperature leaving the radiant section |
| `Input\STR_FLUE` | stream ID | Stream whose temperature serves as the flue gas value |
| `Input\DUTY` | ENTHALPY-FLO | Duty taken up by the process fluid |
| `Input\H_CONV` | HEAT-TRANS-C | Convective coefficient, flue gas to tubes |
| `Input\TUBE_AREA` | AREA | Outside surface of the tubes |
| `Input\COLD_PL_AREA` | AREA | Cold plane area of the tube rows |

## Input | Radiant

`TBW_OFF` lowers the bridgewall temperature below the flue gas temperature; `W1` and `W2` weight the process inlet and outlet temperatures in the weighted mean.

| Path | Type | Purpose |
|---|---|---|
| `Input\RAD_EX_FAC` | real | Exchange factor of the radiation (default 0.5) |
| `Input\C_PL_EFF` | real | Absorption factor of the tube rows on the cold plane (default 0.75) |
| `Input\T_FF_FAC` | real | Factor for the tube front-face temperature (default 1.1) |
| `Input\T_SURF_FAC` | real | Factor for the tube surface temperature (default 1.75) |
| `Input\W1` | real | Weight of the process inlet temperature (default 1) |
| `Input\W2` | real | Weight of the process outlet temperature (default 1) |
| `Input\TBW_OFF` | DELTA-T | Bridgewall offset (default 0) |
| `Input\W_DT_OFF` | DELTA-T | Added when the tube wall temperature is computed (default 0) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\RAD_TDUTY` | ENTHALPY-FLO | Total duty |
| `Output\RAD_RDUTY` | ENTHALPY-FLO | Radiant part of the duty |
| `Output\RAD_CDUTY` | ENTHALPY-FLO | Convective part of the duty |
| `Output\RAD_TFLUE` | TEMPERATURE | Flue gas temperature |
| `Output\RAD_TBW` | TEMPERATURE | Bridgewall temperature |
| `Output\RAD_TSURF` | TEMPERATURE | Tube surface temperature |
| `Output\RAD_TFF` | TEMPERATURE | Tube front-face temperature |
| `Output\RAD_TAVGWT` | TEMPERATURE | Weighted mean process temperature |
| `Output\RAD_TOUT` | TEMPERATURE | Process outlet temperature |
