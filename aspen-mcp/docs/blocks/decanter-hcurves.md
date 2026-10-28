# Decanter: heating curves

Property tables along the path from the feed to the outlet. Paths are under `\Data\Blocks\{name}\`.

1. `add_element` on `Subobjects\Hcurves` with an ID, e.g. `1`; the curve's fields are keyed by that ID.

| Path | Type | Purpose |
|---|---|---|
| `Input\INDEP_VAR\{id}` | `DUTY`, `TEMP` | Variable stepped along the curve |
| `Input\OPT_RANGE\{id}` | `NPOINT`, `INCREMENT`, `LIST` | Points by count, by step size or as a list |
| `Input\NPOINT\{id}` | int | Number of intervals (`NPOINT`) |
| `Input\INCR\{id}` | number | Step size (`INCREMENT`), in the stepped variable's units |
| `Input\LIST\{id}\{row}` | number | Listed values (`LIST`): `insert_row`, then write each value |
| `Input\PROPERTIES\{id}\{row}` | Prop-Set ID | Extra property sets reported along the curve (rows without labels) |

Stepped in `TEMP`, the curve runs from the feed temperature to the outlet temperature.

With `INCREMENT` 5 or `LIST` 30, 35 the points fall on those temperatures.

`Output\Prop Data\HCURVE\{id}` holds the points as a table, one row per quantity plus one per property-set property.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TEMP_OUT\{id}\{pt}` | TEMPERATURE | Temperature at curve point `{pt}` (1, 2, ...) |
| `Output\DUTY_OUT\{id}\{pt}` | ENTHALPY-FLO | Duty at the point |
| `Output\PRES_OUT\{id}\{pt}` | PRESSURE | Pressure there |
