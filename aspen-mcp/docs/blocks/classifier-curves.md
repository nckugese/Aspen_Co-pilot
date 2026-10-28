# Classifier: efficiency tables

`METHOD` = `DATA`: a table gives, per particle size, velocity or density, the share that goes to `S(OUT)`. Paths are under `\Data\Blocks\{name}\`; basics in [classifier.md](classifier.md).

1. Set `METHOD` = `DATA` and `CLASS_CHAR`; the table that matches it is used: `SIZE`/`GEFF`, `GEFFVEL`/`VEL_EFF` or `GEFFDEN`/`DEN_EFF`.
2. Insert one row per point into the first list (`insert_row`); the efficiency list gets the same row `#n`.
3. Write each point. At least two points are needed: with one the block stays incomplete.

## Tables

| Path | Type | Purpose |
|---|---|---|
| `Input\SIZE\{row}` | LENGTH | Particle size of the point |
| `Input\GEFF\{row}` | fraction | Share of particles of that size sent to `S(OUT)` |
| `Input\GEFFVEL\{row}` | VELOCITY | Settling velocity of the point |
| `Input\VEL_EFF\{row}` | fraction | Share sent to `S(OUT)` at that velocity |
| `Input\GEFFDEN\{row}` | DENSITY | Particle density of the point |
| `Input\DEN_EFF\{row}` | fraction | Share sent to `S(OUT)` at that density |

## Between the points

| Path | Type | Purpose |
|---|---|---|
| `Input\INTERPOLATE` | `LINEAR`, `LIN-SPLINE`, `LOG-SPLINE`, `FITTING` | Linear, spline on a linear or an RRSB grid, or a fitted correlation |
| `Input\OPT_ROGERS` | `NO`, `YES` | `FITTING`: try the Rogers correlation |
| `Input\OPT_PLITT` | `NO`, `YES` | `FITTING`: try the Plitt correlation |
| `Input\OPT_MOLERUS` | `NO`, `YES` | `FITTING`: try the Molerus correlation |

With several correlations on, the block keeps the one that fits the table best and reports it in `BESTFIT`.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BESTFIT` | int | Code of the correlation used |
| `Output\FIT_D50` | LENGTH | Cut size of the fitted curve |
| `Output\FIT_ALPHA` | real | Sharpness parameter of the fitted curve |
| `Output\FIT_OFFSET` | fraction | Fines bypass of the fitted curve |
