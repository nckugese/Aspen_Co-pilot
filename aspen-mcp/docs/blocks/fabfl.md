# FabFl (fabric filter, baghouse)

Dusty gas flows through cloth bags grouped in cells; the dust forms a cake on the cloth until the bags are cleaned. `METHOD` `SOLIDS-SEP` is a plain split instead ([solids separator](fabfl-solids-separator.md)). Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` dusty gas, `G(OUT)` cleaned gas, `S(OUT)` collected dust. The feed needs a solid substream; these runs carried calcite in `CIPSD` (stream class `MIXCIPSD`, sizes 0 to 20 um) in 300 kmol/hr nitrogen.

What each choice needs before it can run:

`FAB-FILTER`: `EFF_OPT` ([efficiency](fabfl-efficiency.md)); in `SIMULATION` mode also `NCELLS`.

`CALCULATE` `TIME` (default) takes `MAX_PDROP` and returns the filtering time; `PRESSURE` takes `FILT_TIME` and returns the drop.

`VEL_OPT` `FROM-AREA`: `FILTER_AREA`, which then replaces the bag data in the area.

`MODE` `DESIGN` sizes the baghouse instead ([design](fabfl-design.md)).

`SOLIDS-SEP`: `PRES` plus the two specs that `PHASEP_OPT` names.

Area in service = (`NCELLS` - `NCLEAN`) x `NBAGS` x `AREA`: 346.3 m2 for 4 cells, 230.9 m2 with `NCLEAN` 2.

Keep `Output\VELOCITY` between `MIN_VEL` and `MAX_VEL`: outside, the run ends with a warning.

Aspen refuses a `FILT_TIME` outside 30 s to 10000 s.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\METHOD` | `FAB-FILTER`, `SOLIDS-SEP` | Bag filter model, or a plain split; no default |
| `Input\MODE` | `SIMULATION`, `DESIGN` | Rate a given baghouse (default), or size one |
| `Input\NCELLS` | int | `SIMULATION`: number of cells |
| `Input\NBAGS` | int | Bags per cell (default 78) |
| `Input\NCLEAN` | int | Cells off line for cleaning at a time (default 1) |
| `Input\AREA` | AREA | Cloth area of one bag (default 1.48 m2) |
| `Input\DIAM` | LENGTH | Bag diameter (default 0.154 m) |
| `Input\CALCULATE` | `TIME`, `PRESSURE` | Solve for the filtering time, or for the drop |
| `Input\MAX_PDROP` | PDROP | `TIME`: drop at which the bags are cleaned |
| `Input\FILT_TIME` | TIME | `PRESSURE`: filtering time between cleanings |
| `Input\VEL_OPT` | `FROM-BAGHOUS`, `FROM-AREA` | Area from the bag data (default), or from `FILTER_AREA` |
| `Input\FILTER_AREA` | AREA | `FROM-AREA`: total filtering area |
| `Input\MIN_VEL` | VELOCITY | Lowest gas velocity through the cloth (default 0.00254 m/s) |
| `Input\MAX_VEL` | VELOCITY | Highest one (default 0.0254 m/s) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EFF` | fraction | Share of the feed dust caught |
| `Output\TOT_AREA` | AREA | Filtering area in service |
| `Output\VELOCITY` | VELOCITY | Gas velocity through the cloth |
| `Output\TIME` | TIME | Filtering time between cleanings |
| `Output\PDROP` | PDROP | Mean drop over a cycle ([pressure drop](fabfl-pressure-drop.md)) |
| `Output\MAXIMUM` | PDROP | Drop just before cleaning (`MINIMUM`: just after) |
| `Output\SPACE` | AREA | Floor space needed |
| `Output\LOAD_IN` | MASS-DENSITY | Dust per volume of gas at the inlet (`LOAD_OUT` at the outlet) |

More: [design](fabfl-design.md), [coefficient model](fabfl-coefficient-model.md), [pressure drop](fabfl-pressure-drop.md), [efficiency](fabfl-efficiency.md), [solids separator](fabfl-solids-separator.md).

Not covered: Heating curves (shared form that this block's tree does not carry); Utility (not checked); GAS_UPFLOW (upward gas flow flag of the coefficient model, no effect seen in the runs); CLEAN_TIME (bag cleaning time, no effect seen in the runs); MEDIUM_RES (cloth resistance, no effect seen in the runs).
