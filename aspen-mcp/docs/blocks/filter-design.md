# Filter: design

`MODE` = `DESIGN`: the block sizes the filter for a target cake. Paths are under `\Data\Blocks\{name}\`; basics in [filter.md](filter.md).

`DRUM` and `BELT` (not `BROWNELL`) need all four extra streams: wash liquid and gas on `F2(IN)`, wash filtrate and deliquoring outlet on `P2(OUT)` ([washing](filter-washing.md)); the washing target `CONTAM_REDFA` then needs a dissolved component in the feed liquid (ethanol here).

`BROWNELL` design needs `MAX_PDROP`, `RATIO` and `REVS`; Aspen refuses the model while an extra stream is connected.

The specific cake resistance sets the area: with the computed default the drum came out below 0.5 m2 and the run warned; `CAKE_RES_H` 1e14 1/m2 gave a 1.3 m drum ([filter cake](filter-cake.md)).

## Design parameters

| Path | Type | Purpose |
|---|---|---|
| `Input\CAKE_THICK` | LENGTH | Target cake thickness (3-15 mm avoids a warning) |
| `Input\CAKE_SAT` | fraction | Target cake saturation after deliquoring |
| `Input\CONTAM_REDFA` | fraction | Target ratio of contaminant left in the cake liquid after washing |
| `Input\MAX_PDROP` | PDROP | Drum: largest allowed pressure difference |
| `Input\RATIO` | ratio | Drum: width over diameter |
| `Input\MAX_FILTAREA` | fraction | Drum: largest share of the surface used for filtration |
| `Input\BELT_WIDTH` | LENGTH | Belt: belt width |
| `Input\DEAD_AFRAC` | fraction | Belt: share of the belt that does no work |
| `Input\WASH_PDROP` | PDROP | Pressure difference while washing |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\DIAM_CALC` | LENGTH | Drum diameter |
| `Output\WIDTH_CALC` | LENGTH | Drum width |
| `Output\DRUM_DEPTH_C` | LENGTH | Drum immersion depth |
| `Output\DRUM_SPEED_C` | FREQUENCY | Drum speed |
| `Output\WASH_LIQ_C` | MASS-FLOW | Wash liquid flow the washing target needs |
| `Output\BELT_LNGTH_C` | LENGTH | Belt length |
| `Output\BELT_SPEED_C` | VELOCITY | Belt speed |
