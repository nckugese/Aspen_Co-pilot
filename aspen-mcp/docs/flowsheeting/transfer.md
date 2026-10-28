# Transfer

Copies a whole stream, its flows, one substream or one variable onto other streams or variables each time it runs.

Root: `\Data\Flowsheeting Options\Transfer\{id}`

1. `add_element` on `\Data\Flowsheeting Options\Transfer` with an ID.
2. Set `OPT_COPY`, then the source, then each target.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_COPY` | `ENTSTRM`, `STRM`, `SUBSTRM`, `OBLOCK` | What it copies: a whole stream, the flows of a stream, one substream, one variable |

The target keeps its own `Input`; the copy shows in its results (G: `Input` 20 C, results 95 C).

`STRM` copies the flows only: G keeps its 20 C, while `ENTSTRM` and `SUBSTRM` bring the vapor's 95 C along.

Left at `AUTOMATIC`, the run places the transfer itself: H1 ran at the flash's 95 C instead of its own 50 C.

## Streams

| Path | Type | Purpose |
|---|---|---|
| `Input\EQ_STRM1` | stream ID | `ENTSTRM`: source stream |
| `Input\SET_STRM1\{row}` | stream ID | `ENTSTRM`: a target stream; `insert_row` first |
| `Input\EQ_FLOWS` | stream ID | `STRM`: source stream |
| `Input\SET_FLOWS\{row}` | stream ID | `STRM`: a target stream; `insert_row` first |
| `Input\EQ_STREAM` | stream ID | `SUBSTRM`: source stream |
| `Input\EQ_SUB` | substream | `SUBSTRM`: its substream (`MIXED`, ...) |
| `Input\SUB_SUB\{stream}` | substream | `SUBSTRM`: one row per target, labelled with the target stream (`insert_row`, `set_label`); the value is its substream |

## Variable (`OBLOCK`)

| Path | Type | Purpose |
|---|---|---|
| `Input\EQVARTYPE` | `BLOCK-VAR`, `STREAM-VAR` | Kind of the source variable |
| `Input\EQBLOCK` | block ID | Source block (`BLOCK-VAR`) |
| `Input\EQSTREAM` | stream ID | Source stream (`STREAM-VAR`) |
| `Input\EQVARIABLE` | variable name | Source variable (`TEMP`, ...); `EQSENTENCE` fills itself |
| `Input\VARY_VARTYPE\{row}` | `BLOCK-VAR`, ... | A target: one row of the vary lists ([flowsheeting.md](flowsheeting.md#vary-an-input)); `insert_row` on `Input\VARY_VARTYPE` first |
| `Input\VARYBLOCK\{row}` | block ID | Target block |
| `Input\VARYVARIABLE\{row}` | variable name | Target variable |

## Sequence

| Path | Type | Purpose |
|---|---|---|
| `Input\WHEN` | `AUTOMATIC`, `BEFORE` | Placed by the run (the default), or just before the object in `BLK_ID` |
| `Input\BLOCK_TYPE` | `BLOCK`, `CONVERGENCE`, `CALCULATOR`, `TRANSFER`, `BALANCE` | Kind of object `BLK_ID` names |
| `Input\BLK_ID` | ID | The object it runs before |

## Diagnostics

| Path | Type | Purpose |
|---|---|---|
| `Input\TERM_LEVEL` | int 0-10 | Detail of messages on the control panel |
| `Input\SIM_LEVEL` | int 0-10 | Detail of messages in the history |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BLKSTAT` | int | 0 when it ran without error |
