# PetroFrac Hcurves: condenser, reboiler, pumparounds, strippers

Paths are under `\Data\Blocks\{name}\`.

1. `add_element` on `Subobjects\Condenser Hcurves` or `Subobjects\Reboiler Hcurves` with an ID, e.g. `1`. Condenser fields start with `CH_`, reboiler fields with `RH_`; both are keyed by the ID.

## Condenser and reboiler

| Path | Type | Purpose |
|---|---|---|
| `Input\CH_INDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the condenser curve |
| `Input\CH_NPOINTS\{id}` | int | Points on the condenser curve |
| `Input\CH_PROPERTIE\{id}\{row}` | Prop-Set ID | Extra property sets on the condenser curve (rows without labels) |
| `Input\RH_INDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the reboiler curve |
| `Input\RH_NPOINTS\{id}` | int | Points on the reboiler curve |
| `Input\RH_PROPERTIE\{id}\{row}` | Prop-Set ID | Extra property sets on the reboiler curve (rows without labels) |

## Pumparounds

`add_element` on `Subobjects\Pumparounds\{id}\Subobjects\Hcurves`; its `PA_` curve fields are keyed by the pumparound ID, then the curve ID.

| Path | Type | Purpose |
|---|---|---|
| `Input\PA_NPOINTS\{id}\{id}` | int | Points on a pumparound curve |
| `Input\PA_PROPERTIE\{id}\{id}\{row}` | Prop-Set ID | Extra property sets on that curve (rows without labels) |

## Stripper reboilers

`add_element` on `Subobjects\Strippers\{stripper}\Subobjects\Reboiler Hcurves`; its `SR_` fields are keyed by the stripper ID, then the curve ID.

| Path | Type | Purpose |
|---|---|---|
| `Input\SR_NPOINTS\{stripper}\{id}` | int | Points on a stripper reboiler curve |
| `Input\SR_PROPERTIE\{stripper}\{id}\{row}` | Prop-Set ID | Extra property sets on that curve (rows without labels) |
