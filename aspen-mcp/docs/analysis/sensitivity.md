# Sensitivity

Runs the flowsheet once per case, a case being one set of values for the varied inputs, and tabulates chosen results for every case.

Root: `\Data\Model Analysis Tools\Sensitivity\{id}`

## Setup

1. Create it with `add_element` on `\Data\Model Analysis Tools\Sensitivity` and an ID.
2. Vary: `insert_row` on `Input\VARY_VARTYPE` adds row `#n` to every vary field; vary rows take no label.
3. Fill a vary row with the fields of [flowsheeting.md](../flowsheeting/flowsheeting.md) (Vary an input), here lists `<field>\{row}`, in order: `VARY_VARTYPE`, then `VARYBLOCK` or `VARYSTREAM` (and `VARYCOMPONEN`), then `VARYVARIABLE`; a field is refused until the ones before it are set. `VARYSENTENCE` fills itself.
4. Define the variables the table reads, as in [flowsheeting.md](../flowsheeting/flowsheeting.md) (Define a variable).
5. Tabulate: `insert_row` on `Input\EXPR`, label the row with its column number (`1`, `2`, ...) and write a define variable or an expression of them.

Fortran lines (`insert_row` on `Input\FORTRAN_EXEC`, code from column 7) run before the table is filled; a variable they set can be tabulated.

A range by `INCR` runs every step from `LOWER` to `UPPER`; `OLIST` runs exactly the listed values; `LOGARITHMIC` spaces the points by an even ratio of the absolute value (a temperature in K).

Two vary rows give every combination of their values; with `SERIES` `YES` each row is varied alone while the other keeps its base value.

With `CASES` `YES` you list the cases: `insert_row` on `Input\ACTIVE` once per case, then on `Input\VALUES\{case}` once per vary row.

## Vary

| Path | Type | Purpose |
|---|---|---|
| `Input\VARY_VARTYPE\{row}` | `BLOCK-VAR`, `STREAM-VAR`, `MOLE-FLOW`, `MASS-FLOW`, `CONFIG-VAR` | Kind of input varied |
| `Input\OPT_LIST\{row}` | `RANGE`, `OLIST`, `LOGARITHMIC` | How the values are given: an even range, a list, a range with even ratios |
| `Input\OPT_RANGE\{row}` | `NPOINT`, `INCR` | A range by number of points or by step |
| `Input\LOWER\{row}` | string | First value of the range |
| `Input\UPPER\{row}` | string | Last value of the range |
| `Input\NPOINT\{row}` | string | Number of points (`NPOINT`) |
| `Input\INCR\{row}` | string | Step (`INCR`) |
| `Input\LIST\{row}\{i}` | real | One listed value (`OLIST`; `insert_row` on `LIST\{row}` per value) |

## Tabulate and Fortran

| Path | Type | Purpose |
|---|---|---|
| `Input\EXPR\{n}` | string | Column n: a define variable or an expression |
| `Input\FORTRAN_EXEC\{row}` | string | One executable Fortran line |
| `Input\FORTRAN_DEC\{row}` | string | One declaration line |

## Cases

| Path | Type | Purpose |
|---|---|---|
| `Input\CASES` | `NO`, `YES` | Cases from the vary rows, or listed one by one |
| `Input\ACTIVE\{case}` | `YES`, `NO` | Run this case |
| `Input\VALUES\{case}\{i}` | real | Value of vary row i in this case |

## Options

| Path | Type | Purpose |
|---|---|---|
| `Input\BASE_CASE` | `LAST`, `FIRST`, `NO` | When the base case (inputs as entered) runs: after the cases, before them, never |
| `Input\SERIES` | `NO`, `YES` | Vary rows in every combination, or one row at a time; `YES` not with `CASES` `YES` |
| `Input\TOGBL` | `NONE`, `INCLUDE`, `ALL` | Blocks reset before each case: none, those listed, all |
| `Input\BLOCKS\{row}` | ID | A block to reset (`INCLUDE`) |
| `Input\TOGST` | `NONE`, `INCLUDE`, `ALL` | Streams reset before each case: none, those listed, all |
| `Input\STREAMS\{row}` | ID | A stream to reset (`INCLUDE`) |
| `Input\SORT` | `YES`, `NO` | Sort the report table by the vary values |
| `Input\HIGH_PRECISI` | `STD`, `HIGH` | Significant figures in the report table: standard or more |
| `Input\SIM_LEVEL` | int | Level of diagnostic messages, 0-10 |

## Results (after a run)

The base case gets a row of its own unless its values are already one of the cases.

| Path | Type | Purpose |
|---|---|---|
| `Output\BLKSTAT` | int | 0 when it ran |
| `Output\SENSVAR\{case}\{col}` | real | Result table: one row per case; the vary values first, then the tabulated columns in order |
| `Output\ROWSTAT\{case}` | int | 0 when that case converged |
| `Output\VARID\{n}` | string | Name of define variable n |
| `Output\VALUE\{n}` | real | Its value in the base case |

More: optimization of the same variables: [optimization.md](optimization.md).

Not covered: Vary summary view (a read-only view of the vary rows).
