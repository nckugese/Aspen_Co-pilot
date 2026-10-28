# HyCyc (hydrocyclone)

Separates solids from a liquid by the swirl in a cyclone: coarse particles leave with the underflow, fines with the overflow. `MODEL` `SOLIDS-SEP` is a plain split instead ([solids separator](hycyc-solids-separator.md)). Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` slurry feed, `L(OUT)` overflow (most of the liquid and the fines), `S(OUT)` underflow (the coarse solids with some liquid). Both outlets leave at the feed pressure minus the computed drop `PDRP`; there is no outlet pressure input.

The feed needs a solid substream with a size distribution; a working setup is calcite in a `CIPSD` substream (stream class `MIXCIPSD`).

`MODEL` has no default. `HYDROCYCLONE` in `SIMULATION` mode (the default) needs `TYPE`, `METHOD` and `DIAM`.

`NCYCLONE` cyclones in parallel share the feed, so each sees less flow and the drop falls.

`DESIGN` mode needs `EFF`, `DIAM_PART`, `MAX_DIAM` and `MAX_PDROP` in place of `DIAM`, and finds the diameter and number of cyclones.

In `DESIGN` mode every `METHOD` except `BRADLEY` also needs `DES_PDROP`; the result then runs at that drop.

`TYPE` `USER` is refused in `DESIGN` mode; use `USER-RATIO` or a built-in type.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\MODEL` | `HYDROCYCLONE`, `SOLIDS-SEP` | Rate a hydrocyclone, or a plain solids split |
| `Input\CALC_MODE` | `SIMULATION`, `DESIGN` | Rate a given diameter, or size the cyclone for a target efficiency |
| `Input\TYPE` | `BRADLEY-RC`, `BRADLEY-RO`, `RIETEMA-RC`, `RIETEMA-RO`, `USER`, `USER-RATIO` | Proportions: Bradley or Rietema with a rectangular (`-RC`) or round (`-RO`) inlet, or your own ([geometry](hycyc-geometry.md)) |
| `Input\METHOD` | `BRADLEY`, `PLITT`, `NAGESWARARAO`, `MOD-BRAUN`, `USER` | Efficiency and pressure-drop correlation ([correlations](hycyc-correlations.md), [user curve](hycyc-user-efficiency.md)) |
| `Input\DIAM` | LENGTH | `SIMULATION`: cyclone diameter |
| `Input\NCYCLONE` | int | `SIMULATION`: cyclones in parallel sharing the feed (default 1) |
| `Input\EFF` | fraction | `DESIGN`: target grade efficiency at the `DIAM_PART` size |
| `Input\DIAM_PART` | LENGTH | `DESIGN`: particle size that efficiency refers to |
| `Input\MAX_DIAM` | LENGTH | `DESIGN`: largest diameter allowed |
| `Input\MAX_PDROP` | PDROP | `DESIGN`: largest pressure drop allowed |
| `Input\DES_PDROP` | PDROP | `DESIGN`: pressure drop to design for (all methods except `BRADLEY`) |
| `Input\DEN_PART` | DENSITY | `DESIGN`: particle density (optional) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\DIAM_OUT` | LENGTH | Cyclone diameter (computed in `DESIGN`) |
| `Output\NUMBER` | int | Cyclones in parallel (computed in `DESIGN`) |
| `Output\PDRP` | PDROP | Pressure drop |
| `Output\CEFF` | fraction | Overall separation efficiency of the solids |
| `Output\VELOCITY` | VELOCITY | Inlet velocity |
| `Output\VOLFLOW` | VOLUME-FLOW | Liquid throughput of one cyclone |
| `Output\TOP_LFLOW` | VOLUME-FLOW | Overflow volume flow |
| `Output\BOT_VFLOW` | VOLUME-FLOW | Underflow volume flow |
| `Output\LIQ_RATIO` | fraction | Share of the feed liquid in the underflow |

More: [geometry](hycyc-geometry.md), [correlations](hycyc-correlations.md), [user efficiency curve](hycyc-user-efficiency.md), [solids separator](hycyc-solids-separator.md).

Not covered: Heating curves, Utility (shared forms that this block's tree does not carry).
