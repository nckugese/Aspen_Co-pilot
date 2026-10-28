# RBatch pressure and vent

Paths are under `\Data\Blocks\{name}\`. `PRES_TYPE` `PROFILE` and `CALCULATE` (Setup | Specifications), and the vent on `VP(OUT)`.

## Pressure profile (`PROFILE`)

Paired lists: one `insert_row` on `Input\PPROF_TIME` per point adds the same row to `Input\PPROF_PRES`.

| Path | Type | Purpose |
|---|---|---|
| `Input\PPROF_TIME\{row}` | TIME | Time of the point |
| `Input\PPROF_PRES\{row}` | PRESSURE | Pressure at that time |

## Vent (`VP(OUT)`)

With a stream on `VP(OUT)`, set `NPHASE` 2 or 3: vapor formed at the set pressure leaves through the vent.

| Path | Type | Purpose |
|---|---|---|
| `Input\P_OPEN` | PRESSURE | Pressure at which the vent opens |
| `Input\P_CLOSE` | PRESSURE | Pressure at which it closes again |

`P_OPEN` and `P_CLOSE` are not enterable with `CALCULATE`.

| Path | Type | Purpose |
|---|---|---|
| `Input\NPHASE_ACCUM` | `1`, `2` | Phases in the vent accumulator |
| `Input\PHASE_ACCUM` | `L`, `V` | Accumulator phase when `NPHASE_ACCUM` is 1 |

## Closed vessel (`CALCULATE`)

| Path | Type | Purpose |
|---|---|---|
| `Input\VOLUME` | VOLUME | Reactor volume; the pressure follows from it |
| `Input\P_SETPOINT` | PRESSURE | Set point of the vent pressure controller |
| `Input\P_GAIN` | real | Its proportional gain |
| `Input\P_INT_TIME` | real | Its integral time, s |
| `Input\P_MAX_OUT` | MASS-FLOW | Largest vent flow it can open |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\PRES_REAC\{pt}` | PRESSURE | Profile: reactor pressure (computed with `CALCULATE`) |
| `Output\MO_FLOW_VENT\{pt}` | MOLE-FLOW | Profile: vent flow |
