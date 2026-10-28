# CCD: side streams

Extra feeds into a stage, draws from a stage, and pseudo streams that copy a stage flow. All are keyed by the stream name, `{stream}`. Paths are under `\Data\Blocks\{name}\`; basics in [ccd.md](ccd.md).

A stream on `SF(IN)`, `SP(OUT)` or `PS(OUT)` adds an empty row under its name; the block stays incomplete until that row has a stage and a direction.

## Side feeds (`SF(IN)`)

| Path | Type | Purpose |
|---|---|---|
| `Input\FEED_STAGE\{stream}` | int | Stage the side feed enters |
| `Input\FEED_DIRCODE\{stream}` | `OVER`, `UNDER` | Joins the stage overflow or underflow |

## Side draws (`SP(OUT)`)

| Path | Type | Purpose |
|---|---|---|
| `Input\PROD_STAGE\{stream}` | int | Stage the draw leaves |
| `Input\PROD_DIRCODE\{stream}` | `UNDER`, `OVER` | Draw from the stage underflow or overflow |
| `Input\FRAC\{stream}` | fraction | Share of that flow drawn off |

`UNDER` takes that share of the stage underflow, solids included (20 % of the feed solids left through the draw); `OVER` takes overflow liquid only.

## Pseudo streams (`PS(OUT)`)

A pseudo stream reports a copy of one stage flow; the real outlets keep the same flows.

| Path | Type | Purpose |
|---|---|---|
| `Input\PSEUDO_STAGE\{stream}` | int | Stage whose flow is copied |
| `Input\PSEUDO_DIRCO\{stream}` | `UNDER`, `OVER` | Copy the underflow or the overflow |

## Results (after a run)

`SOL_FLOW` equals the side feed's mass flow.

| Path | Type | Purpose |
|---|---|---|
| `Output\SOL_FLOW` | MASS-FLOW | Total side feed |
| `Output\SIDE_DRAW` | MASS-FLOW | Side draw taken from an underflow |
| `Output\LIQ_FLOW` | MASS-FLOW | Side draw taken from an overflow |
