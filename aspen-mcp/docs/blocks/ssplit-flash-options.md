# SSplit: flash options

Outlet pressure and the phases the outlets are flashed for, at the feed enthalpy. Paths are under `\Data\Blocks\{name}\`.

## Input | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES` | PRESSURE | Outlet pressure when above zero; pressure drop when zero or below |
| `Input\NPHASE` | `1`, `2`, `3` | Phases checked: one, vapor-liquid (default) or vapor-liquid-liquid |
| `Input\PHASE` | `V`, `L`, `S` | The one phase; writable once `NPHASE` is `1` |
| `Input\MAXIT` | int | Flash iteration limit |
| `Input\TOL` | tolerance | Flash tolerance |
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | Water handling in the flash: none, a separate free-water phase, or dirty water |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\PRES_OUT\{substream}` | PRESSURE | Outlet pressure (the block reports none; read an outlet stream) |
