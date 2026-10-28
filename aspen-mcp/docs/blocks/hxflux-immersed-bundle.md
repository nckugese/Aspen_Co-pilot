# HXFlux: immersed tube bundle

`AREA_OPT` = `IMM-BUNDLE`: the area is the part of the bundle covered by liquid, found from a level reading, in place of `AREA`. Paths are under `\Data\Blocks\{name}\`; basics in [hxflux.md](hxflux.md).

It needs `MAX_AREA`, `SPAN`, a reading in `LEVEL_MEAS`, `BUNDLE_DIA` (horizontal) or `TUBE_LEN` (vertical), and one of `LEVEL_TOP` and `LEVEL_BOT`; the second of those two is refused.

`NUM_BUNDLES` sets the rows of `LEVEL_MEAS`: `#0`, `#1`, ... one per bundle.

## Input | Immersed Tube Bundle

| Path | Type | Purpose |
|---|---|---|
| `Input\NUM_BUNDLES` | int | Number of bundles |
| `Input\ORIENTATION` | `HORIZONTAL`, `VERTICAL` | Bundle orientation |
| `Input\BUNDLE_DIA` | LENGTH | Bundle diameter (horizontal) |
| `Input\TUBE_LEN` | LENGTH | Tube length (vertical) |
| `Input\MAX_AREA` | AREA | Area of the bundle when fully covered |
| `Input\SPAN` | LENGTH | Height that a 0 to 100 % level reading spans |
| `Input\LEVEL_TOP` | percent | Reading at which the bundle is just fully covered |
| `Input\LEVEL_BOT` | percent | Reading at which the liquid just reaches the bundle |
| `Input\LEVEL_MEAS\{row}` | percent | Measured level reading of each bundle |
| `Input\AER_PARM` | real | Aeration factor on the level (default 1) |
| `Input\A_METHOD` | `RIGOROUS`, `APPROXIMATE` | How the covered area follows from the liquid height |
| `Input\ACALC_OPT` | `COVERED`, `EXPOSED` | Area used: the part under the liquid or the part above it |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\AREA_CALC` | AREA | Area found from the level |
| `Output\QCALC` | ENTHALPY-FLO | Duty |
