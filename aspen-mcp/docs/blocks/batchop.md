# BatchOp

Batch vessel (pot) integrated over time: charged, heated or cooled, and optionally reacting, venting, fed, drawn or filtered. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `BC(IN)` batch charge, `CF(IN)` feeds during the batch, `RP(OUT)` the contents at the end, `VP(OUT)` vent, `LD(OUT)` liquid draw, `FT(OUT)` filtrate, `HS(OUT)` heat stream.

It solves only in a batch-process flowsheet: set `\Data\EO Configuration\Solve-Options\Input\PROCESS` to `BATCH`; with the default `CONTINUOUS` the run returns no results.

Time runs from 0 to `MAX_TIME` in `\Data\Convergence\Batch-Options\Input` (default 100 hr) with a profile point every `OUTPUT_INT` (default 0.01 hr): 2 hr and 0.05 hr gave 41 points.

Without `TYPE`, `FEED_TIME` (`BAT-FEED`) or `DISCHARGE_T` the block stays incomplete and the run does not start.

The charge is the `BC(IN)` flow times `FEED_TIME` (`BAT-FEED`), or `CHARGE_MOLE` / `CHARGE_MASS` of the `BC(IN)` composition (`BAT-CHARGE`); `EMPTY` starts with nothing and fills from `CF(IN)`.

`RP(OUT)` carries what is in the pot at the end divided by `DISCHARGE_T`.

`QCYCLE` is `QCALC` times the cycle: charge time (`FEED_TIME`, or the charge over the `BC(IN)` flow) + `MAX_TIME` + `DISCHARGE_T` + `DOWN_TIME`.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `T-SPEC`, `TCOOL-SPEC`, `DUTY-SPEC` | Heat spec (shortcut mode): fixed temperature, coolant temperature with U and area, or fixed duty |
| `Input\TEMP` | TEMPERATURE | Pot temperature (`T-SPEC`) |
| `Input\COO_TEMP` | TEMPERATURE | Coolant temperature (`TCOOL-SPEC`) |
| `Input\COO_U` | HEAT-TRANS-C | Coolant-side coefficient (`TCOOL-SPEC`) |
| `Input\COO_AREA` | AREA | Heat-transfer area (`TCOOL-SPEC`) |
| `Input\DUTY` | ENTHALPY-FLO | Duty added (`DUTY-SPEC`) |
| `Input\PRES_TYPE` | `CONSTANT`, `CALCULATE` | Pressure fixed, or computed from the vessel volume ([batchop-vent-pressure.md](batchop-vent-pressure.md)) |
| `Input\PRES` | PRESSURE | Pot pressure (`CONSTANT`) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the pot: one, vapor-liquid, vapor-liquid-liquid |
| `Input\PHASE` | `L`, `V` | The phase when `NPHASE` is 1 |

`PHASE` goes only with `NPHASE` 1: clear it (write `""`) before setting 2 or 3.

| Path | Type | Purpose |
|---|---|---|
| `Input\HTRANMODE` | `SHORTCUT`, `RIGOROUS` | Heat from `TYPE`, or from jacket and coils ([batchop-heat-transfer.md](batchop-heat-transfer.md)) |
| `Input\REACSYS` | `NO`, `YES` | Kinetic reactions in the pot ([batchop-reactions.md](batchop-reactions.md)) |

## Setup | Specifications: charge and times

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_TIME` | `BAT-FEED`, `BAT-CHARGE`, `EMPTY` | How the pot is charged |
| `Input\FEED_TIME` | TIME | Time the `BC(IN)` flow charges the pot (`BAT-FEED`) |
| `Input\OPT_BASIS` | `MOLE`, `MASS` | Basis of the charge amount (`BAT-CHARGE`) |
| `Input\CHARGE_MOLE` | MOLES | Charge amount (`MOLE`) |
| `Input\CHARGE_MASS` | MASS | Charge amount (`MASS`) |
| `Input\DISCHARGE_T` | TIME | Time to empty the pot after the batch |
| `Input\DOWN_TIME` | TIME | Idle time added to the cycle |
| `\Data\Convergence\Batch-Options\Input\MAX_TIME` | TIME | End time of the batch (flowsheet-wide) |
| `\Data\Convergence\Batch-Options\Input\OUTPUT_INT` | TIME | Time between profile points (flowsheet-wide) |

## Setup | Controllers (`T-SPEC`)

| Path | Type | Purpose |
|---|---|---|
| `Input\GAIN` | real | Temperature controller gain (default 2500) |
| `Input\INT_TIME` | real | Its integral time |
| `Input\DER_TIME` | real | Its derivative time |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STOP-TIME` | TIME | Time the batch ended |
| `Output\QCALC` | ENTHALPY-FLO | Heat per cycle divided by the cycle |
| `Output\QCYCLE` | ENTHALPY | Heat per cycle |
| `Output\TMIN` | TEMPERATURE | Lowest pot temperature |
| `Output\TMAX` | TEMPERATURE | Highest pot temperature |
| `Output\TIME\{pt}` | TIME | Profile: time of point `{pt}` (1, 2, ...) |
| `Output\TEMP_REAC\{pt}` | TEMPERATURE | Profile: pot temperature |
| `Output\MASS_REAC\{pt}` | MASS | Profile: pot holdup |
| `Output\MO_FRAC_REAC\{pt}\{comp}` | fraction | Profile: pot mole fraction per component |
| `Output\DUTY_INST\{pt}` | ENTHALPY-FLO | Profile: duty |

More: [reactions](batchop-reactions.md), [vent and pressure](batchop-vent-pressure.md), [feeds and draws](batchop-streams.md), [heat transfer](batchop-heat-transfer.md), [vessel geometry](batchop-geometry.md), [filtration](batchop-filtration.md), [convergence](batchop-convergence.md), [report](batchop-report.md).

Not covered: Jacket/Coils results (jacket and coil result sheets; their selector keywords are not in the tree); Transport Properties (mass transfer), Setup Mass Transfer (mass transfer (kLa): integration failed in our runs); User Subroutines (user Fortran kinetics and heat-transfer subroutines); TYPE USER-DUTY (user Fortran heat-transfer subroutine); Kinetics crystallization (CRYSTSYS) (not checked: needs a crystallization reaction set); Setup Washing and Deliquoring, Particle classification of draws and filtrate, Free water (BLKOPFREWAT) (not checked); Setup Pressure (column) (column configuration only, not checked); Pressure and vent-flow controllers (P_*, VF_*) (no effect seen in our runs); Unit procedures (operating steps) (flowsheet objects, not part of the block; a minimal one did not run).
