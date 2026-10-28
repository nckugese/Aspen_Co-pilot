# Classifier

Splits the solids of a feed into fines and coarse by particle size, settling velocity or particle density, with a separation function, a measured efficiency table or a sifter (air classifier) model. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `G(IN)` extra sifting gas, `P(OUT)` fines, `S(OUT)` coarse solids.

The feed needs a solid substream with a size distribution; a working setup is calcite in `CIPSD` (stream class `MIXCIPSD`).

`METHOD` has no default. `FUNCTION` then needs `SHARPNESS` and the cut value that matches `CLASS_CHAR`: `CUT_SIZE`, `CUT_VELOCITY` or `CUT_DENSITY`.

Fluid split: the default (`FINES-SPLIT` with `FLUID_SPLIT` 0) sends all the fluid to `S(OUT)`; set `FLUID_SPLIT` for a wet fines stream.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\METHOD` | `FUNCTION`, `DATA`, `SIFTER` | Model: separation function, efficiency table ([curves](classifier-curves.md)) or sifter ([sifters](classifier-sifter.md)) |
| `Input\CLASS_CHAR` | `SIZE`, `VELOCITY`, `DENSITY` | Property the solids are separated by |
| `Input\CLASS_MODEL` | `ROGERS`, `PLITT` | `FUNCTION`: shape of the separation curve |
| `Input\CUT_SIZE` | LENGTH | Cut size (`SIZE`) |
| `Input\CUT_VELOCITY` | VELOCITY | Cut settling velocity (`VELOCITY`) |
| `Input\CUT_DENSITY` | DENSITY | Cut particle density (`DENSITY`) |
| `Input\SHARPNESS` | real | Sharpness of the cut |
| `Input\FINES_OFFSET` | fraction | Share of the fines that bypass to `S(OUT)` |
| `Input\FLUID_SPEC` | `FINES-SPLIT`, `COARSE-SPLIT`, `COARSE-LOAD`, `FINES-LOAD` | Fluid spec: share of the feed fluid to fines or coarse, or the fluid load of the coarse or fines outlet |
| `Input\FLUID_SPLIT` | fraction | `*-SPLIT`: share of the feed fluid sent to the named outlet |
| `Input\FLUID_LOAD` | mass ratio | `*-LOAD`: kg of fluid per kg of solids in the named outlet |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EFFICIENCY` | fraction | Share of the feed solids that leave in `S(OUT)` |
| `Output\FEED_DIAM` | LENGTH | Median particle size of the feed |
| `Output\COARSE_D50` | LENGTH | Median particle size in `S(OUT)` |
| `Output\FINES_D50` | LENGTH | Median particle size in `P(OUT)` |

More: [efficiency tables](classifier-curves.md), [sifters](classifier-sifter.md), [impeller wheels](classifier-impeller.md), [outlet conditions](classifier-outlet.md).

Not covered: Whiten fit (`OPT_WHITEN`) (the run crashes the Aspen engine); `VEL_OPT` (the block stays incomplete with every input tried); Heating curves, Utility (shared forms that this block's tree does not carry).
