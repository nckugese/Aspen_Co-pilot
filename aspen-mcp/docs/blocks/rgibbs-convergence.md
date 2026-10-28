# RGibbs atom matrix, convergence and estimates

Paths are under `\Data\Blocks\{name}\`.

## Advanced | Atom Matrix

| Path | Type | Purpose |
|---|---|---|
| `Input\ATOM_MATRIX` | `SYSTEM`, `LOCAL` | Element make-up of each component from the databank, or typed here |

1. Set `ATOM_MATRIX` `LOCAL`; the component rows of `Input\ATOM_COEF` are already there.
2. `insert_row` on dimension 1 of `Input\ATOM_COEF` once per element, labelled `C`, `H`, `O`, ...
3. Write every cell `ATOM_COEF\{comp}\{atom}`, 0 where the element is absent.

| Path | Type | Purpose |
|---|---|---|
| `Input\ATOM_COEF\{comp}\{atom}` | real | Atoms of that element in one molecule |

A full typed matrix gives the same outlet as the databank one.

## Advanced | Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Most iterations |
| `Input\TOL` | real | Convergence tolerance |
| `Input\FEED_FLASH` | `NO`, `YES` | Flash the feed first to give the phases a start |
| `Input\TLOWER` | TEMPERATURE | Lower temperature bound |
| `Input\TUPPER` | TEMPERATURE | Upper temperature bound |
| `Input\EB_MAXIT` | int | Most energy-balance iterations (duty mode) |
| `Input\EB_TOL` | real | How tightly the heat balance must close (duty mode) |

## Advanced | Estimates

| Path | Type | Purpose |
|---|---|---|
| `Input\FLOWEST\{comp}` | MOLE-FLOW | Outlet flow guess (row: `insert_row` labelled with the component) |
| `Input\TEST` | TEMPERATURE | Outlet temperature guess (duty mode) |
