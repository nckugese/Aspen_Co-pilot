# MCompr convergence and phases

Paths are under `\Data\Blocks\{name}\`. Defaults suit most cases; base setup as in [mcompr.md](mcompr.md).

`BLKOPFREWAT=YES` runs clean with a method such as GRAYSON. With PENG-ROB the gas leaving each cooler, saturated by the steam-table water model, fails the equation of state's vapor stability test at the next stage (CMSTIN.10, BLKSTAT 1); `DIRTY` does not have this problem with PENG-ROB.

Free water (`BLKOPFREWAT` YES or DIRTY) cannot be combined with `COOLER_NPHAS=3`; the write is refused.

## Setup | Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\COMPR_NPHASE` | `1`, `2`, `3` | Phases allowed in the compressors (default 2) |
| `Input\COOLER_NPHAS` | `1`, `2`, `3` | Phases allowed in the coolers (default 2) |
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | Treat water as a separate free-water phase in this block |
| `Input\PS_FLASH` | `ITERATIVE`, `DIRECT` | Method of the pressure-entropy flash |
| `Input\TOL` | real | Tolerance of the stage calculation (default 1e-4) |
| `Input\MAXIT` | int | Iterations of the stage calculation (default 30) |
| `Input\TEMP_TOL` | DELTA-T | Tolerance on temperature (default 0.01 C) |
| `Input\TEMP_MAXIT` | int | Iterations on temperature (default 30) |
| `Input\SB_TOL` | real | Tolerance of the outer loop on the outlet spec (default 1e-4) |
| `Input\SB_MAXIT` | int | Iterations of that loop (default 30) |
| `Input\HEAD_TOL` | real | Tolerance on the head (curves, default 1e-3) |
| `Input\HEAD_MAXIT` | int | Iterations on the head (default 30) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_VFRAC\{stage}` | fraction | Vapor fraction after each cooler |
