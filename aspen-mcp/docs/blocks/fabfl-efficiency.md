# FabFl: separation efficiency

`FAB-FILTER` needs a grade efficiency curve, the share of each particle size that is caught (Efficiency sheet). Paths are under `\Data\Blocks\{name}\`; basics in [fabfl.md](fabfl.md).

`IDEAL` caught all the dust; the two 500 nm presets caught 96.6 % and 98.1 % of this 0-20 um dust.

`PIECEWISE` is a built-in curve: a size table made no difference to it.

`CURVE-PARAMS`: efficiency = 1 - exp(-(a x + b / x)^c), x the particle size in nm; a 0.0001, b 1000, c 2 gave 62.8 %.

A table (`TABULAR`):

1. Add one row per point with `insert_row` on `Input\DIAM_PART`; `EFFIC` gets the same rows.
2. Fill `DIAM_PART\#i` and `EFFIC\#i` for each row, smallest size first.

Let the points span the feed's sizes: points that cover only part of the feed's size range end with out-of-bound warnings.

Without rows the run still ends with `BLKSTAT` 0, but it logs errors and all the dust leaves in `G(OUT)`.

`FITTING` needs at least one model set to `YES` (with none it falls back to `LINEAR` and warns); `BESTFIT` names the one chosen: 1 Plitt, 2 Rogers, 4 Whiten, 8 Molerus, 16 the fabric filter equation.

## Input | Efficiency

| Path | Type | Purpose |
|---|---|---|
| `Input\EFF_OPT` | `IDEAL`, `90-AT-500NM`, `95-AT-500NM`, `CURVE-PARAMS`, `PIECEWISE`, `TABULAR` | Efficiency curve; no default |
| `Input\EFF_A` | real | `CURVE-PARAMS`: a |
| `Input\EFF_B` | real | `CURVE-PARAMS`: b |
| `Input\EFF_C` | real | `CURVE-PARAMS`: c |
| `Input\DIAM_PART\{row}` | LENGTH | `TABULAR`: particle size of the point |
| `Input\EFFIC\{row}` | fraction | `TABULAR`: share of that size caught |
| `Input\INTERPOLATE` | `LINEAR`, `LIN-SPLINE`, `LOG-SPLINE`, `FITTING` | `TABULAR`: between the points use straight lines (default), a spline, a spline on a log size grid, or a fitted model |
| `Input\OPT_PLITT` | `NO`, `YES` | `FITTING`: try the Plitt curve |
| `Input\OPT_ROGERS` | `NO`, `YES` | `FITTING`: try the Rogers curve |
| `Input\OPT_WHITEN` | `NO`, `YES` | `FITTING`: try the Whiten curve |
| `Input\OPT_MOLERUS` | `NO`, `YES` | `FITTING`: try the Molerus curve |
| `Input\OPT_FABFLEXP` | `NO`, `YES` | `FITTING`: try the fabric filter equation |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EFF` | fraction | Share of the feed dust caught |
| `Output\COARSE_D50` | LENGTH | Median size of the dust in `S(OUT)` (`FINES_D50`: in `G(OUT)`) |
| `Output\FIT_D50` | LENGTH | `FITTING`: cut size of the fitted curve |
| `Output\BESTFIT` | int | `FITTING`: model chosen |
