# Sep2: outlet flash

Conditions of one outlet in place of the feed-flash conditions. Paths are under `\Data\Blocks\{name}\`; `{stream}` is the outlet.

1. `insert_row` on `Input\TEMP` with the outlet stream as label; every table below then has that row.
2. Write two of `TEMP`, `PRES`, `DELT`, `VFRAC` on the row (not `TEMP` with `DELT`).

## Input | Outlet Flash

| Path | Type | Purpose |
|---|---|---|
| `Input\TEMP\{stream}` | TEMPERATURE | Outlet temperature |
| `Input\PRES\{stream}` | PRESSURE | Outlet pressure when above zero; drop from the feed when zero or below |
| `Input\DELT\{stream}` | DELTA-T | Shift from the feed-flash temperature (negative cools) |
| `Input\VFRAC\{stream}` | fraction | Outlet vapor fraction |
| `Input\NPHASE\{stream}` | `1`, `2`, `3` | Phases checked in the outlet flash |
| `Input\PHASE\{stream}` | `V`, `L` | The one phase when `NPHASE` is `1` |
| `Input\FREE_WATER\{stream}` | `NO`, `YES`, `DIRTY` | Free-water handling of the outlet flash |
| `Input\KODE\{stream}` | `NOFLASH` | `NOFLASH`: the outlet is not flashed and no duty is computed |
| `Input\T_EST\{stream}` | TEMPERATURE | Temperature estimate |
| `Input\P_EST\{stream}` | PRESSURE | Pressure estimate |
| `Input\MAXIT\{stream}` | int | Flash iteration limit |
| `Input\TOL\{stream}` | tolerance | Flash tolerance |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STREAM_TEMP\{stream}` | TEMPERATURE | Outlet temperature |
| `Output\STREAM_DELT\{stream}` | DELTA-T | Outlet temperature minus the feed-flash temperature |
| `Output\STREAM_PDROP\{stream}` | PDROP | Outlet pressure minus the feed-flash pressure |
