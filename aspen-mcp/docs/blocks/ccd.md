# CCD (counter-current decanter)

A train of washing stages: the slurry enters the top stage, the wash liquid the bottom stage, and the solids move down against the liquid; each stage settles to a set liquid-to-solids ratio. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `S(IN)` slurry, `L(IN)` wash liquid, `L(OUT)` overflow (the wash liquor), `S(OUT)` underflow (the washed solids). Side feeds, side draws and pseudo streams: [side streams](ccd-side-streams.md); heat streams and convergence: [heat](ccd-heat.md).

The slurry needs a solid substream; a working setup is calcite in `CISOLID` (stream class `MIXCISLD`), with a solute such as methanol dissolved in the water to wash out.

Connecting fills the stream table: the `S(IN)` stream enters stage 1 `UNDER`, the `L(IN)` stream stage `NSTAGE` `OVER`; `L(OUT)` leaves stage 1 `OVER` and `S(OUT)` stage `NSTAGE` `UNDER`, following later changes of `NSTAGE`. Moving one of these four leaves the block incomplete.

To run it needs `NSTAGE`, `PRES`, and at least one stage row holding both `MEFF` and `RATIO`.

## Input | Specifications

1. Insert a row into `MEFF` labelled with a stage number (`insert_row`, then the label `1`, `2`, ...); `RATIO` gets the same row.
2. Write `MEFF\{stage}` and `RATIO\{stage}` on that row; add rows for stages that differ.

Stages without a row reuse the given values: one row on stage 1 gave the same outlets as that row on all three stages.

| Path | Type | Purpose |
|---|---|---|
| `Input\NSTAGE` | int | Number of stages, 2 or more |
| `Input\PRES` | PRESSURE | Pressure of all stages |
| `Input\TAMB` | TEMPERATURE | Ambient temperature (default 25 C) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the stage flashes (default 2) |
| `Input\PHASE` | `L`, `V`, `S` | The single phase when `NPHASE` is 1 |
| `Input\MEFF\{stage}` | fraction | How well the stage mixes, 0 to 1 |
| `Input\RATIO\{stage}` | mass ratio | Liquid-to-solids mass ratio of the stage underflow |

At `RATIO` 0.5 `S(OUT)` carried 0.5 kg liquid per kg solids; at `MEFF` 0.7 it kept more of the dissolved methanol than at 1.

## Input | Streams

| Path | Type | Purpose |
|---|---|---|
| `Input\FEED_STAGE\{stream}` | int | Stage a feed enters |
| `Input\FEED_DIRCODE\{stream}` | `UNDER`, `OVER` | Flow the feed joins: `UNDER` the underflow (solids side), `OVER` the overflow |
| `Input\PROD_STAGE\{stream}` | int | Stage a product leaves |
| `Input\PROD_DIRCODE\{stream}` | `UNDER`, `OVER` | Flow the product takes: the stage underflow or overflow |
| `Input\FRAC\{stream}` | fraction | Share of that flow the product takes (default 1) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TOP_LTEMP` | TEMPERATURE | Temperature of the overflow leaving stage 1 |
| `Output\B_TEMP` | TEMPERATURE | Temperature of the underflow leaving the last stage |
| `Output\DUTY` | ENTHALPY-FLO | Total duty of all stages |
| `Output\TOP_LFLOW` | MASS-FLOW | Product from the top stage (the overflow) |
| `Output\PROD_LFLOW` | MASS-FLOW | Product from the bottom stage (the underflow) |
| `Output\B_TEMP2\{stage}` | TEMPERATURE | Temperature of each stage |
| `Output\QCALC\{stage}` | ENTHALPY-FLO | Duty of each stage |
| `Output\L1_FLOW\{stage}` | MASS-FLOW | Underflow product drawn at each stage (0 where none) |
| `Output\L2_FLOW\{stage}` | MASS-FLOW | Overflow product drawn at each stage (0 where none) |

More: [side streams](ccd-side-streams.md), [temperature, duty, heat streams and convergence](ccd-heat.md).

Not covered: UA heat exchange on a stage (`HEAT_UA`, `HEAT_TMED`) (stays incomplete with every input tried); Pseudo stream flow basis (`FLP_BASIS`, `BASIS_FLP`) (not checked); Heating curves, Utility (shared forms that this block's tree does not carry).
