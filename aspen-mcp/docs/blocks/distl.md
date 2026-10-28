# DISTL

Shortcut column (Edmister): for a given stage count, feed stage, reflux ratio and distillate rate it rates the split and the duties. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `D(OUT)` distillate, `B(OUT)` bottoms, `CWD(OUT)` free water from the condenser; `CHS` / `RHS` (IN and OUT) heat streams for the condenser and the reboiler.

To run it needs `NSTAGE`, `FEED_LOC`, `RR`, `D_F`, `PTOP` and `PBOT`.

Write `NSTAGE` before `FEED_LOC`: the feed stage must lie in 1..`NSTAGE`, and lowering `NSTAGE` below it clears it.

Accepted ranges: `NSTAGE` 3 to 500, `RR` above 0 (no negative multiples), `D_F` strictly between 0 and 1.

The distillate gets `D_F` times the feed's moles; distillate and bottoms leave at `PTOP` and `PBOT`.

Both duties come out positive. A heat stream on `CHS(OUT)` carries `COND_DUTY` with the same sign, one on `RHS(OUT)` carries `REB_DUTY` negated.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\NSTAGE` | int | Number of stages |
| `Input\FEED_LOC` | int | Stage number that receives the feed |
| `Input\RR` | ratio | Reflux ratio |
| `Input\D_F` | ratio | Distillate over feed, molar |
| `Input\COND_TYPE` | `TOTAL`, `PARTIAL` | Condenser: total (liquid distillate) or partial (vapor distillate); default `TOTAL` |
| `Input\PTOP` | PRESSURE | Condenser pressure |
| `Input\PBOT` | PRESSURE | Reboiler pressure |

## Results (after a run)

`TOP_TEMP` is the distillate temperature; the distillate is all liquid with `TOTAL` and all vapor with `PARTIAL`.

| Path | Type | Purpose |
|---|---|---|
| `Output\COND_DUTY` | ENTHALPY-FLO | Heat removed in the condenser, positive |
| `Output\REB_DUTY` | ENTHALPY-FLO | Heat added in the reboiler |
| `Output\TOP_TEMP` | TEMPERATURE | Distillate temperature |
| `Output\BOTTOM_TEMP` | TEMPERATURE | Bottoms temperature |
| `Output\FEED_TRAY_T` | TEMPERATURE | Feed stage temperature |
| `Output\FEED_QUALITY` | fraction | Share of the feed that is vapor (feed quality) |
| `Output\ACT_REFLUX` | ratio | Reflux ratio used |
| `Output\ACT_STAGES` | int | Stage count used |

More: [convergence and free water](distl-convergence.md).

Not covered: Dynamics (Aspen Dynamics only).
