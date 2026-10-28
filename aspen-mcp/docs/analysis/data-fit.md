# Data fit: data sets

Measurements that a Data-Fit regression ([data-fit-regression.md](data-fit-regression.md)) compares with the model: point data (each row one steady operating point) or profile data (values along a batch time or a reactor length).

Root: `\Data\Model Analysis Tools\Data-Fit\Data-Set\{id}`

## Setup

1. Create it with `add_element` on `\Data\Model Analysis Tools\Data-Fit\Data-Set` and `<ID>!POINT-DATA` or `<ID>!PROFILE-DATA`.
2. Row `#0` of `Input\USE` exists and is a `STD-DEV` row. Each `insert_row` on `Input\USE` adds a data row and its cells in `VALUE` (and in `TIME` for a profile).

A `STD-DEV` row gives each column's standard deviation for the rows below it; row `#0` starts at `INPUT` 0 and `RESULT` 1 (the profile run sets 0.001 for a mass fraction).

## Point data

Define rows: as in [flowsheeting.md](../flowsheeting/flowsheeting.md) (Define a variable). A variable can be a model input (the value is set before the point runs) or a measured result.

Only a variable that is a model input has `INPUT` cells (here the flash temperature `TF`, not the vapor flow `VF`).

| Path | Type | Purpose |
|---|---|---|
| `Input\USE\{row}` | `DATA`, `STD-DEV`, `IGNORE` | Row kind: measurements, standard deviations, skipped |
| `Input\VALUE\{row}\{var}\INPUT` | real | Value of `{var}` set as a model input in this row |
| `Input\VALUE\{row}\{var}\RESULT` | real | Measured value of `{var}`, compared with the model |

## Profile data

| Path | Type | Purpose |
|---|---|---|
| `Input\BLOCKTYPE` | `RPLUG`, `RBATCH`, `BATCHOP`, `BATCHCRYSTAL`, `BFERM` | Type of the block profiled |
| `Input\BLOCK` | ID | The block |
| `Input\FVN_VARIABLE\{var}` | `MOLEFRAC-L`, `MASSFRAC-L`, `MOLECONC-L`, `MASSCONC-L`, `MOLEFRAC-V`, `PARTIAL-PRES`, `TEMPERATURE`, `PRESSURE` | Measured quantity; the row is `insert_row` + a label naming it |
| `Input\FVN_ID2\{var}` | ID | Component of a composition variable |
| `Input\UNITS` | string | Unit of the profile coordinate: a length for `RPLUG`, a time for batch types |
| `Input\TIME\{row}` | real | Coordinate of the row (time, or length for `RPLUG`) |
| `Input\VALUE\{row}\{var}` | real | Measured value |
| `Input\TEMP` | TEMPERATURE | Temperature at the start of the profile |
| `Input\PRES` | PRESSURE | Pressure at the start of the profile |
| `Input\FLOW\{comp}` | MOLE-FLOW | Component flows at the start of the profile |
