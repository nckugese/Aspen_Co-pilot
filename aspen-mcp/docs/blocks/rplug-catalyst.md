# RPlug catalyst

Paths are under `\Data\Blocks\{name}\`. A packed catalyst bed in the tube.

Give `BED_VOIDAGE` or `CATWT`. The fluid gets only the voids: the residence time falls by the void share; `IGN_CAT_VOL` = `YES` gives it the whole tube again.

The particle density is `CAT_RHO`; the similar `RHO_CAT` does not complete the input.

## Setup | Catalyst

| Path | Type | Purpose |
|---|---|---|
| `Input\CAT_PRESENT` | `NO`, `YES` | The tube holds catalyst |
| `Input\BED_VOIDAGE` | fraction | Void share of the bed |
| `Input\CATWT` | MASS | Catalyst mass (instead of `BED_VOIDAGE`) |
| `Input\CAT_RHO` | DENSITY | Particle density |
| `Input\DIA_PART` | LENGTH | Particle diameter (bed pressure drop) |
| `Input\SPHERICITY` | real | Particle sphericity |
| `Input\IGN_CAT_VOL` | `NO`, `YES` | Leave the catalyst out of the volume and residence time |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\RES_TIME` | TIME | Time the fluid spends in the bed voids |
| `Output\B_PRES\MIXED\{id}` | PRESSURE | Pressure profile through the bed |
