# CFuge: perforated basket

`TYPE` = `PERF-BASKET`. Each basket row is one candidate machine; the block uses the best one. Paths are under `\Data\Blocks\{name}\`; basics in [cfuge.md](cfuge.md).

1. Insert a row into `Input\DIAM` (`insert_row`); `REVS` gets the same row `#0`.
2. Write `DIAM\#0` and `REVS\#0`; more rows add more candidates.

## Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\DIAM\{row}` | LENGTH | Basket diameter |
| `Input\REVS\{row}` | FREQUENCY | Basket speed |
| `Input\HEIGHT` | ratio | Basket height over its radius |
| `Input\CAKE` | ratio | Radius of the cake surface over the basket radius |
| `Input\LIQUID` | ratio | Radius of the liquid surface over the basket radius |

## Solids cake

| Path | Type | Purpose |
|---|---|---|
| `Input\MEDIUM_RES` | FILTER-RESIS | Resistance of the filter cloth (required) |
| `Input\CAKE_RES` | SPEC-FLT-RES | Specific cake resistance, computed when blank |
| `Input\DIAM_PART` | LENGTH | Mean particle size in the cake, from the feed PSD when blank |
| `Input\POROSITY` | fraction | Cake porosity |
| `Input\SPHERICITY` | fraction | Mean particle sphericity |

## Deliquoring

| Path | Type | Purpose |
|---|---|---|
| `Input\BASKET_DELIQ` | `SPEC-RM`, `ESTIM-RM` | Cake moisture: given as `WETNESS`, or estimated from the cake |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\SPEED` | FREQUENCY | Speed of the chosen basket |
| `Output\PART_DIAMR` | LENGTH | Mean particle size used for the cake |
