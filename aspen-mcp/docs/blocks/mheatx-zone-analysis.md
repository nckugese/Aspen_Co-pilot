# MHeatX zone analysis

Paths are under `\Data\Blocks\{name}\`. Splits the exchanger into zones along the duty to give UA, LMTD and the minimum approach.

With `NPOINT` 0 (the default) the block runs without zones and the results below stay empty.

## Setup | Zone Analysis

| Path | Type | Purpose |
|---|---|---|
| `Input\NPOINT` | int | Number of zones; 0 turns the analysis off |
| `Input\FLOW_DIR` | `COUNTERCURRE`, `COCURRENT` | Flow arrangement |
| `Input\ADD_POINTS` | `YES`, `NO` | Add points where a phase changes and where a stream enters or leaves |
| `Input\ADAPTIVE_GRI` | `YES`, `NO` | Add zones where the profile bends; needs `ADD_POINTS` `YES` and zones |
| `Input\MAX_NPOINT` | int | Upper limit on zone points, with `ADAPTIVE_GRI` `YES` |
| `Input\DTTOL` | number | Approach threshold for the extra zones, with `ADAPTIVE_GRI` `YES` |
| `Input\CHECK_PHASE` | `YES`, `NO` | Take each zone's phase from the inlet and outlet states |
| `Input\OPT_CALC` | `FLASH`, `TQTABLE` | Zone points by a flash each, or interpolated from a flash table (`TQTABLE` needs `NPOINT` > 0) |

## Setup | Flash Table

| Path | Type | Purpose |
|---|---|---|
| `Input\TQTAB_NPOINT` | int | Flash-table points for every stream |

## Results (zone analysis on)

| Path | Type | Purpose |
|---|---|---|
| `Output\UA` | UA | Overall UA |
| `Output\LMTD` | DELTA-T | Duty divided by UA |
| `Output\MITA` | DELTA-T | Minimum temperature approach |
| `Output\HSTA` | DELTA-T | Approach at the hot end (`CSTA` cold end) |
| `Output\HSNTU` | number | Hot-side NTU (`CSNTU` cold side) |
| `Output\HOT_TEMP\{pt}` | TEMPERATURE | Hot composite temperature at a point (`COLD_TEMP` cold) |
| `Output\DUTY2\{pt}` | ENTHALPY-FLO | Cumulative duty at a point |
| `Output\UAZONE\{pt}` | UA | UA of the zone ending at the point |
