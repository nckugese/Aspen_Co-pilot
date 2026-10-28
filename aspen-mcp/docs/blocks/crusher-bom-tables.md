# Crusher: BOM selection and breakage tables

BOM types (gyratory, roll, cage mill): `SEL_FUN` or `BREAK_FUN` `USER-SPEC` replaces the built-in curve by a table (Selection Function and Breakage Function sheets). Paths are under `\Data\Blocks\{name}\`; basics in [crusher.md](crusher.md).

1. Set `SEL_FUN` = `USER-SPEC` and insert one row per point into `SIZE_RAT1` (`insert_row`); `VALUE1` gets the same row `#n`.
2. For breakage set `BREAK_FUN` = `USER-SPEC` and fill `SIZE_RAT2`/`VALUE2` (particles above the cut-off) or `SIZE_RAT3`/`VALUE3` (below) the same way. One of the two tables is enough; with `USER-SPEC` and no table the block stays incomplete.

## Tables

| Path | Type | Purpose |
|---|---|---|
| `Input\SEL_FUN` | `BOM`, `USER-SPEC` | Selection function: built-in or table |
| `Input\BREAK_FUN` | `BOM`, `USER-SPEC` | Breakage function: built-in or table |
| `Input\SIZE_RAT1\{row}` | fraction | Size ratio of the selection point |
| `Input\VALUE1\{row}` | fraction | Share of particles at that ratio that break |
| `Input\SIZE_RAT2\{row}` | fraction | Fragment size over parent size (above the cut-off) |
| `Input\VALUE2\{row}` | fraction | Cumulative share of fragments below that ratio |
| `Input\SIZE_RAT3\{row}` | fraction | Fragment size over parent size (below the cut-off) |
| `Input\VALUE3\{row}` | fraction | Cumulative share of fragments below that ratio |
| `Input\RATIO_CUT` | ratio | Cut-off size over `DIAM`, which picks the breakage table (default 1.7) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\POWER` | POWER | Grinding power |
| `Output\OUTLET_D50` | LENGTH | Median size of the product solids |
