# Selector

Passes one of its inlet streams through to the outlet unchanged; the other inlets end there. Paths are under `\Data\Blocks\{name}\`. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` material inlets and `P(OUT)` material outlet; `HS(IN)`/`HS(OUT)` for heat streams, `WS(IN)`/`WS(OUT)` for work streams.

An inlet port keeps every stream connected to it; an outlet port holds one stream, and Aspen refuses a second. Each stream kind goes only on its own ports.

Nothing besides the ports is required.

When the Selector is the only block, write at least one input (`STREAM` does it); left untouched, the run returns no results.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\STREAM` | stream ID | The inlet whose flow and conditions are copied to the outlet |

Left empty, `STREAM` defaults to the inlet that was connected first (connection order, not name order).

Name a stream that is on an inlet port: the field also takes an outlet or an unconnected stream ID, but the run then returns no results.

Heat streams: connect them to `HS(IN)`, the outlet to `HS(OUT)`, and set `STREAM` to the one to pass; the outlet carries that duty.

Work streams work the same way on `WS(IN)` and `WS(OUT)`; the outlet carries the chosen power.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STRMID` | stream ID | The inlet that was passed |

The block has no other results: read temperature, pressure and flows on the outlet stream, where they equal the chosen inlet's.

Not covered: none.
