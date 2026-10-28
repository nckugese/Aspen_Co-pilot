# Flash3: key component

Picks which liquid leaves on `L2(OUT)`. Paths are under `\Data\Blocks\{name}\`.

## Input | Key Components

| Path | Type | Purpose |
|---|---|---|
| `Input\L2_COMP` | component ID | Key component: the liquid richest in it leaves on `L2(OUT)` |

With `L2_COMP` `BENZENE` the organic liquid leaves on `L2(OUT)` and the water-rich one on `L1(OUT)`; with `WATER` it is the other way round.

Left empty, the block chooses which liquid is `L2` itself (for an organic-water feed, possibly the water-rich one): set `L2_COMP` when the assignment matters.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\LIQ_RATIO` | fraction | First liquid over total liquid (molar) |
| `Output\X2\{comp}` | mole fraction | Second-liquid composition |
