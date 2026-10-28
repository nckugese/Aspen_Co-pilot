# PetroFrac design specs and runback specs

Paths are under `\Data\Blocks\{name}\`. A design spec meets a product target by adjusting one column input; a runback spec holds the liquid leaving a stage at a set rate by adjusting the duty on a stage.

## Design Specs

1. `add_element` on `Subobjects\Design Specs` with an ID, e.g. `1`; its fields are keyed by that ID.
2. Set the spec type and value, add rows to the component and stream lists, then pick what is adjusted.

The entered value of the adjusted input is only the starting point; `Output\VAR_VAL\{id}` holds the final one.

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_TYPE\{id}` | `MOLE-FRAC`, `MASS-FRAC`, `STDVOL-FRAC`, `MOLE-RECOV`, `MASS-RECOV`, `STDVOL-RECOV`, `MOLE-FLOW`, `MASS-FLOW` | Kind of target |
| `Input\VALUE\{id}` | real | Target value |
| `Input\SPEC_COMPS\{id}\{row}` | component ID | Components the target counts (rows without labels) |
| `Input\SPEC_STREAMS\{id}\{row}` | stream ID | Product streams the target is read on (rows without labels) |
| `Input\VARTYPE\{id}` | `D`, `B`, `RR`, `DUTY`, `LPROD`, `VPROD` | Input adjusted: distillate, bottoms, reflux ratio, a stage duty, or a liquid / vapor side-product rate |

| Path | Type | Purpose |
|---|---|---|
| `Output\VAR_VAL\{id}` | real | Final value of the adjusted input |
| `Output\CALC\{id}` | real | Value reached |

## Runback

1. `insert_row` on `Input\OPT_LSPEC` and `set_label` with the stage whose liquid is held; the row appears in `OPT_LSPEC`, `L_SPEC_QSTAG`, `BASIS_LSPEC` and `LSPEC_BASIS` together.
2. Set `STAGE`, the stage whose duty is adjusted and the rate. That stage needs no side-heater row of its own.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_LSPEC\{stage}` | `STAGE` | What is adjusted: `STAGE`, the duty on a stage |
| `Input\L_SPEC_QSTAG\{stage}` | int | Stage whose duty is adjusted |
| `Input\BASIS_LSPEC\{stage}` | MOLE-FLOW | Liquid rate to hold |
| `Input\LSPEC_BASIS\{stage}` | `MOLE`, `MASS`, `STDVOL` | Basis of that rate |
