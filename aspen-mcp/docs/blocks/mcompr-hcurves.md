# MCompr cooler heating curves

Paths are under `\Data\Blocks\{name}\`; `{id}` is the heating-curve ID. Base setup as in [mcompr.md](mcompr.md).

1. `add_element` on `\Data\Blocks\{name}\Subobjects\Hcurves` with an ID (e.g. `1`); the ID gets a row in every field below.
2. Set `HC_STG\{id}` to the stage whose cooler is traced; the rest is optional.

## Heating Curves | Setup

| Path | Type | Purpose |
|---|---|---|
| `Input\HC_STG\{id}` | int | Stage whose cooler the curve follows |
| `Input\INDEP_VAR\{id}` | `DUTY`, `TEMP`, `VFRAC` | Variable stepped along the curve |
| `Input\OPT_RANGE\{id}` | `NPOINT`, `INCREMENT`, `LIST` | Points by count, by step size, or as a list |
| `Input\NPOINTS\{id}` | int | Number of intervals (default 10) |
| `Input\PRES_PROFILE\{id}` | `CONSTANT`, `LINEAR`, `OUTLET`, `INLET`, `MID-POINT` | Pressure along the curve |
| `Input\PDROPS\{id}` | PDROP | Drop applied along the curve by the pressure profile |

## Heating Curves | Additional Properties

| Path | Type | Purpose |
|---|---|---|
| `Input\PROPERTIES\{id}\{row}` | property-set ID | Extra property sets tabulated along the curve |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\Prop Data\HCURVE\{id}\TEMP\{pt}` | TEMPERATURE | Temperature at each point (1 to NPOINTS+2) |
| `Output\Prop Data\HCURVE\{id}\DUTY\{pt}` | ENTHALPY-FLO | Duty from the cooler inlet |
| `Output\Prop Data\HCURVE\{id}\VFRAC\{pt}` | fraction | Vapor fraction |
| `Output\Prop Data\HCURVE\{id}\PRES\{pt}` | PRESSURE | Pressure |
