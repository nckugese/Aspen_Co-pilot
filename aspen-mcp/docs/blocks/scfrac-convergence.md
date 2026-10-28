# SCFrac convergence

Paths are under `\Data\Blocks\{name}\`.

An FI that would pass `MAX_FINDEX` stops at the cap and the block still ends with BLKSTAT 0 while the spec is missed: check `Output\ERR\{spec}` after every run.

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Iterations for the product specs (default 50) |
| `Input\TOL` | real | Tolerance on the spec residuals (default 1e-4) |
| `Input\MAX_FINDEX` | int | Highest FI the solver may use (default 10) |
| `Input\FLASH_MAXIT` | int | Iterations of each flash (default 30) |
| `Input\FLASH_TOL` | real | Flash tolerance (default 1e-4) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\ERR\{spec}` | real | Reached minus target for each spec |
