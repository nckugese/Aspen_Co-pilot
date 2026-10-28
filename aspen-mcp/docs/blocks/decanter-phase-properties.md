# Decanter: KLL correlation and phase properties

A fitted K for each component, or a property method per liquid. Paths are under `\Data\Blocks\{name}\`.

## Properties | KLL Correlation (with `KLL_CORR` `POLYNOMIAL`)

`ln K = a + b/T + c ln T + d T`, T in K; `K` is x(L1) / x(L2), the inverse of the `B_K` result.

1. `KLL_CORR` `POLYNOMIAL`; until coefficients are given the block is incomplete.
2. Add one row per component to `COEFFA`, labelled with the component ID (`insert_row`); `COEFFB` to `COEFFD` get the same rows.
3. Give `COEFFA` for every component (0 when only b, c or d is used); `COEFFB` to `COEFFD` may stay empty.

| Path | Type | Purpose |
|---|---|---|
| `Input\COEFFA\{comp}` | number | a |
| `Input\COEFFB\{comp}` | number | b (times 1/T) |
| `Input\COEFFC\{comp}` | number | c (times ln T) |
| `Input\COEFFD\{comp}` | number | d (times T) |
| `Input\BASIS` | `MOLE`, `MASS`, `STDVOL` | Fraction basis of K (default `MOLE`) |

The same coefficients on a `MASS` basis give another split.

## Properties | Phase Properties

| Path | Type | Purpose |
|---|---|---|
| `Input\L1OPSET` | property method | Method for the first liquid (`L2OPSET`: second liquid); empty uses the block's |
| `Input\L1SOLU_WATER` | `0`, `1`, `2`, `3`, `4`, `5` | Water solubility method for that liquid (`L2SOLU_WATER`) |
| `Input\L1HENRY_COMP` | Henry-Comps ID | Henry components for that liquid (`L2HENRY_COMP`) |
| `Input\L1TRUE_COMPS` | `YES` | `YES` for true species (`L2TRUE_COMPS`); `NO` was refused with NRTL |

`L2OPSET` `UNIQUAC` with `L1OPSET` `NRTL` converged with another split than NRTL for both.
