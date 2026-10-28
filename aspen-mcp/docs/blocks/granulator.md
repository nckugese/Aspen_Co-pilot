# Granulator

Fluidized-bed size enlargement of solids: layering of the solids sprayed with a liquid (granulation), particles sticking together (agglomeration), or a given outlet size distribution. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` seed solids, `L(IN)` sprayed liquid, `G(IN)` gas, `P(OUT)` product, `G(OUT)` gas.

The solids need a size distribution; a working setup is calcite in `CIPSD` (stream class `MIXCIPSD`).

`GRANULATION` and `AGGLOMERATIO` need a stream on `L(IN)` and `BED_MASS`; `AGGLOMERATIO` also a prefactor ([agglomeration](granulator-agglomeration.md)).

`USER-SPEC` runs with or without `L(IN)`.

Connect `G(IN)` and `G(OUT)` together or not at all: `G(OUT)` alone leaves the block incomplete.

With `GRANULATION`, `RES_TIME` is `BED_MASS` over the solids flow in `P(OUT)`.

`MOISTURE` needs a moisture component: insert a row into `\Data\Components\Moisture-Comps\Input\COMP` and write `H2O` to it. Without one the value is not passed to the run and the product stays dry.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\METHOD` | `GRANULATION`, `AGGLOMERATIO`, `USER-SPEC` | Growth model: layering from the spray, agglomeration ([agglomeration](granulator-agglomeration.md)) or a given outlet PSD ([outlet PSD](granulator-outlet-psd.md)) |
| `Input\BED_MASS` | MASS | Mass of solids held in the bed |
| `Input\MODEL` | `MIXED`, `PLUG-FLOW` | `GRANULATION`: solids in the bed well mixed or in plug flow |
| `Input\GROWTH_MODEL` | `SURFACE`, `VOLUME`, `DIAMETER` | `MIXED`: growth shared out by particle surface, volume or diameter |
| `Input\GROWTH_SCALE` | real | `MIXED`: multiplier on the growth rate (default 1) |
| `Input\MOISTURE` | fraction | Water left in the product solids |
| `Input\MOIST_BASIS` | `WET`, `DRY` | `MOISTURE` per kg of wet or of dry solids |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\AVERAGE` | LENGTH | Product D50 |
| `Output\DC_WIDTH1` | LENGTH | Sauter mean size (d32) of the product |
| `Output\RATE` | VELOCITY | Mean growth rate of the particle size |
| `Output\RES_TIME` | TIME | Mean residence time of the solids in the bed |
| `Output\AREA_CALC` | AREA | Particle surface area in the bed |
| `Output\MINIMUM` | LENGTH | Mean size of the seeds in `F(IN)` |
| `Output\MAXIMUM` | LENGTH | Seed d32 (Sauter mean size) |

`AREA_CALC` is filled only with `SURFACE` growth.

Despite their names, `MINIMUM` and `MAXIMUM` describe the seeds (checked against the feed PSD).

More: [agglomeration](granulator-agglomeration.md), [outlet PSD](granulator-outlet-psd.md), [outlet flash](granulator-outlet.md), [convergence](granulator-convergence.md).

Not covered: Gas ports and elutriation (`G(IN)`, `G(OUT)`, `ELUTRIATION`, `AREA`, `SHARPNESS`, `ELUT_BEF_AGG`) (with a gas inlet the block wants elutriation on, and the V15 engine rejects the `ELUTRIATION` keyword the GUI writes, so no run starts); Cumulative fraction (`CUMFRAC`) (no effect seen); Heating curves, Utility, List views (shared forms that this block's tree does not carry).
