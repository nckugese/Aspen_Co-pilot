# Decanter: flash options

How the liquid-liquid split is solved. Paths are under `\Data\Blocks\{name}\`.

## Input | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\LL_METH` | `EQ-SOLVE`, `GIBBS` | Solve by equal fugacities (default) or by Gibbs energy minimum |
| `Input\KLL_CORR` | `PROPOPTSET`, `POLYNOMIAL` | Liquid-liquid K from the property method (default) or from a correlation ([decanter-phase-properties.md](decanter-phase-properties.md)) |
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | Free water: `YES` makes the second liquid pure water, `DIRTY` a water phase that can hold organics |
| `Input\MAXIT` | int | Iteration limit (default 30) |
| `Input\TOL` | tolerance | Convergence tolerance (default 1e-4) |

With `GIBBS` the `KLL_CORR` choice is not used: `POLYNOMIAL` coefficients gave the plain `GIBBS` result.

`YES` sent pure water to `L2(OUT)`; with `DIRTY` that outlet kept traces of benzene and toluene.
