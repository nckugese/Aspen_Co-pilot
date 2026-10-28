# Data fit: regression

Adjusts varied inputs so that the model matches the measurements of one or more data sets ([data-fit.md](data-fit.md)), by weighted least squares.

Root: `\Data\Model Analysis Tools\Data-Fit\Regression\{id}`

## Setup

1. Create it with `add_element` on `\Data\Model Analysis Tools\Data-Fit\Regression` and an ID.
2. Data sets: `insert_row` on `Input\WEIGHT`, label the row with the data set ID and write its weight.
3. Vary rows as for a sensitivity ([sensitivity.md](sensitivity.md)): `insert_row` on `Input\VARY_VARTYPE`, then type, block or stream, variable, `LOWER` and `UPPER`.

The fit recovers the value the data were made with: 1 atm (1.013 bar) for the point data, 70 C for the profile.

With `EVALONLY` `YES` the varied inputs keep their values and only the comparison is reported.

Set `AFCTOL` well below the sum of squares you expect at the fit (both runs use 1e-10): at the default 0.01 the fits stopped on that tolerance with a warning.

## Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\WEIGHT\{set}` | real | Weight of a data set (`insert_row` + its ID as label) |
| `Input\EVALONLY` | `NO`, `YES` | Fit, or only compare the model at the current values |

## Vary

| Path | Type | Purpose |
|---|---|---|
| `Input\VARY_VARTYPE\{row}` | `BLOCK-VAR`, `STREAM-VAR`, `MOLE-FLOW` | Kind of input fitted |
| `Input\LOWER\{row}` | real | Lower limit |
| `Input\UPPER\{row}` | real | Upper limit |
| `Input\DISABLE\{row}` | `NO`, `YES` | Keep this row fixed |

## Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\MAX_ITER` | int | Iteration limit |
| `Input\MXFCAL` | int | Limit on flowsheet passes |
| `Input\AFCTOL` | real | Absolute tolerance on the sum of squares |
| `Input\RFCTOL` | real | Stops when the sum of squares changes by less than this fraction |
| `Input\XCTOL` | real | Tolerance on the fitted values |
| `Input\XFTOL` | real | Smallest step before it stops |
| `Input\BOUNDFAC` | real | Bound factor of the first steps |
| `Input\INIRIN` | `BASE-CASE`, `MEASUREMENTS` | Starting values of measured inputs: the model's, or the data |
| `Input\COVAR_REQ` | `YES`, `NO` | Report the covariance and correlation matrices |

## Advanced

| Path | Type | Purpose |
|---|---|---|
| `Input\INIT_STEP` | real | Size of the first step |
| `Input\PERT_FAC` | real | Relative perturbation for the derivatives |
| `Input\SIM_LEVEL` | int | Level of diagnostic messages, 0-10 |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BLKSTAT` | int | 0 when it converged |
| `Output\CVSTAT` | string | Which tolerance ended the fit |
| `Output\ESTVALUE\{n}` | real | Fitted value of vary row n |
| `Output\STAND_DEV\{n}` | real | Its standard deviation |
| `Output\RECVALUE\{set}\{k}` | real | Model value at measurement k of a data set |
| `Output\RESIDUAL\{set}\{k}` | real | Residual at measurement k |
