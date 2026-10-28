# Heater: valid phases and free water

Phases the outlet flash looks for, and water drawn off on its own. Paths are under `\Data\Blocks\{name}\`.

## Input | Specifications (valid phases)

| Path | Type | Purpose |
|---|---|---|
| `Input\NPHASE` | `1`, `2`, `3` | Phases: one, vapor-liquid (default), or vapor-liquid-liquid |
| `Input\PHASE` | `V`, `L` | The one phase; writable once `NPHASE` is `1` |
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | `YES`: pure water leaves on `WD(OUT)`; `DIRTY`: that water keeps some dissolved organics |

`PHASE` is locked until `NPHASE` is `1`.

To leave `NPHASE` `1`, clear `PHASE` first (write `""`); otherwise the new `NPHASE` is refused.

A feed that splits into two liquids needs `NPHASE` `3`: at `2` the run ends with a phase-stability warning.

At `NPHASE` `3` the outlet holds an organic first liquid and a water-rich second liquid.

`PHASE` `L` keeps the outlet all liquid and `V` all vapor at the same 100 C and 1 atm.

Connecting a stream to `WD(OUT)` sets `BLKOPFREWAT` to `YES`; `NO` is then refused.

With `YES` nearly all the water leaves on `WD(OUT)` and none of the organics; with `DIRTY` a trace of them goes with it.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\LIQ_RATIO` | fraction | First liquid over total liquid |
| `Output\X1\{comp}` | mole fraction | First-liquid composition (`X2`: second liquid) |
