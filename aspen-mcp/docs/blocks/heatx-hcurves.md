# HeatX heating curves

Paths are under `\Data\Blocks\{name}\`. Property curves of the hot and the cold side.

1. `add_element` on `Subobjects\Hot Hcurves` or `Subobjects\Cold Hcurves` with an ID, e.g. `1`. Hot fields start with `H`, cold fields with `C`; both are keyed by the ID.

| Path | Type | Purpose |
|---|---|---|
| `Input\HINDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the hot curve |
| `Input\HNPOINT\{id}` | int | Points on the hot curve |
| `Input\HPDROP\{id}` | PDROP | Pressure change along the hot curve |
| `Input\HPROPERTIES\{id}\{row}` | Prop-Set ID | Extra property sets on the hot curve (rows without labels) |
| `Input\CINDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the cold curve |
| `Input\CNPOINT\{id}` | int | Points on the cold curve |
| `Input\CPROPERTIES\{id}\{row}` | Prop-Set ID | Extra property sets on the cold curve (rows without labels) |
