# RCSTR catalyst

Paths are under `\Data\Blocks\{name}\`. A catalyst charge for rates written per catalyst mass.

The fluid holds only the voids: the run gave a liquid volume of `BED_VOIDAGE` x volume. With `IGN_CAT_VOL` = `YES` the fluid fills the whole volume.

## Setup | Catalyst

| Path | Type | Purpose |
|---|---|---|
| `Input\CAT_PRESENT` | `YES`, `NO` | The reactor holds catalyst |
| `Input\CATWT` | MASS | Catalyst mass |
| `Input\CAT_RHO` | DENSITY | Catalyst particle density |
| `Input\BED_VOIDAGE` | fraction | Void share of the bed |
| `Input\IGN_CAT_VOL` | `NO`, `YES` | Leave the catalyst out of the volume balance |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\LIQ_VOL` | VOLUME | Liquid volume left for the fluid |
