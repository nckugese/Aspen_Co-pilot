# HyCyc: user efficiency curve

`METHOD` `USER`: you give the grade efficiency (share of each particle size sent to the underflow). Paths are under `\Data\Blocks\{name}\`; basics in [hycyc.md](hycyc.md).

`CEFF` is the share of the feed solids that ends in `S(OUT)`.

Without curve rows the block is incomplete.

1. Set `METHOD` to `USER`.
2. `insert_row` on `Input\DIAM_PARTIC` once per point; each row appears in `EFFIC` too (rows `#0`, `#1`, ..., no labels).
3. Write a size in `DIAM_PARTIC\{row}` and its efficiency in `EFFIC\{row}`, smallest size first.

`FITTING` needs at least one fit set to `YES`; with several, the best one is used.

## Efficiency

| Path | Type | Purpose |
|---|---|---|
| `Input\DIAM_PARTIC\{row}` | LENGTH | Particle size of the point |
| `Input\EFFIC\{row}` | fraction | Share of that size sent to `S(OUT)` |
| `Input\INTERPOLATE` | `LINEAR`, `LIN-SPLINE`, `LOG-SPLINE`, `FITTING` | Between the points: straight lines, a spline on a linear grid, a spline on an RRSB grid, or a fitted function |
| `Input\OPT_PLITT` | `YES`, `NO` | `FITTING`: try the Plitt function |
| `Input\OPT_ROGERS` | `YES`, `NO` | `FITTING`: try the Rogers function |
| `Input\OPT_WHITEN` | `YES`, `NO` | `FITTING`: try the Whiten function |
| `Input\OPT_MOLERUS` | `YES`, `NO` | `FITTING`: try the Molerus function |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\CEFF` | fraction | Overall separation efficiency |
| `Output\BESTFIT` | int | `FITTING`: which function fitted best |
| `Output\FIT_D50` | LENGTH | `FITTING`: fitted cut size |
| `Output\FIT_ALPHA` | real | `FITTING`: fitted sharpness |
| `Output\FIT_OFFSET` | fraction | `FITTING`: fitted fines bypass |
