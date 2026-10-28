# RBatch continuous feed

Paths are under `\Data\Blocks\{name}\`. A stream on `CF(IN)` enters during the reaction (Setup | Continuous Feeds); `{stream}` is its name.

Connecting the stream adds its entry to `OPT_FEED`, `FPROF_TIME` and `FPROF_FLOW`.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_FEED\{stream}` | `INLET`, `PROFILE` | Flow taken from the stream, or from a time profile |

1. For `PROFILE`: `insert_row` on `Input\FPROF_TIME\{stream}` and on `Input\FPROF_FLOW\{stream}` once per point (rows `#0`, `#1`, ...).

| Path | Type | Purpose |
|---|---|---|
| `Input\FPROF_TIME\{stream}\{row}` | TIME | Time of the point |
| `Input\FPROF_FLOW\{stream}\{row}` | MASS-FLOW | Mass rate fed at that point |

Write `FPROF_TIME` without a unit (it is read in hours with METCBAR): with a unit the input translator rejects the block (BADUNT) and nothing runs.

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\MA_FLOW_FEED\MIXED\{stream}\{pt}` | MASS-FLOW | Profile: how fast the side stream enters, by mass |
| `Output\MA_CUMU_FEED\MIXED\{stream}\{pt}` | MASS | Profile: mass fed so far |
