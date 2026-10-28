# DISTL convergence

Paths are under `\Data\Blocks\{name}\`. Limits for the block's own loop and its flashes; the defaults solve ordinary cases.

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Iterations of the block's loop (default 60) |
| `Input\TEMP_TOL` | DELTA-T | Temperature tolerance of that loop (default 0.005 C) |
| `Input\FLASH_MAXIT` | int | Iterations of each flash (default 30) |
| `Input\FLASH_TOL` | real | Flash tolerance (default 1e-4) |
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | Water phase in the condenser: none, pure or dirty (default `NO`) |

With `YES` or `DIRTY`, connect a stream to `CWD(OUT)`: the water collected in the condenser leaves there.
