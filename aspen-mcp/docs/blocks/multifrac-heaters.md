# MultiFrac heaters and heat streams

Paths are under `\Data\Blocks\{name}\`.

## Side duties

| Path | Type | Purpose |
|---|---|---|
| `Input\HEATER_DUTY\{col}\{stage}` | ENTHALPY-FLO | Duty on a stage (row: `insert_row` + `set_label` the stage on `HEATER_DUTY\{col}`) |

## Heat streams

| Path | Type | Purpose |
|---|---|---|
| `Input\H_FEED_COL\{heat}` | int | Column a heat stream on `HS(IN)` enters |
| `Input\H_FEED_STAGE\{heat}` | int | Stage it enters |

Give the heat stream its duty at `\Data\Streams\{heat}\Input\DUTY`.

## Heating or cooling a connect stream

Set one of `CS_DUTY`, `CS_TEMP`, `CS_DELT` per connect stream: once one is set the others are refused.

| Path | Type | Purpose |
|---|---|---|
| `Input\CS_DUTY\{cs}` | ENTHALPY-FLO | Duty added to the connect stream |
| `Input\CS_TEMP\{cs}` | TEMPERATURE | Temperature it is brought to |
| `Input\CS_DELT\{cs}` | DELTA-T | Temperature rise it gets |
| `Input\QSTREAM_OUT\{cs}` | ID | Heat stream on `HS(OUT)` that carries that duty away |
| `Input\QSTREAM_IN\{cs}` | ID | Heat stream on `HS(IN)` that supplies the duty |

A heat stream already placed on a column with `H_FEED_COL` is refused here.
