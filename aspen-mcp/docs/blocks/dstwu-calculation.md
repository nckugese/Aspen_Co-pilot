# DSTWU reflux table and HETP

Paths are under `\Data\Blocks\{name}\`. Optional extras on the Calculation Options sheet.

## Reflux ratio against stages

Rows run from `LOWER` to `UPPER`, labelled with the stage count: 7 points or a step of 3 over 12 to 30 both give 12, 15, ..., 30.

In `NUMBER` mode write `NPOINT` even when 11 is wanted: the 11 shown is not applied, and the table gets one row per stage.

| Path | Type | Purpose |
|---|---|---|
| `Input\PLOT` | `NO`, `YES` | Build a table of reflux ratio against stage count |
| `Input\LOWER` | int | Lowest stage count in the table |
| `Input\UPPER` | int | Highest stage count in the table |
| `Input\OPT_SZNO` | `NUMBER`, `SIZE` | Table rows set by a count (`NPOINT`) or a step (`INCR`) |
| `Input\NPOINT` | int | Number of rows (`NUMBER`) |
| `Input\INCR` | int | Step between rows (`SIZE`) |
| `Input\PRECISION` | `STD`, `HIGH` | Digits kept in the table: standard or high |

## HETP

`HETP` is `PACK_HEIGHT` divided by `ACT_STAGES`.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_CALHETP` | `NO`, `YES` | Work out the HETP from a packed height |
| `Input\PACK_HEIGHT` | LENGTH | Packed height the stages must fit in |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\RR_OUT\{nst}` | ratio | Reflux ratio for that stage count |
| `Output\HETP` | LENGTH | Height of packing per theoretical stage |
