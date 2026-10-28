# Flowsheeting options

Objects that read flowsheet values while the run goes and set inputs from them: a [design spec](design-spec.md), a [calculator](calculator.md), a [transfer](transfer.md) and a [balance](balance.md).

Root: `\Data\Flowsheeting Options\{kind}\{id}`

`{kind}` is `Design-Spec`, `Calculator`, `Transfer` or `Balance`. Create one with `add_element` on `\Data\Flowsheeting Options\{kind}` and an ID.

The define rows below work the same way on a sensitivity, an optimization and a constraint (`\Data\Model Analysis Tools\{kind}\{id}`).

## Define a variable

A defined variable names one flowsheet value; spec expressions and Fortran lines use that name.

1. `insert_row` on `Input\FVN_VARTYPE`, then `set_label` with the name (at most 8 characters). The row appears in every `FVN_` list.
2. `set_value` the type first, then its stream or block, then the variable or component: each field is enterable only once the one before it is set.

| Path | Type | Purpose |
|---|---|---|
| `Input\FVN_VARTYPE\{var}` | `STREAM-VAR`, `MOLE-FLOW`, `MOLE-FRAC`, `MASS-FLOW`, `MASS-FRAC`, `BLOCK-VAR` | Kind: a total stream value, a component's flow or fraction in a stream, a block value |
| `Input\FVN_STREAM\{var}` | stream ID | Stream (the stream kinds) |
| `Input\FVN_SUBS\{var}` | substream | Substream; fills itself with `MIXED` once the stream is set |
| `Input\FVN_COMPONEN\{var}` | component ID | Component (`MOLE-FLOW`, `MOLE-FRAC`, `MASS-FLOW`, `MASS-FRAC`) |
| `Input\FVN_BLOCK\{var}` | block ID | Block (`BLOCK-VAR`) |
| `Input\FVN_VARIABLE\{var}` | variable name | `STREAM-VAR`: `TEMP`, `PRES`, `VFRAC`, `MOLE-FLOW`, `MASS-FLOW`, ...; `BLOCK-VAR`: an input or result of that block (a Flash2: `TEMP`, `PRES`, `QCALC`, ...) |
| `Input\FVN_SENTENCE\{var}` | sentence | Group of a block variable; fills itself (`PARAM`) once the variable is set |
| `Input\FVN_UOM\{var}` | unit name | Unit the value is read and written in; default: the run's unit set |

## Vary an input

A design spec varies one input and these fields hold one value each. In a transfer they are lists without labels: `insert_row` on `Input\VARY_VARTYPE`, then `set_value` on `<field>\#0`, `#1`, ...

| Path | Type | Purpose |
|---|---|---|
| `Input\VARY_VARTYPE` | `BLOCK-VAR`, `STREAM-VAR`, `MOLE-FLOW` | Kind: a block input, a total stream value, one component's flow in a stream |
| `Input\VARYBLOCK` | block ID | Block (`BLOCK-VAR`) |
| `Input\VARYSTREAM` | stream ID | Stream (`STREAM-VAR`, `MOLE-FLOW`) |
| `Input\VARYCOMPONEN` | component ID | Component (`MOLE-FLOW`) |
| `Input\VARYVARIABLE` | variable name | A block input (`TEMP`, `PRES`, `DUTY`, ...) or a stream's `TEMP`, `PRES`, `MOLE-FLOW`, ... |
| `Input\VARYSENTENCE` | sentence | Fills itself once the variable is set |
| `Input\VARYUOM` | unit name | Unit of the limits; default: the run's unit set |

Not covered: calculator EO options, transfer EO options (equation-oriented mode, not checked); calculator tear variables, flash options of streams a balance computes, balance linear equations, balance scale factors, other define and vary kinds (vectors, prop-set values, parameters, ...) (not checked); Excel calculators (need a workbook open in Excel; not run unattended).
