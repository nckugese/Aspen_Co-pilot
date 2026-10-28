# Flash3: heating curves

Property tables along the path from the feed to the flash outlet. Paths are under `\Data\Blocks\{name}\`.

1. `add_element` on `Subobjects\Hcurves` with an ID, e.g. `1`; the curve's fields are keyed by that ID.

| Path | Type | Purpose |
|---|---|---|
| `Input\INDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the curve |
| `Input\OPT_RANGE\{id}` | `NPOINT`, `INCREMENT`, `LIST` | Points by count, by step size or as a list |
| `Input\NPOINTS\{id}` | int | Number of intervals (`NPOINT`) |
| `Input\INCR\{id}` | number | Step size (`INCREMENT`), in the stepped variable's units |
| `Input\LISTS\{id}\{row}` | number | Listed values (`LIST`): `insert_row`, then write each value |
| `Input\PROPERTIES\{id}\{row}` | Prop-Set ID | Extra property sets reported along the curve (rows without labels) |

Stepped in `TEMP`, the curve runs from the feed temperature to the flash temperature; the phase-change point is added.

With `INCREMENT` 2 or `LIST` 60, 70, 80 the points fall on those temperatures.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TEMP_OUT\{id}\{pt}` | TEMPERATURE | Temperature at curve point `{pt}` (1, 2, ...) |
| `Output\DUTY_OUT\{id}\{pt}` | ENTHALPY-FLO | Duty at the point |
| `Output\VFRAC_OUT\{id}\{pt}` | fraction | Vapor fraction at the point |
| `Output\PRES_OUT\{id}\{pt}` | PRESSURE | Pressure there |

`Output\Prop Data\HCURVE\{id}` holds the same points as a table: one row per quantity (`DUTY`, `PRES`, `TEMP`, `VFRAC`) plus one per property-set property, e.g. `TOTAL RHOMX`.
