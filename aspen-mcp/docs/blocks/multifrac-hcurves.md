# MultiFrac heating curves

Paths are under `\Data\Blocks\{name}\`. Curves of a column's condenser, a column's reboiler, or a connect stream that is heated or cooled.

1. `add_element` on `Subobjects\Condenser Hcurves`, `Reboiler Hcurves` or `Connect Stream Hcurves` with an ID (`1`); condenser fields start with `CH_`, reboiler fields with `RH_`, connect-stream fields with `ICHTR_`.

| Path | Type | Purpose |
|---|---|---|
| `Input\CH_COL\{id}` | int | Column whose condenser is drawn |
| `Input\RH_COL\{id}` | int | Column whose reboiler is drawn |
| `Input\ICHTR_STRM\{id}` | int | Connect stream drawn |
| `Input\CH_INDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the curve (`RH_INDEP_VAR`, `ICHTR_INDVAR`) |
| `Input\CH_NPOINTS\{id}` | int | Points on the curve (`RH_NPOINTS`) |
| `Input\CH_PROPERTIE\{id}\{row}` | ID | Extra property sets on a condenser curve (rows without labels) |
| `Input\RH_PROPERTIE\{id}\{row}` | ID | The same for a reboiler curve |
| `Input\ICHTR_PROPER\{id}\{row}` | ID | The same for a connect-stream curve |
