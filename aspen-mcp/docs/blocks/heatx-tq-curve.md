# HeatX T-Q curve and zone analysis

Paths are under `\Data\Blocks\{name}\`. Temperature profiles along the duty.

## T-Q Curve

| Path | Type | Purpose |
|---|---|---|
| `Input\CURVE` | `YES`, `NO` | Compute the T-Q curve (on by default) |
| `Input\NPOINT` | int | Points on the curve |
| `Input\PRES_PROF` | `INLET`, `OUTLET`, `IN-OUT`, `USER` | Pressure used along the curve |
| `Input\SCUT_INTVLS` | `NO`, `YES` | Interval (zone) analysis in the shortcut model |

## Results (lists, one entry per point or zone)

| Path | Type | Purpose |
|---|---|---|
| `Output\HX_FLS_HDUTY\{pt}` | ENTHALPY-FLO | Duty at a curve point (`HX_FLS_CDUTY` cold) |
| `Output\HX_FLS_HTEMP\{pt}` | TEMPERATURE | Temperature of the hot stream at that point (`HX_FLS_CTEMP` cold) |
| `Output\HX_FLS_HVFR\{pt}` | fraction | Hot vapor fraction at the point (`HX_FLS_CVFR` cold) |
| `Output\HX_ZO_Q\{zone}` | ENTHALPY-FLO | Duty of a zone |
| `Output\HX_ZO_AREA\{zone}` | AREA | Area of a zone |
| `Output\HX_ZO_CMTD\{zone}` | DELTA-T | Driving temperature difference within a zone |
