# Pump flash options and vapor check

Paths are under `\Data\Blocks\{name}\`.

`VFRAC_CHK` decides what vapor in the feed does: `ERROR` (default) stops the block, `WARNING` finishes with a warning, `NONE` lets it run.

A feed with two liquids gives a phase-stability warning with the default `NPHASE=1`; `NPHASE=3` handles it.

`BLKOPFREWAT=YES` with a stream on `WD(OUT)` sends the free water there; without that stream it stays in the product.

## Setup | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\VFRAC_CHK` | `ERROR`, `WARNING`, `INFORMATION`, `NONE` | Response to vapor |
| `Input\TOLVF` | fraction | Vapor fraction tolerated, default 0.001 |

## Setup | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\NPHASE` | `1`, `2`, `3` | Phases considered: liquid only, vapor-liquid, or two liquids too |
| `Input\MAXIT` | int | Flash iteration limit, default 30 |
| `Input\TOL` | real | Flash tolerance, default 1e-4 |
| `Input\BLKOPFREWAT` | `YES`, `NO`, `DIRTY` | Free-water calculation |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\B_VFRAC` | fraction | Outlet vapor fraction |
