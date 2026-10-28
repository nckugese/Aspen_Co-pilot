# MHeatX heating curves

Paths are under `\Data\Blocks\{name}\`. Property curves of one stream through the exchanger.

1. `add_element` on `Subobjects\Hcurves` with an ID, e.g. `1`; its fields are keyed by that ID.
2. Name the stream in `SID\{id}` (an inlet ID).

| Path | Type | Purpose |
|---|---|---|
| `Input\SID\{id}` | inlet stream ID | Stream the curve follows |
| `Input\INDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the curve |
| `Input\OPT_RANGE\{id}` | `NPOINT`, `INCREMENT`, `LIST` | Steps by a point count, an increment or a list |
| `Input\HNPOINT\{id}` | int | Number of points |
| `Input\INCR\{id}` | number | Step size with `INCREMENT` |
| `Input\PRES_PROFILE\{id}` | `CONSTANT`, `LINEAR`, `OUTLET`, `INLET`, `MID-POINT` | Pressure along the curve |
| `Input\PDROP\{id}` | PDROP | Pressure loss the profile spreads over the curve |
| `Input\PROPERTIES\{id}\{row}` | Prop-Set ID | Extra property sets (rows without labels) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\TEMP_OUT\{id}\{stream}\{pt}` | TEMPERATURE | Temperature at a curve point |
| `Output\DUTY_OUT\{id}\{stream}\{pt}` | ENTHALPY-FLO | Duty at the point |
| `Output\VFRAC_OUT\{id}\{stream}\{pt}` | fraction | Vapor fraction at the point |
