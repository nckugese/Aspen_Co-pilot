# RadFrac condenser and reboiler curves

Paths are under `\Data\Blocks\{name}\`. Curves of the condenser and of the reboiler.

1. `add_element` on `Subobjects\Condenser Hcurves` or `Subobjects\Reboiler Hcurves` with an ID, e.g. `1`. Condenser fields start with `CH_`, reboiler fields with `RH_`; both are keyed by the ID.

| Path | Type | Purpose |
|---|---|---|
| `Input\CH_INDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the condenser curve |
| `Input\CH_NPOINTS\{id}` | int | Points on the condenser curve |
| `Input\CH_PDROP\{id}` | PDROP | Pressure change along the condenser curve |
| `Input\CH_PROPERTIE\{id}\{row}` | ID | Extra property sets on the condenser curve (rows without labels) |
| `Input\RH_INDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the reboiler curve |
| `Input\RH_NPOINTS\{id}` | int | Points on the reboiler curve |
| `Input\RH_PROPERTIE\{id}\{row}` | ID | Extra property sets on the reboiler curve (rows without labels) |
