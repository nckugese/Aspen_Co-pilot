# DSTWU convergence

Paths are under `\Data\Blocks\{name}\`. Limits for the block's own flash and key-ratio loops; the defaults solve ordinary cases.

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Iterations of the block's outer loop (default 50) |
| `Input\K_TOL` | real | Tolerance on the K-values (default 0.05) |
| `Input\TEMP_TOL` | DELTA-T | Tolerance on the temperatures (default 0.2 C) |
| `Input\FLASH_MAXIT` | int | Iterations of each flash (default 30) |
| `Input\FLASH_TOL` | real | Flash tolerance (default 1e-4) |

## Free water

| Path | Type | Purpose |
|---|---|---|
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | Phases in the condenser: no free water, pure or dirty water |

With `YES` or `DIRTY`, connect a stream to `CWD(OUT)`: it takes the water phase from the condenser (with `DIRTY` it carries a trace of organics); dissolved water stays in the distillate.

With NRTL the block's default `SOLU_WATER` 3 ends in a phase-stability failure (BLKSTAT 2); set `Input\SOLU_WATER` to `2` (Block Options).

Give the feed stream the same setting (`Input\FREE_WATER\MIXED` on the stream); a feed left at the global `NO` makes input translation warn.
