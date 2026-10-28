# USER3: variable initial values

Starting values for the model's variables, by name or by row number of `Output\VARIABLE` ([user3.md](user3.md)). Paths are under `\Data\Blocks\{name}\`.

1. Insert a row in `Input\VINIT` (or `Input\YINIT`), label it with the variable name (or its row number), then write the value (insert_row, set_label, set_value).

| Path | Type | Purpose |
|---|---|---|
| `Input\VINIT\{variable}` | real | Starting guess for the named model variable |
| `Input\YINIT\{n}` | real | Starting guess for the model variable in row n |

A starting value does not change a fixed variable: with `STRM_2_RATIO` fixed at 0.5, a starting value of 0.3 still leaves an even split.
