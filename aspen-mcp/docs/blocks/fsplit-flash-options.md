# FSplit: flash options

Pressure and the phases of the outlets; the outlets are flashed at the feed enthalpy. Paths are under `\Data\Blocks\{name}\`.

## Input | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES1` | PRESSURE | Outlet pressure when above zero; pressure drop when zero or below |
| `Input\NPHASE1` | `1`, `2`, `3` | Phases checked: one, vapor-liquid (default), or vapor-liquid-liquid |
| `Input\PHASE1` | `V`, `L` | The one phase; writable once `NPHASE1` is `1` |
| `Input\MAXIT1` | int | Flash iteration limit |
| `Input\TOL1` | tolerance | Flash tolerance |
| `Input\BLKOPFREWAT` | `NO`, `YES` | YES: water leaves as its own free-water phase in the flash |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_PRES` | PRESSURE | Outlet pressure |
