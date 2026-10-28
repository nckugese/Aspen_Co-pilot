# Screen: selection function

`MODEL` = `USER-SPEC`: a table gives, per particle size, the share that stays on the deck. Paths are under `\Data\Blocks\{name}\`; basics in [screen.md](screen.md).

1. Set `MODEL\1` = `USER-SPEC` and `DECK_OPENING\1`.
2. Insert one row per point into `SIZE2` (`insert_row`); `VALUE2` gets the same row `#n`. The block stays incomplete without a row.
3. Write each point.

A value is the share of particles of that size sent to `O(OUT)`: a flat 0.99 table sends 99 % of the solids there.

## Table

| Path | Type | Purpose |
|---|---|---|
| `Input\SIZE2\{row}` | LENGTH | Particle size of the point |
| `Input\VALUE2\{row}` | fraction | Share of particles of that size kept on the deck |
| `Input\INTERPOLATE` | `LINEAR` | Between the points: linear (default) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\DECK_OVEF\1` | fraction | Oversize efficiency of the deck |
| `Output\COARSE_D50\1` | LENGTH | Median particle size in `O(OUT)` |
