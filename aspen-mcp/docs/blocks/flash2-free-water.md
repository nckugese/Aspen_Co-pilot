# Flash2: free water

A separate water phase sent to its own outlet. Paths are under `\Data\Blocks\{name}\`.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | `NO` no free water; `YES` the water phase is pure water; `DIRTY` it carries dissolved organics |

Connecting a stream to `WD(OUT)` sets `BLKOPFREWAT` to `YES`; removing it sets `NO`.

With `YES` the water phase leaves on `WD(OUT)` and `L(OUT)` keeps only the water dissolved in the organic liquid.

With `YES` and no stream on `WD(OUT)`, the water stays in `L(OUT)`.

With `DIRTY` the stream on `WD(OUT)` also holds some benzene.

Free water works only with `NPHASE` 2: writing `NPHASE` 3 is refused while `BLKOPFREWAT` is `YES`. For a full liquid-liquid split use `NO` with `NPHASE` 3.
