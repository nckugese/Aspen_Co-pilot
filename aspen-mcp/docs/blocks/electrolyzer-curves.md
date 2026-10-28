# Electrolyzer: performance curves

`MODEL_TYPE` `CURVES` reads the cell (or stack) voltage from measured voltage versus current-density curves. Paths are under `\Data\Blocks\{name}\`; setup in [electrolyzer.md](electrolyzer.md).

1. Set `MODEL_TYPE` `CURVES` and `ACTUAL_AREA` (area of one cell).
2. Write the curve count to `CV_NCURVES`: it creates curve rows `1`, `2`, ... in every `CV_` table.
3. Insert point rows on `CV_CRDN\{curve}` (labels `1`, `2`, ...); `CV_VOLTG\{curve}` gets the same rows.
4. Fill the points and the curve's reference temperature and pressure, and mark it active.

A curve needs at least 4 points: with 3 the input stays incomplete.

## Performance Curves | Setup

| Path | Type | Purpose |
|---|---|---|
| `Input\CURVE_TYPE` | `CELLV-CRDNS`, `STCKV-CRDNS` | Curves give cell volts (`CV_` tables) or stack volts (`SV_` tables) |
| `Input\CV_NCURVES` | int | Number of curves (`SV_NCURVES` for stack volts) |
| `Input\CV_CRDN\{curve}\{pt}` | CURRENT-DENS | Current density of a point |
| `Input\CV_VOLTG\{curve}\{pt}` | VOLTAGE | Cell voltage of that point |
| `Input\CV_REF_TEMP\{curve}` | TEMPERATURE | Temperature the curve was measured at |
| `Input\CV_REF_PRES\{curve}` | PRESSURE | Pressure the curve was measured at |
| `Input\CV_ACTIVECUR\{curve}` | `YES`, `NO` | Use this curve |
| `Input\CELLV_OFF` | VOLTAGE | Offset added to the cell voltages (`STCKV_OFF` for stack curves) |
| `Input\SHOW_PLOTS` | `YES`, `NO` | Plot the curves in the GUI |

| Path | Type | Purpose |
|---|---|---|
| `Output\ELEC-POWER` | ELEC-POWER | Power drawn |
