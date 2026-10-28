# BatchOp feeds and draws

Paths are under `\Data\Blocks\{name}\`. Streams in and out during the batch (Setup | Operation and the stream fields of the block's flowsheet form).

Connecting the ports fills the stream fields; they need no input.

| Path | Type | Purpose |
|---|---|---|
| `Input\CHARGE_STRM` | stream | Stream on `BC(IN)` |
| `Input\FEED_STRM` | stream list | Streams on `CF(IN)`, each ID followed by `*` |
| `Input\VENT_STRM` | stream | Stream on `VP(OUT)` |
| `Input\DRAW_STRM` | stream | Stream on `LD(OUT)` |
| `Input\FILTER_STRM` | stream | Stream on `FT(OUT)` |

A `CF(IN)` stream flows in at its own rate for the whole batch: 100 kmol charged plus 10 kmol/hr for 2 hr left 120 kmol (`RP(OUT)` 120 kmol/hr over a 1 hr discharge).

## Draws (Setup | Operation)

| Path | Type | Purpose |
|---|---|---|
| `Input\DRAWMASSFLOW\{stream}` | MASS-FLOW | Draw rate of `LD(OUT)` stream `{stream}` for the whole batch |
| `Input\LIQDRAWPH\{stream}` | `L`, `L1`, `L2` | Liquid phase drawn |

The `LD(OUT)` stream shows the draw rate, and that amount leaves the pot: 1000 kg/hr for 2 hr took the contents from 100 to 76.5 kmol.
