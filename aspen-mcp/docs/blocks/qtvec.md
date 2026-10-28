# QTVec

Builds a load stream, a heat stream that carries a heating or cooling curve (temperature and duty point by point), from heat streams or from one load stream, and sets where the curve starts. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `HS(IN)` heat streams, `LS(IN)` one load stream, `LS(OUT)` the outlet load stream; material streams are refused. Feed it two or more heat streams, or one load stream: a single heat stream gives a broken curve (one real point, the rest at -273.15 C).

## Load streams (Setup | Stream Class)

The streams on `LS(IN)` and `LS(OUT)` are heat streams placed in the LOAD class, in this order:

1. Create each one with `add_element` on `\Data\Streams` as `<id>!HEAT`.
2. `insert_row` on `\Data\Flowsheet\Def-Streams\Input\H_SCLASS` (row 0), then set `H_SCLASS\#0` to `LOAD` (once per flowsheet).
3. Per load stream: `insert_row` on `...\Def-Streams\Input\H_SLIST\#0` and set the new row (`#0`, `#1`, ...) to the stream ID.

The stream's own `Input\H_SCLASS` = `LOAD` is not enough (it stays a heat stream, `NPOINT` is refused). An outlet left in the heat class ends the run with no run status and no block results.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SIDE` | `HOT`, `COLD` | HOT: temperature falls along the curve, duties positive; COLD: it rises, duties negative |
| `Input\OPT_SPEC` | `TEMPSPEC`, `DELTSPEC` | How the first point is placed |
| `Input\TEMP` | TEMPERATURE | TEMPSPEC: temperature of the first point |
| `Input\DELT` | DELTA-T | DELTSPEC: second point minus first point (below 0 for HOT, above 0 for COLD) |

Heat streams merge into one composite curve sorted by temperature: overlaps add their duties, gaps stay flat, and only the first point moves. For example, one curve of 160, 100, 90, 60 C with 150, 50, 50, 0 kW (each duty is what remains to the end); two streams of 150-100 C (100 kW) and 120-80 C (50 kW) merge into 150, 120, 100, 80 C with 150, 90, 25, 0 kW.

COLD side: heat streams have negative duty with `TEMP` below `TEND`; TEMPSPEC 40 C gives 40, 100, 110, 130 C with -150, -50, -50, 0 kW.

DELTSPEC places the first point from the second: -20 on the base streams starts at 120 C, 20 on the cold ones at 80 C, -20 on the load stream below at 190 C.

Two streams sharing an end temperature (one ends at 100 C, the next starts there) leave a spare last point at -273.15 C, and the outlet's `TEND` then reads -273.15 C.

## Heat stream inlets

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Input\DUTY` | ENTHALPY-FLO | Duty: positive for HOT (TEMP above TEND), negative for COLD |
| `\Data\Streams\{stream}\Input\TEMP` | TEMPERATURE | Start temperature |
| `\Data\Streams\{stream}\Input\TEND` | TEMPERATURE | End temperature |

## Load stream inlet

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Input\NPOINT` | int | Points on the curve, 2 or more; creates cells `1`..`n` under TVEC and QVEC |
| `\Data\Streams\{stream}\Input\TVEC\{n}` | real | Temperature of point n |
| `\Data\Streams\{stream}\Input\QVEC\{n}` | real | Duty from point n to the end; the last cell is forced to 0 |

Write the cells as plain numbers in the stream's unit set (METCBAR: C and cal/sec). A QVEC written with a unit reads back in it, but the run then misreads it: 100 kW became 23,885 kW.

With TEMPSPEC 210 C the load stream's first point moves from 200 to 210 C; the other points pass unchanged.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\QCALC` | ENTHALPY-FLO | Outlet load stream: total duty |
| `\Data\Streams\{stream}\Output\TBEGIN` | TEMPERATURE | Outlet load stream: first point |
| `\Data\Streams\{stream}\Output\TEND` | TEMPERATURE | Outlet load stream: last point |
| `Output\BAL_ENTH_OUT` | ENTHALPY-FLO | Duty leaving the block |

The point-by-point curve is not in the tree (the outlet's `Output` has only the three values above); it is printed in the run report's stream section.

Not covered: none.
