# Screen

Splits the solids of a feed by particle size on one or more screen decks; each deck sends its coarse fraction to an outlet and passes its fines to the next deck. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `O(OUT)` coarse of deck 1, `U(OUT)` fines of the last deck, `MS(OUT)` one stream per lower deck's coarse.

The feed needs a solid substream with a size distribution; a working setup is calcite in `CIPSD` (stream class `MIXCIPSD`).

Every per-deck field is a list indexed `1` to `NDECKS` (top deck first); setting `NDECKS` creates the indices.

Each deck needs `MODEL`. `PLITT`, `ROGERS`, `MOLERUS` and `WHITEN` then need `CUT_SIZE` and `SHARPNESS`; `IDEAL` needs `CUT_SIZE`; `BOM` and `USER-SPEC` need `DECK_OPENING`.

With `NDECKS` 2 or more, connect a stream to `MS(OUT)` for each deck below the first and name it in `COARSE_STRM\{n}`; otherwise the block stays incomplete.

`BOM` and `USER-SPEC` work on a one-deck screen only: with two decks the block stays incomplete.

The block-level `MODE`, `LEVEL` and `OPENING` do not take effect: use `DECK_MODE`, `DECK_LEVEL` and `DECK_OPENING`.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\NDECKS` | int | Number of decks (default 1) |
| `Input\MODEL\1` | `PLITT`, `ROGERS`, `MOLERUS`, `WHITEN`, `IDEAL`, `BOM`, `USER-SPEC` | Grade-efficiency model of the deck: four classifier curves, ideal cut, Bureau of Mines correlation ([strength](screen-separation-strength.md)) or a size table ([selection function](screen-selection-function.md)) |
| `Input\CUT_SIZE\1` | LENGTH | Cut size: half of the particles of this size stay on the deck |
| `Input\SHARPNESS\1` | real | Sharpness of the cut (curve models) |
| `Input\FINES_OFFSET\1` | fraction | Share of the fines that bypass to the coarse outlet (curve models) |
| `Input\WHITEN_BETA\1` | real | `WHITEN` with an offset above 0: shape parameter beta |
| `Input\DECK_OPENING\1` | LENGTH | Mesh opening (`BOM`, `USER-SPEC`) |
| `Input\DECK_MODE\1` | `WET`, `DRY` | `BOM`: wet (default) or dry screening |
| `Input\DECK_LEVEL\1` | `UPPER`, `LOWER` | `BOM`: upper (default) or lower deck of the machine |
| `Input\COARSE_STRM\{n}` | stream | Outlet stream for the coarse of deck n (a stream on `MS(OUT)`) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash |
| `Input\PHASE` | `L`, `V`, `S` | The phase when `NPHASE` is 1 |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EFF` | fraction | Overall efficiency: oversize recovered to the overflow plus undersize to the underflow, as a share of the feed |
| `Output\OVERSZ_EFF` | fraction | Share of the feed oversize that leaves on `O(OUT)` |
| `Output\UNDERSZ_EFF` | fraction | Share of the feed undersize that leaves on `U(OUT)` |
| `Output\TAGGART_EFF` | fraction | Taggart efficiency |
| `Output\FINES_D50` | LENGTH | Median particle size in `U(OUT)` |
| `Output\COARSE_D50\1` | LENGTH | Median particle size of the coarse of deck 1 |
| `Output\DECK_OVEF\1` | fraction | Oversize efficiency of deck 1 |
| `Output\DECK_UDEF\1` | fraction | Undersize efficiency of deck 1 |

`OVERSZ_EFF` and `UNDERSZ_EFF` split the feed at the cut size (or the opening); `EFF` is their feed-weighted sum.

More: [fluid split](screen-fluid.md), [separation strength](screen-separation-strength.md), [selection function](screen-selection-function.md).

Not covered: Selection-function splines and fits (`INTERPOLATE` LIN-SPLINE, LOG-SPLINE, FITTING with `OPT_PLITT`, `OPT_ROGERS`, `OPT_MOLERUS`, `OPT_WHITEN`) (every run stops the Aspen engine); Heating curves, Utility (shared forms that this block's tree does not carry).
