# Filter: convergence

Step and layer controls of the rated filter calculation (not `SOLIDS-SEP`). The defaults are a good start. Paths are under `\Data\Blocks\{name}\`; basics in [filter.md](filter.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\INIT_NLAYER` | int | Cake layers at the start (default 100) |
| `Input\LAYER_AGG` | real | Percent difference below which layers merge (default 0.1) |
| `Input\FLOW_INCR` | real | Percent flow change that adds a layer (default 50) |
| `Input\INIT_FL_INCR` | real | Percent flow change at the start (default 5) |
| `Input\MIN_INITSTEP` | TIME | Smallest first time step |
| `Input\MAX_INITSTEP` | TIME | Largest first time step |
| `Input\MAX_TSTEP` | TIME | Largest time step while filtering |
| `Input\MAX_NSTEP` | int | Most time steps (default 3000) |
| `Input\MAX_ITER` | int | Most iterations (default 40000) |
| `Input\FLOWTOL` | real | Percent tolerance on the flows (default 0.1) |
| `Input\FLASH_MAXIT` | int | Most flash iterations (default 30) |
| `Input\FLASH_TOL` | real | Flash tolerance (default 1e-4) |
