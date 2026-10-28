# DSTWU

Shortcut column (Winn, Underwood, Gilliland): from two key components and their recoveries it gives the minimum reflux and stages, then either the stages for a given reflux or the reflux for given stages. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `D(OUT)` distillate, `B(OUT)` bottoms, `CWD(OUT)` free water from the condenser; `CHS` / `RHS` (IN and OUT) heat streams for the condenser and the reboiler.

To run it needs both keys, both recoveries, `PTOP`, `PBOT`, `OPT_NTRR` and the `RR` or `NSTAGE` it selects.

Both recoveries are fractions of the key's feed that leave in the distillate; `RECOVH` must stay below `RECOVL`, otherwise the write is refused.

A negative `RR` is a multiple of the minimum (-1.5 gives 1.5 x `MIN_REFLUX`); a positive one is used as is.

An `NSTAGE` below the minimum is not an error: the block uses twice `MIN_STAGES` instead, so compare `ACT_STAGES` with `NSTAGE`.

`OPT_RDV` writes `RDV` (`LIQUID` 0, `VAPOR` 1); for `VAPLIQ` set `RDV` after it. The run uses `RDV`.

A heat stream on `CHS(OUT)` or `RHS(OUT)` carries the condenser or reboiler duty with the sign reversed.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_NTRR` | `RR`, `NSTAGE` | What is given: the reflux ratio or the stage count (default `NSTAGE`) |
| `Input\RR` | ratio | Reflux ratio; negative = multiple of the minimum |
| `Input\NSTAGE` | int | Stage count; the condenser and the reboiler count as stages |
| `Input\LIGHTKEY` | component | Light key |
| `Input\RECOVL` | fraction | Share of the light key's feed recovered in the distillate |
| `Input\HEAVYKEY` | component | Heavy key |
| `Input\RECOVH` | fraction | Share of the heavy key's feed that still reaches the distillate |
| `Input\PTOP` | PRESSURE | Condenser pressure |
| `Input\PBOT` | PRESSURE | Reboiler pressure |
| `Input\OPT_RDV` | `LIQUID`, `VAPOR`, `VAPLIQ` | Condenser: total (liquid distillate), partial with vapor distillate, or partial with both |
| `Input\RDV` | fraction | Share of the distillate leaving as vapor |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\MIN_REFLUX` | ratio | Minimum reflux ratio |
| `Output\ACT_REFLUX` | ratio | Reflux ratio used |
| `Output\MIN_STAGES` | real | Minimum stages |
| `Output\ACT_STAGES` | real | Stages used |
| `Output\FEED_LOCATN` | real | Feed stage |
| `Output\RECT_STAGES` | real | Stages above the feed |
| `Output\DIST_VS_FEED` | ratio | Distillate over feed |
| `Output\COND_DUTY` | ENTHALPY-FLO | Condenser duty, negative |
| `Output\REB_DUTY` | ENTHALPY-FLO | Reboiler duty |
| `Output\DISTIL_TEMP` | TEMPERATURE | Distillate temperature |
| `Output\BOTTOM_TEMP` | TEMPERATURE | Bottoms temperature |

More: [reflux table and HETP](dstwu-calculation.md), [convergence](dstwu-convergence.md).

Not covered: none.
