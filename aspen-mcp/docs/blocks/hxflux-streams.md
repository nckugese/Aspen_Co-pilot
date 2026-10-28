# HXFlux: stream and heat-stream links

A temperature can be read from a stream of the flowsheet, and the duty from a heat stream. Paths are under `\Data\Blocks\{name}\`; basics in [hxflux.md](hxflux.md).

A stream named in `HOT_IN`, `HOT_OUT`, `COLD_IN` or `COLD_OUT` is only read: it is not connected to this block.

`HS(IN)` and `HS(OUT)` go together: with only one of them connected the block stays incomplete.

The heat stream on `HS(IN)` stands in for `DUTY` (leave `DUTY` blank); it leaves unchanged on `HS(OUT)`.

`HEATSTRM_DIR` must suit the sign of that heat stream: a cooler's is positive (`HOT-TO-COLD`), a heater's negative (`COLD-TO-HOT`). With the wrong one the block ends in error.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_HOTIN` | `TEMPERATURE`, `STREAM` | Hot inlet: a value (`THOT_IN`) or a stream's temperature |
| `Input\HOT_IN` | stream ID | Stream read for the hot inlet |
| `Input\OPT_HOTOUT` | `TEMPERATURE`, `STREAM` | Same for the hot outlet |
| `Input\HOT_OUT` | stream ID | Stream read for the hot outlet |
| `Input\OPT_COLDIN` | `TEMPERATURE`, `STREAM` | Same for the cold inlet |
| `Input\COLD_IN` | stream ID | Stream read for the cold inlet |
| `Input\OPT_COLDOUT` | `TEMPERATURE`, `STREAM` | Same for the cold outlet |
| `Input\COLD_OUT` | stream ID | Stream read for the cold outlet |
| `Input\DUTY_SID` | stream ID | Heat stream whose value is used as the duty; it needs no port |
| `Input\HEATSTRM_DIR` | `HOT-TO-COLD`, `COLD-TO-HOT` | Sign of the linked heat stream: positive (default) or negative |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\HOTINT` | TEMPERATURE | Hot inlet temperature read from its stream |
| `Output\IN_TEMP` | TEMPERATURE | Cold inlet temperature read from its stream |
| `Output\QCALC` | ENTHALPY-FLO | Duty taken from the heat stream |
| `Output\AREA_CALC` | AREA | Area that duty needs |
