# RBatch

Batch or semi-batch reactor: kinetic reactions integrated over time until a stop criterion is met. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `BC(IN)` batch charge, `CF(IN)` continuous feed, `RP(OUT)` reactor product, `VP(OUT)` vent, `HS(OUT)` heat stream.

Nothing runs without a stream on `BC(IN)`, `PRINT_TIME`, `MAX_TIME` and the cycle time; with no stop criterion the batch goes on to `MAX_TIME` and ends with a warning (`STOP-CRIT` 0).

Streams are averages over one cycle: the charge is the `BC(IN)` flow times `CYCLE_TIME` (`TOT-CYCLE`) or times `FEED_TIME` (`BAT-FEED`, cycle = reaction time + `DOWN_TIME`), and `RP(OUT)` spreads the batch over the cycle.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `T-SPEC`, `T-PROFILE`, `TCOOL-SPEC`, `DUTY-SPEC`, `DUTY-PROF` | Operating mode: fixed temperature, temperature profile, coolant, duty, duty profile ([rbatch-operating-spec.md](rbatch-operating-spec.md)) |
| `Input\TEMP` | TEMPERATURE | Reactor temperature (`T-SPEC`) |
| `Input\PRES_TYPE` | `CONSTANT`, `PROFILE`, `CALCULATE` | Pressure fixed, given over time, or computed from the volume ([rbatch-pressure-vent.md](rbatch-pressure-vent.md)) |
| `Input\PRES` | PRESSURE | Reactor pressure (`CONSTANT`) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the reactor: one, vapor-liquid, vapor-liquid-liquid |
| `Input\PHASE` | `L`, `V` | The phase when `NPHASE` is 1 |
| `Input\CATWT` | MASS | Catalyst mass in the reactor |

`PHASE` goes only with `NPHASE` 1: clear it (write `""`) before setting 2 or 3.

With a stream on `VP(OUT)` and the pressure `CONSTANT` or `PROFILE`, `NPHASE` cannot be switched back to 1.

## Setup | Reactions

A fresh block has no row: `insert_row` on `Input\RXN_ID`, then write the set ID to `RXN_ID\#0`.

| Path | Type | Purpose |
|---|---|---|
| `Input\RXN_ID\{row}` | ID | Kinetic reaction set (for example a POWERLAW set) |

## Setup | Stop Criteria

1. `insert_row` on `Input\LOCATION` and label the row with the criterion number, e.g. `1`; `VARIABLE`, `VALUE`, `COMP` and `FROM` get the same row.
2. Set `LOCATION` before `VARIABLE`: `VARIABLE` is refused while it is empty.
3. Set `VARIABLE`, then `VALUE`, plus `COMP` for a component-based variable.

| Path | Type | Purpose |
|---|---|---|
| `Input\LOCATION\{id}` | `REACTOR`, `ACCUMULATOR`, `VENT` | Where the variable is watched |
| `Input\VARIABLE\{id}` | `TIME`, `MASS-FRAC`, `MOLE-FRAC`, `CONVERSION`, `MOLES`, `MASS`, `VOLUME`, `TEMP`, `MOLE-FLOW`, `MASS-FLOW`, `VFRAC`, `PRES` | What ends the batch |
| `Input\VALUE\{id}` | real | Value of the variable that ends the batch |
| `Input\COMP\{id}` | component | Component for fraction, conversion, moles or mass |
| `Input\FROM\{id}` | `ABOVE`, `BELOW` | Side the variable comes from |

`VALUE` has no unit of its own: it is read in the global unit set (`TIME` 1 stops at 1 hr in METCBAR).

## Setup | Operation Times

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_TIME` | `TOT-CYCLE`, `BAT-FEED` | Cycle given as a total, or as feed time + down time |
| `Input\CYCLE_TIME` | TIME | Total cycle time (`TOT-CYCLE`) |
| `Input\FEED_TIME` | TIME | Time the charge flow fills the batch (`BAT-FEED`) |
| `Input\DOWN_TIME` | TIME | Time between batches (`BAT-FEED`) |
| `Input\MAX_TIME` | TIME | Longest reaction time allowed |
| `Input\PRINT_TIME` | TIME | Time step at which a profile point is stored |
| `Input\MAX_NPOINT` | int | Most profile points kept |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STOP-CRIT` | int | Number of the criterion that ended the batch (0: none, ran to `MAX_TIME`) |
| `Output\STOP-TIME` | TIME | Reaction time at the stop |
| `Output\QCALC` | ENTHALPY-FLO | Mean duty: heat per batch divided by the cycle |
| `Output\QCYCLE` | ENTHALPY | Heat per cycle (`QCALC` times the cycle time) |
| `Output\TMIN` | TEMPERATURE | Lowest reactor temperature |
| `Output\TMAX` | TEMPERATURE | Highest reactor temperature |
| `Output\TIME\{pt}` | TIME | Profile: time of point `{pt}` (1, 2, ...) |
| `Output\TEMP_REAC\{pt}` | TEMPERATURE | Profile: reactor temperature |
| `Output\MO_FRAC_REAC\{pt}\{comp}` | fraction | Profile: reactor mole fraction per component |

More: [operating specification](rbatch-operating-spec.md), [pressure and vent](rbatch-pressure-vent.md), [continuous feed](rbatch-continuous-feed.md), [convergence](rbatch-convergence.md), [report](rbatch-report.md).

Not covered: User Subroutines (user Fortran kinetics and heat-transfer subroutines); TYPE USER-DUTY (user Fortran heat-transfer subroutine); Free water (BLKOPFREWAT) (not checked).
