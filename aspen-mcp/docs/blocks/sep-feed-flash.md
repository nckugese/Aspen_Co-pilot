# Sep: feed flash

Pressure and phases of the flash of the combined feed. Paths are under `\Data\Blocks\{name}\`.

Outlets with no outlet-flash row ([sep-outlet-flash.md](sep-outlet-flash.md)) leave at the feed-flash temperature and pressure.

## Input | Feed Flash

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES1` | PRESSURE | Flash pressure when above zero; pressure drop from the feed when zero or below |
| `Input\NPHASE1` | `1`, `2`, `3` | Phases checked: one, vapor-liquid (default), or vapor-liquid-liquid |
| `Input\PHASE1` | `V`, `L` | The one phase; writable once `NPHASE1` is `1` |
| `Input\MAXIT1` | int | Flash iteration limit |
| `Input\TOL1` | tolerance | Flash tolerance |
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | Free water: `YES` water as its own phase, `DIRTY` that phase with dissolved organics |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STREAM_PRES\{stream}` | PRESSURE | Outlet pressure (the flash pressure) |
