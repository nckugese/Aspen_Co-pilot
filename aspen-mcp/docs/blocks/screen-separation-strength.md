# Screen: separation strength

`MODEL` = `BOM`: the Bureau of Mines correlation turns a separation strength into the grade efficiency of the deck. Paths are under `\Data\Blocks\{name}\`; basics in [screen.md](screen.md).

Only `BOM` reads this sheet; a curve model with `OPT_SEP` set gives the same result as without.

`BUILT-IN` (default) takes the strength from a correlation that also depends on `DECK_MODE` and `DECK_LEVEL`; `SCALAR` needs `STRENGTH`.

`USER`: the block interpolates the table linearly at `DECK_OPENING`; one row per point (`insert_row` on `SIZE1`, the `VALUE1` row follows).

## Fields

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_SEP` | `BUILT-IN`, `SCALAR`, `USER` | Source of the strength: correlation, one value, or a table against opening |
| `Input\STRENGTH` | real | `SCALAR`: the strength |
| `Input\SIZE1\{row}` | LENGTH | `USER`: opening of the point |
| `Input\VALUE1\{row}` | real | `USER`: strength at that opening |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STRENGTH_OUT\1` | real | Strength used on deck 1 |
| `Output\DECK_OPEN\1` | LENGTH | Opening of deck 1 |
