# Decanter: solid entrainment

Where solids in the feed go. Paths are under `\Data\Blocks\{name}\`.

## Input | Entrainment

| Path | Type | Purpose |
|---|---|---|
| `Input\LIQUID1\{substream}` | fraction | Share of the solid substream sent to `L1(OUT)`; an entry exists per solid substream (none without one) |

Left empty, all solids leave on `L2(OUT)`; 0.3 sent 3 of 10 kmol/hr to `L1(OUT)` and the rest to `L2(OUT)`.
