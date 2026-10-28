# Valve parameters

Valve data for `SET-PRESSURE` and `CALC-PRESSURE`: a library valve, a characteristic equation, or a table. Give one of the three. Paths are under `\Data\Blocks\{name}\`.

A library valve locks the equation fields and an equation locks the library fields.

## Input | Valve Parameters: library valve

| Path | Type | Purpose |
|---|---|---|
| `Input\VAL_TYPE` | `BALL`, `BUTTERFLY`, `GLOBE` | Valve type |
| `Input\MFGR` | string | Maker; the shipped library has `NELES-JAMESBURY` |
| `Input\SERIES` | string | Series: `BALL` `5000_REDUCED_PORT_FLANGED`, `METAL_SEATED_FULL_PORT`; `BUTTERFLY` `ANSI_CLASS_150`, `ANSI_CLASS_300`; `GLOBE` `V500_` or `V810_` + `LINEAR_FLOW` or `EQUAL_PERCENT_FLOW` |
| `Input\SIZE` | string | Nominal size as `<inches>-IN`, e.g. `2-IN`; the sizes differ per series |

Each type sizes the same duty: the opening and Cv come out for globe, ball and butterfly.

## Input | Valve Parameters: characteristic equation

| Path | Type | Purpose |
|---|---|---|
| `Input\CHAR_EQN` | `LINEAR`, `PARABOLIC`, `HYPERBOLIC`, `SQUARE-ROOT`, `QUICK-OPENING`, `EQUAL-PERCENTAGE` | Shape of Cv against opening |
| `Input\MAX_FLO_COEF` | number | Cv fully open |
| `Input\PDRP_FAC` | number | xT, the factor that fixes where a gas chokes |
| `Input\PREC_FAC` | number | Liquid pressure recovery factor FL (liquid choking) |

The shape changes the opening, not the Cv: all six find Cv 6.28; `LINEAR` gives 12.6 % (Cv / Cv max).

## Input | Valve Parameters: table

1. `insert_row` on `Input\VP_DAT`; the row (`#0`, `#1`, ...) appears in `CV_DAT`, `XT_DAT` and `FL_DAT` too.
2. Fill the four cells of each row.

| Path | Type | Purpose |
|---|---|---|
| `Input\VP_DAT\{row}` | percent | Opening |
| `Input\CV_DAT\{row}` | number | Cv at that opening |
| `Input\XT_DAT\{row}` | number | xT at that opening |
| `Input\FL_DAT\{row}` | number | FL at that opening |

Give at least 4 rows: with 3 the block stays incomplete.

The table sized the duty at 13 % and rated 50 % open.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\PDROP_FAC` | number | xT used |
| `Output\PRREC_FAC` | number | FL used |
| `Output\CRIT_PRS_FAC` | number | FF, used for the liquid choking limit |

With the equation the factors used are the ones given (0.7, 0.9); a library valve takes them from its data.
