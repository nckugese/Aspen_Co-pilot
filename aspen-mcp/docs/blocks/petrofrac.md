# PetroFrac

Rigorous column for refinery fractionation: a main column with an optional feed furnace, side strippers and pumparounds. Variants of its icon are the same block. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `MF(IN)` main-column feeds, `SF(IN)` stripper steam, `LD(OUT)` liquid distillate, `VD(OUT)` vapor distillate, `B(OUT)` bottoms, `SP(OUT)` side products, `WD(OUT)` free water, `SB(OUT)` stripper bottoms.

To run it needs `CTYPE`, `PRES1`, a feed stage per feed and the column specs: two with a condenser and a kettle. `NSTAGE` and `RTYPE` (default `KETTLE`) cannot be cleared once feed stages and specs are set.

Two specs at most: the rest lock until one is cleared (write `""`). Refused pairs: distillate with bottoms rate, a condenser or reboiler duty with a reflux ratio or reflux rate.

A `NONE-BOTFEED` or `NONE-BOTPA` bottom is refused while a reflux ratio is set; pair it with a distillate or bottoms rate.

`PARTIAL-V`, `NONE-TOPPA` and `NONE-TOPFEED` send the distillate out of `VD(OUT)`; they are refused while a stream sits on `LD(OUT)`.

## Setup | Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\NSTAGE` | int | Stages of the main column, condenser = 1 |
| `Input\CTYPE` | `TOTAL`, `SUBCOOLED`, `PARTIAL-V`, `PARTIAL-VL`, `NONE-TOPPA`, `NONE-TOPFEED` | Top of the column: condenser type, or no condenser with a top pumparound / a top liquid feed |
| `Input\RTYPE` | `KETTLE`, `NONE-BOTFEED`, `NONE-BOTPA` | Bottom: kettle reboiler, or none (stripping steam or furnace feed at the bottom / a bottom pumparound) |

Column specs (a furnace spec also counts, see [petrofrac-furnace.md](petrofrac-furnace.md)):

| Path | Type | Purpose |
|---|---|---|
| `Input\BASIS_D` | MOLE-FLOW | Distillate rate |
| `Input\BASIS_B` | MOLE-FLOW | Bottoms rate |
| `Input\BASIS_RR` | ratio | Reflux ratio |
| `Input\BASIS_L1` | MOLE-FLOW | Reflux rate |
| `Input\Q_COND` | ENTHALPY-FLO | Condenser duty, negative |
| `Input\Q_REB` | ENTHALPY-FLO | Reboiler duty |

## Setup | Streams

| Path | Type | Purpose |
|---|---|---|
| `Input\FEED_STAGE\{stream}` | int | Feed stage; the entry appears once the stream is on `MF(IN)` |
| `Input\FEED_CONVEN\{stream}` | `ABOVE-STAGE`, `ON-STAGE`, `ON-STAGE-VAP`, `ON-STAGE-LIQ`, `FURNACE` | How the feed enters its stage; `FURNACE` sends it through the feed furnace |
| `Input\PROD_STAGE\{stream}` | int | Side-product stage (stream on `SP(OUT)`) |
| `Input\PROD_PHASE\{stream}` | `L`, `V` | Side-product phase |
| `Input\PROD_FLOW\{stream}` | MOLE-FLOW | Side-product rate |

## Setup | Pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES1` | PRESSURE | Pressure of stage 1, the condenser when there is one |
| `Input\OPT_DP` | `P-BOTTOM`, `DP-STAGE`, `DP-COL` | Rest of the profile: bottom pressure, drop per stage or drop over the column |
| `Input\PRESN` | PRESSURE | Bottom stage pressure (`P-BOTTOM`) |
| `Input\DP_STAGE` | PDROP | Drop from one stage to the next |
| `Input\DP_COL` | PDROP | Drop over the whole column |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\COND_DUTY` | ENTHALPY-FLO | Condenser duty |
| `Output\REB_DUTY` | ENTHALPY-FLO | Reboiler duty |
| `Output\MOLE_D` | MOLE-FLOW | Distillate rate |
| `Output\B_TEMP5\{stage}` | TEMPERATURE | Stage temperature, main column |
| `Output\X3\{stage}\{comp}` | fraction | Stage liquid composition, mole basis |
| `Output\LIQ_FLOW5\{stage}` | MOLE-FLOW | Liquid leaving a stage |

More: [furnace and steam](petrofrac-furnace.md), [condenser, free water and utilities](petrofrac-condenser.md), [side strippers](petrofrac-strippers.md), [pumparounds](petrofrac-pumparounds.md), [design and runback specs](petrofrac-design-specs.md), [efficiencies](petrofrac-efficiencies.md), [side heaters](petrofrac-heaters.md), [convergence and estimates](petrofrac-convergence.md), [property sections](petrofrac-properties.md), [heating curves](petrofrac-hcurves.md), [tray and packing sizing](petrofrac-sizing.md), [analysis and report](petrofrac-analysis.md).

Not covered: Connectivity (a view of the stream connections, not checked); Dynamics, Stripper dynamics (Aspen Dynamics only); Subroutines (user Fortran subroutines); Stage Wizard (a wizard, command-only).
