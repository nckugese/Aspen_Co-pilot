# CCD: temperature, duty, heat streams and convergence

Per-stage temperature or duty, temperature guesses, heat streams and convergence settings. Paths are under `\Data\Blocks\{name}\`; basics in [ccd.md](ccd.md).

Without entries on the first two sheets every stage is adiabatic: the base run's total duty was 0.

## Input | Temp-Duty Profiles

1. Insert a row into `TEMP` labelled with the stage number (`insert_row`, then the label); `HEAT_SDUTY` and `TEMP_EST` get the same row.
2. Write `TEMP` or `HEAT_SDUTY` on that row, not both: once one has a value the other is refused.

| Path | Type | Purpose |
|---|---|---|
| `Input\TEMP\{stage}` | TEMPERATURE | Fixed stage temperature; the block computes the duty |
| `Input\HEAT_SDUTY\{stage}` | ENTHALPY-FLO | Heat added to the stage |
| `Input\TEMP_EST\{stage}` | TEMPERATURE | Starting guess for the stage temperature |

A `TEMP` row also holds the stages without a row: 50 C on stage 2 put all three stages at 50 C.

## Input | Heat Streams

Every stream on `HS(IN)` or `HS(OUT)` gets its own row, keyed by the stream name, that stays incomplete until it has a stage; with an inlet heat stream on the block, a fixed `TEMP` is refused.

| Path | Type | Purpose |
|---|---|---|
| `Input\H_FEED_STAGE\{stream}` | int | Stage that receives an inlet heat stream |
| `Input\H_PROD_STAGE\{stream}` | int | Stage whose duty an outlet heat stream carries |

The inlet heat stream's duty became the block duty; the outlet heat stream carried the stage duty with the opposite sign.

## Input | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\EB_MAXIT` | int | Energy balance iterations (default 30) |
| `Input\EB_TOL` | real | Energy balance tolerance (default 1e-4) |
| `Input\FLASH_MAXIT` | int | Flash iterations (default 30) |
| `Input\FLASH_TOL` | real | Flash tolerance (default 1e-4) |

## Results (after a run)

With 50 kW on stage 2, `TOP_LTEMP` and `B_TEMP` ([ccd.md](ccd.md)) matched the `L(OUT)` and `S(OUT)` temperatures, while `TOP_TEMP` and `BOTTOM_TEMP` stayed at the 25 C of the feeds.

| Path | Type | Purpose |
|---|---|---|
| `Output\DUTY` | ENTHALPY-FLO | Total duty, the sum of the stage duties |
| `Output\QCALC\{stage}` | ENTHALPY-FLO | Duty of each stage, also for a fixed `TEMP` |
