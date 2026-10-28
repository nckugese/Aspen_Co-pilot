# Filter: filter cake

Cake and cloth properties of the rated types (not `SOLIDS-SEP`). Blank resistances are computed from the particles. Paths are under `\Data\Blocks\{name}\`; basics in [filter.md](filter.md).

## Cake

| Path | Type | Purpose |
|---|---|---|
| `Input\CAKE_RES_H` | INVERSE-AREA | Specific cake resistance, computed when blank |
| `Input\POROSITY` | fraction | Cake porosity (default 0.45) |
| `Input\SPHERICITY` | fraction | Mean particle sphericity (default 0.75) |
| `Input\DIAM_PART` | LENGTH | Mean particle size, from the feed size distribution when blank |

## Compressibility

| Path | Type | Purpose |
|---|---|---|
| `Input\COMP_MODEL` | `INCOMP`, `COMP-A`, `COMP-B` | Cake model: incompressible, or one of two compressible forms |
| `Input\COMPRES` | real | `INCOMP`: compressibility exponent (default 0) |

`COMP-A` needs `COMPA_KA`, `COMPA_NA`, `COMPA_KE`, `COMPA_NE`; `COMP-B` needs `COMPB_KA`, `COMPB_NA`, `COMPB_KC`, `COMPB_NC`, `COMPB_PBA`, `COMPB_PBC`.

| Path | Type | Purpose |
|---|---|---|
| `Input\COMPA_KA` | real | `COMP-A`: resistance factor |
| `Input\COMPA_NA` | real | `COMP-A`: resistance exponent |
| `Input\COMPA_KE` | real | `COMP-A`: porosity factor |
| `Input\COMPA_NE` | real | `COMP-A`: porosity exponent, below 1 |
| `Input\COMPB_KA` | SPEC-FLT-RES | `COMP-B`: resistance factor |
| `Input\COMPB_PBA` | PRESSURE | `COMP-B`: reference pressure of the resistance law |
| `Input\MAT_LAW_FORM` | `MEAN`, `LOCAL` | Compressible laws applied to cake averages or locally |

## Retention by the cloth

1. Insert a row into `Input\LOWER` (`insert_row`); `UPPER` and `RET_FRAC` get the same row `#0`.
2. Write the size interval and the share of those particles the cloth holds back.

| Path | Type | Purpose |
|---|---|---|
| `Input\LOWER\{row}` | LENGTH | Lower size of the interval |
| `Input\UPPER\{row}` | LENGTH | Upper size of the interval |
| `Input\RET_FRAC\{row}` | fraction | Share of those particles kept in the cake |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\POROSITY_C` | fraction | Mean cake porosity |
| `Output\DIAM_PART_C` | LENGTH | Mean particle size used |
