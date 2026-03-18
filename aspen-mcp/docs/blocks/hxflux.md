# HXFlux (Heat Exchanger with Flux)

Heat exchanger model supporting both convective and radiant heat transfer sections. Used for fired heaters, furnaces, and similar equipment.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| H | IN | Hot stream (flue gas) in |
| C | IN | Cold stream (process) in |
| H | OUT | Hot stream out |
| C | OUT | Cold stream out |

## Input — Convective Section

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\THOT_IN` | float | Specified inlet hot stream temperature |
| `\Data\Blocks\{name}\Input\TCOLD_IN` | float | Specified inlet cold stream temperature |
| `\Data\Blocks\{name}\Input\THOT_OUT` | float | Specified outlet hot stream temperature |
| `\Data\Blocks\{name}\Input\TCOLD_OUT` | float | Specified outlet cold stream temperature |
| `\Data\Blocks\{name}\Input\DUTY` | float | Heat duty |
| `\Data\Blocks\{name}\Input\U` | float | Overall heat transfer coefficient |
| `\Data\Blocks\{name}\Input\AREA` | float | Heat transfer area |
| `\Data\Blocks\{name}\Input\LMTD_CORR` | float | LMTD correction factor |
| `\Data\Blocks\{name}\Input\NUM_BUNDLES` | int | Number of bundles |
| `\Data\Blocks\{name}\Input\BUNDLE_DIA` | float | Bundle diameter |

## Input — Radiant Section

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\H_CONV` | float | Heat transfer coefficient |
| `\Data\Blocks\{name}\Input\TUBE_AREA` | float | Tube surface area |
| `\Data\Blocks\{name}\Input\COLD_PL_AREA` | float | Cold plane area |

## Output — Convective Section

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\HOTINT` | float | Calculated inlet hot stream temperature |
| `\Data\Blocks\{name}\Output\IN_TEMP` | float | Calculated inlet cold stream temperature |
| `\Data\Blocks\{name}\Output\HOT_TEMP` | float | Calculated outlet hot stream temperature |
| `\Data\Blocks\{name}\Output\COLD_TEMP` | float | Calculated outlet cold stream temperature |
| `\Data\Blocks\{name}\Output\LMTD` | float | Log-mean temperature difference |
| `\Data\Blocks\{name}\Output\U-OVER-COEF` | float | Overall heat transfer coefficient |
| `\Data\Blocks\{name}\Output\AREA_CALC` | float | Calculated heat transfer area |
| `\Data\Blocks\{name}\Output\QCALC` | float | Heat duty used |

## Output — Radiant Section

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\RAD_TIN` | float | Calculated inlet temperature |
| `\Data\Blocks\{name}\Output\RAD_TOUT` | float | Calculated outlet temperature |
| `\Data\Blocks\{name}\Output\RAD_TFLUE` | float | Calculated effective flue gas temperature |
| `\Data\Blocks\{name}\Output\RAD_TBW` | float | Bridgewall temperature |
| `\Data\Blocks\{name}\Output\RAD_TSURF` | float | Tube surface temperature |
| `\Data\Blocks\{name}\Output\RAD_TAREA` | float | Calculated tube surface area |

## Typical Setup

1. Place: `place_block(session, 'FH1', 'HXFlux')`
2. Set inlet/outlet temperatures or duty.
3. Specify heat transfer area or coefficient.

## Gotchas

- Has both convective and radiant sections — configure one or both as needed.
- Used for fired heaters and furnaces in petroleum refining.
