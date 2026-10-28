# USER2: Streams

Hands the model the data of flowsheet streams that are not connected to the block, read-only. Paths are under `\Data\Blocks\{name}\`.

1. Insert a row in `Input\STREAMS` (insert_row) and write the stream ID into it.

| Path | Type | Purpose |
|---|---|---|
| `Input\STREAMS\{row}` | stream ID | Extra stream passed to the model, rows `#0`.. |

Each listed stream arrives as one more inlet column after the connected inlets (`NMATI` counts it); the model must not add it to its outlets, or the block is out of mass balance.

The product of another block works too: Aspen computes that block first.
