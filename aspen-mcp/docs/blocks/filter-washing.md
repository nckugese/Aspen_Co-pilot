# Filter: washing and extra streams

Displacing the mother liquor with wash liquid, shown on `DRUM`. Paths are under `\Data\Blocks\{name}\`; basics in [filter.md](filter.md).

1. Connect the wash liquid to `F2(IN)` and a wash filtrate stream to `P2(OUT)`; one without the other is refused.
2. Give each stream its type: `FEED_TYPE\<stream>` `WASH-IN` (or `GAS-IN` for deliquoring gas), `PRODUCT_TYPE\<stream>` `WASH-OUT` (or `DEQ-OUT`); untyped, the block stays incomplete.

With a wash stream the drum needs `WASH_PDROP` and, for `CHOUDHURY`, `WASH_EFF`.

Give the gas inlet and deliquoring outlet as well: with wash alone the run can end with a cake-evaporation warning.

On a belt keep `WASH_PDROP` below `DELIQ_PDROP` (for example 0.2 against 0.6 bar): with both equal the cake drains while it is washed, the deliquoring zone gets no liquid and the run warns.

## Streams

Each type can be given to one stream only.

| Path | Type | Purpose |
|---|---|---|
| `Input\FEED_TYPE\{stream}` | `WASH-IN`, `GAS-IN` | Role of a stream on `F2(IN)` |
| `Input\PRODUCT_TYPE\{stream}` | `WASH-OUT`, `DEQ-OUT` | Role of a stream on `P2(OUT)` |

## Washing

| Path | Type | Purpose |
|---|---|---|
| `Input\WASH_ANGLE` | ANGLE | Drum: angle used for washing |
| `Input\WASH_PDROP` | PDROP | Pressure difference while washing |
| `Input\WASH_AFRAC` | fraction | Belt: share of the belt used for washing |
| `Input\WASH_MODEL` | `CHOUDHURY`, `DISPERSION` | Wash curve: a wash efficiency, or axial dispersion |
| `Input\WASH_EFF` | fraction | `CHOUDHURY`: wash efficiency |
| `Input\DIFFUSIVITY` | DIFFUSIVITY | `DISPERSION`: molecular diffusivity of the contaminant |
| `Input\WASH_FLOWDIR` | `COCURRENT`, `COUNTERCURRE` | Wash liquid through the zones in or against the cake direction |
| `Input\NWASH` | int | Count of washing zones (default 1) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\WASH_RATIO` | ratio | Wash liquid over liquid held in the cake |
| `Output\EFF_WAREA1` | fraction | Effective wash area of zone 1 (`EFF_WAREA2`, `3` likewise) |
