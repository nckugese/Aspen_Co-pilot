# Valve valid phases and flash

Phases the outlet flash looks for, free water, and the flash limits. Paths are under `\Data\Blocks\{name}\`.

## Input | Operation (valid phases, flash options)

| Path | Type | Purpose |
|---|---|---|
| `Input\NPHASE` | `1`, `2`, `3` | Phases: one, vapor-liquid (default), or vapor-liquid-liquid |
| `Input\PHASE` | `V`, `L` | The one phase; writable once `NPHASE` is `1` |
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | Free water: `YES` a pure water phase, `DIRTY` one that keeps some organics; both leave on `P(OUT)` |
| `Input\FLASH_MAXIT` | int | Flash iteration limit (default 30) |
| `Input\FLASH_TOL` | tolerance | Flash tolerance (default 1e-4) |

`PHASE` is locked until `NPHASE` is `1`.

`PHASE` `L` keeps the 80 C liquid all liquid and `V` the 200 C vapor all vapor.

A feed that splits into two liquids needs `NPHASE` `3`: at `2` the run ends with a warning, at `3` it runs clean.

With `ADIAB-FLASH` the block's `X1`, `X2` and `LIQ_RATIO` stay empty; read the phases from the product stream.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TCALC` | TEMPERATURE | Outlet temperature |
| `Output\VCALC` | fraction | Outlet vapor fraction |
