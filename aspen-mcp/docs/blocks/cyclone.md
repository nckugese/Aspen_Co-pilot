# Cyclone

Gas-solids cyclone: rates a cyclone of given diameter, or sizes one for a target efficiency, with one of several separation correlations; or acts as a simple solids separator. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` gas with solids, `G(OUT)` cleaned gas, `S(OUT)` collected solids.

The feed needs a solid substream; a working setup is calcite in `CIPSD` (stream class `MIXCIPSD`) with a size distribution, carried by nitrogen.

`MODEL` has no default. `CYCLONE` then needs `METHOD`, `TYPE` and `DIAM` (simulation).

`DESIGN` needs `EFF` instead of `DIAM`; a blank `MODE` acts as `SIMULATION`.

`MUSCHELKNAUT` in `DESIGN` also needs `DES_PDROP` and sizes the cyclone to that drop.

Every method except `MUSCHELKNAUT` warns when the inlet velocity (`Output\IN_VELOC`) passes 30 m/s; a larger `DIAM` or more cyclones bring it down.

`DESIGN` stops with an error when the target needs more drop than `MAX_PDROP`.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\MODEL` | `CYCLONE`, `SOLIDS-SEP` | Rigorous cyclone, or a simple split ([solids separator](cyclone-solids-separator.md)) |
| `Input\MODE` | `SIMULATION`, `DESIGN` | Rate a given cyclone, or size one |
| `Input\METHOD` | `LEITH-LICHT`, `LAPPLE`, `MOD-LEITH-LI`, `DIETZ`, `MOTHES-LOF`, `MUSCHELKNAUT`, `USER` | Efficiency correlation; `USER` takes a table ([efficiency](cyclone-efficiency.md)), `MUSCHELKNAUT` has its own inputs ([Muschelknautz](cyclone-muschelknautz.md)) |
| `Input\TYPE` | `BARTH1-RECT`, `BARTH1-ROUND`, `BARTH2-RECT`, `BARTH2-ROUND`, `BARTH3-RECT`, `BARTH3-ROUND`, `BARTH4`, `LAPPLE-GP`, `SWIFT-HE`, `SWIFT-GP`, `SWIFT-HT`, `STAIRMAND-HE`, `STAIRMAND-HT`, `USER`, `USER-RATIO` | Standard geometry family, or own dimensions or ratios ([geometry](cyclone-geometry.md)) |
| `Input\DIAM` | LENGTH | `SIMULATION`: cylinder diameter |
| `Input\NCYCLONE` | int | `SIMULATION`: cyclones in parallel (default 1) |
| `Input\VANE` | real | `LAPPLE`: vane constant of the pressure drop (default 16) |
| `Input\EFF` | fraction | `DESIGN`: target share of the feed solids collected |
| `Input\MAX_PDROP` | PDROP | `DESIGN`: highest allowed pressure drop |
| `Input\MAX_CYCLONE` | int | `DESIGN`: most cyclones in parallel (default 100) |
| `Input\DES_PDROP` | PDROP | `DESIGN` with `MUSCHELKNAUT`: the pressure drop to size for |
| `Input\MAXIT` | int | `DESIGN`: iteration limit of the diameter search (default 30) |
| `Input\TOL` | real | `DESIGN`: tolerance of the diameter search |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EFF_OUT` | fraction | Share of the feed solids collected in `S(OUT)` |
| `Output\PDROP` | PDROP | Gas pressure drop |
| `Output\IN_VELOC` | VELOCITY | Inlet gas speed |
| `Output\BU_RATIO` | ratio | Inlet velocity over the saltation velocity |
| `Output\DIAM_CYL` | LENGTH | Cylinder diameter (found in `DESIGN`) |
| `Output\NUMBER` | int | Cyclones in parallel (found in `DESIGN`) |

More: [solids separator](cyclone-solids-separator.md), [geometry](cyclone-geometry.md), [Muschelknautz](cyclone-muschelknautz.md), [efficiency table and solids loading](cyclone-efficiency.md).

Not covered: User subroutine (user Fortran subroutine, `METHOD` `USER-SUB`); Muschelknautz with `USER-RATIO` (the block stays incomplete with every input tried); Heating curves, Utility (shared forms that this block's tree does not carry).
