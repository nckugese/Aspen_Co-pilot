# RadFrac

Rigorous multistage column: distillation, absorption, stripping. Variants of its icon are the same block. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `LD(OUT)` liquid distillate, `VD(OUT)` vapor distillate, `B(OUT)` bottoms, `SP(OUT)` side products, `WD(OUT)` free-water decant, `HS(IN)` heat streams.

To run it needs `NSTAGE`, a feed stage per feed and two operating specs; without one of them the run stops in input translation.

`CONDENSER` left empty acts as a vapor-distillate condenser: it runs with the distillate on `VD(OUT)`, and with only `LD(OUT)` connected it stops in input translation.

An end set to `NONE` takes the place of one spec: with two specs set, `NONE` is refused.

A third spec is refused: clear one (write `""`) before setting another.

`PARTIAL-V` sends the distillate out of `VD(OUT)`; it is refused while a stream sits on `LD(OUT)`.

Without a reboiler, a vapor feed below the bottom stage goes on stage `NSTAGE`+1.

## Setup | Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\CALC_MODE` | `EQUILIBRIUM`, `RIG-RATE` | Equilibrium stages, or rate-based ([radfrac-rate-based.md](radfrac-rate-based.md)) |
| `Input\NSTAGE` | int | Stages, condenser = 1 and reboiler = last |
| `Input\CONDENSER` | `TOTAL`, `PARTIAL-V`, `PARTIAL-V-L`, `NONE` | Condenser type |
| `Input\REBOILER` | `KETTLE`, `THERMOSYPHON`, `NONE` | Reboiler type |
| `Input\NO_PHASE` | int | Phases checked on the stages: 2, or 3 ([radfrac-three-phase.md](radfrac-three-phase.md)) |
| `Input\CONV_METH` | `STANDARD`, `PETROLEUM`, `NONIDEAL`, `AZEOTROPIC`, `CRYOGENIC`, `OTHERS` | Convergence preset ([radfrac-convergence.md](radfrac-convergence.md)) |
| `Input\BASIS_RR` | ratio | Spec: reflux ratio |
| `Input\BASIS_BR` | ratio | Spec: boilup ratio |
| `Input\BASIS_D` | MOLE-FLOW | Spec: distillate rate |
| `Input\BASIS_B` | MOLE-FLOW | Spec: bottoms rate |
| `Input\BASIS_L1` | MOLE-FLOW | Spec: reflux rate |
| `Input\BASIS_VN` | MOLE-FLOW | Spec: boilup rate |
| `Input\D:F` | ratio | Spec: D/F, distillate over total feed |
| `Input\B:F` | ratio | Spec: B/F, bottoms over total feed |
| `Input\Q1` | ENTHALPY-FLO | Spec: condenser duty, negative |
| `Input\QN` | ENTHALPY-FLO | Spec: reboiler duty |

`BASIS_D` or `BASIS_B` on a mass basis: `set_value` with `basis='MASS'` and a mass unit.

## Setup | Streams

| Path | Type | Purpose |
|---|---|---|
| `Input\FEED_STAGE\{stream}` | int | Feed stage; the entry appears once the stream is on `F(IN)` |
| `Input\FEED_CONVEN\{stream}` | `ABOVE-STAGE`, `ON-STAGE`, `ON-STAGE-VAP`, `ON-STAGE-LIQ`, `DECANTER` | How the feed enters its stage |
| `Input\PROD_STAGE\{stream}` | int | Side-product stage (stream on `SP(OUT)`) |
| `Input\PROD_PHASE\{stream}` | `L`, `V` | Side-product phase |
| `Input\PROD_FLOW\{stream}` | MOLE-FLOW | Side-product rate |

## Setup | Pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES1` | PRESSURE | Pressure at stage 1 (the condenser when there is one) |
| `Input\OPT_PRES` | `DP-STAGE`, `DP-COL` | Rest of the column given by a drop per stage or for the whole column |
| `Input\DP_STAGE` | PDROP | Drop from one stage to the next |
| `Input\DP_COL` | PDROP | Pressure drop over the column |

## In a vary or define

A sensitivity, optimization or design spec varies the column as `BLOCK-VAR` with `VARYVARIABLE` `MOLE-RR` (reflux ratio), `NSTAGE` or `FEED-STAGE` (feed stream in `VARYID1`); a define reads `REB-DUTY` or `COND-DUTY`. The sentence (`COL-SPECS`, `PARAM`, `FEEDS`; `RESULTS`) fills itself ([sensitivity.md](../analysis/sensitivity.md)).

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\COND_DUTY` | ENTHALPY-FLO | Condenser duty |
| `Output\REB_DUTY` | ENTHALPY-FLO | Reboiler duty |
| `Output\MOLE_RR` | ratio | Molar reflux ratio |
| `Output\MOLE_D` | MOLE-FLOW | Distillate rate |
| `Output\MOLE_B` | MOLE-FLOW | Bottoms rate |
| `Output\TOP_TEMP` | TEMPERATURE | Top stage temperature |
| `Output\B_TEMP\{stage}` | TEMPERATURE | Stage temperature |
| `Output\X\{stage}\{comp}` | fraction | Liquid composition (mole fraction) per stage and component |

More: [internals](radfrac-internals.md), [rate-based](radfrac-rate-based.md), [pumparounds](radfrac-pumparounds.md), [design specs](radfrac-design-specs.md), [efficiencies](radfrac-efficiencies.md), [heaters, heat streams and utilities](radfrac-heaters.md), [three phases](radfrac-three-phase.md), [convergence and estimates](radfrac-convergence.md), [reactions](radfrac-reactions.md), [heating curves](radfrac-hcurves.md), [analysis and report](radfrac-analysis.md), [property sections](radfrac-properties.md).

Not covered: Dynamics (Aspen Dynamics only); Side heater / pumparound curves (curves of side heaters and pumparounds, not checked); NQ Curves (the run converges but its results stay empty); Packing database (part of the older objects); Pack Rating, Pack Sizing, Tray Rating, Tray Sizing (older objects: the run converges but the results stay empty); EO specs (equation-oriented variable specs, not checked); Rate-based correlations (user correlation parameters for rate-based, not checked); Rate-based report (rate-based report options, not checked); Rate-based subroutines (user Fortran subroutines for rate-based); Subroutines (user Fortran subroutines); Stage Wizard (a wizard, command-only); Selection dialogs (GUI selection state); Side-draw component lists (not checked); Reactions: residence time (residence times, not checked); Reactions: conversion (conversion sheet, not checked).
