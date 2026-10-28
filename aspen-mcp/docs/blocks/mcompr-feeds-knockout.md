# MCompr side feeds and knockout liquids

Paths are under `\Data\Blocks\{name}\`; `{stream}` is the feed or outlet stream named. Base setup as in [mcompr.md](mcompr.md).

Each cooler's liquid needs a way out: either one `LK(OUT)` stream per stage except the last (`PROD_STAGE` 1 to `NSTAGE-1`; the last cooler's liquid leaves with `FLS(OUT)`), or a single `LK(OUT)` stream with `GLOBAL=Y` that collects every stage's liquid.

With free water (`BLKOPFREWAT` YES or DIRTY) a knockout stage needs two streams: one with `PROD_PHASE=L1` for the first liquid and one with `PROD_PHASE=W` for the water.

1. Connect one stream per knockout to `LK(OUT)` and set its `PROD_STAGE\{stream}` (or `GLOBAL\{stream}` `Y`).
2. Set `PROD_PHASE\{stream}` on every knockout stream: `L` (with free water `L1` or `W`). Without it the block stays incomplete, also with `GLOBAL` `Y`, and `run_simulation` refuses to run. The `FLS(OUT)` product stream takes no `PROD_PHASE` (the write is refused).

## Setup | Material (per stream)

| Path | Type | Purpose |
|---|---|---|
| `Input\FEED_STAGE\{stream}` | int | Stage an `IF(IN)` feed enters (`S1F` is stage 1) |
| `Input\PROD_STAGE\{stream}` | int | Stage whose cooler feeds this knockout stream |
| `Input\PROD_PHASE\{stream}` | `L`, `L1`, `W` | Liquid the stream takes: all liquid, first liquid, or free water (`L1` and `W` only with free water on, see `BLKOPFREWAT`) |
| `Input\GLOBAL\{stream}` | `N`, `Y` | `Y`: this knockout stream collects the liquid of every stage |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_VFRAC\{stage}` | fraction | Vapor fraction after each cooler |
