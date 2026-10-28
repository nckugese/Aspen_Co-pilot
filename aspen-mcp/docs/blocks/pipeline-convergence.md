# Pipeline convergence

Paths are under `\Data\Blocks\{name}\` (form Convergence). Fluid flow with `INTEGRATION=YES` only.

## Integration

| Path | Type | Purpose |
|---|---|---|
| `Input\HINIT` | real | Initial step size |
| `Input\INT_TOL` | real | Integration / corrector tolerance |
| `Input\INTERR` | PRESSURE | Allowed error per step (`INT_METHOD=HAMMING`) |
| `Input\CORR_METHOD` | `NEWTON`, `DIRECT` | How the corrector converges |
| `Input\CORR_TOL_RAT` | real | Corrector tolerance as a multiple of `INT_TOL` |
| `Input\P_RECOV` | `YES`, `NO` | Count the elevation pressure gain on downhill runs, or set it to zero |
| `Input\DOWNHILL_MIN` | ANGLE | Slope range treated as downhill: lower bound (`DOWNHILL_MAX` upper) |

## Correlation options

| Path | Type | Purpose |
|---|---|---|
| `Input\SLIP` | `YES`, `NO` | Gas and liquid move at different speeds, or holdup = flowing liquid fraction (the holdup correlations are then unused) |
| `Input\MINVOL` | real | Smallest phase volume fraction treated as two-phase |
| `Input\ORKWLR` | real | Water / liquid ratio above which water is the second liquid |
| `Input\NIKLIN` | `NO`, `YES` | Niklin bubble-rise velocity in the Orkiszewski method |
| `Input\ORKDEN_KEY` | `NO`, `YES` | Modified gas density in the Orkiszewski method |
| `Input\REYN_TRAN` | real | Reynolds number of the laminar-turbulent switch |
| `Input\MAX_WARN` | int | Most warnings printed |

## Beggs-Brill coefficients

| Path | Type | Purpose |
|---|---|---|
| `Input\BB1` | real | Coefficients `BB1` to `BB10` of the Beggs-Brill holdup correlation; blank = built-in |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\B_PRES_OUT` | PRESSURE | Outlet pressure |
| `Output\HOLDUP_OUT2` | VOLUME | Liquid volume held in the line |
