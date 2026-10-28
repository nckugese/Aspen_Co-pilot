# MultiFrac design specs

Paths are under `\Data\Blocks\{name}\`. A design spec is met by varying one of the column specs, a duty or a flow.

1. `add_element` on `Subobjects\Design Specs` with an ID (`1`), and on `Subobjects\Vary` with an ID (`1`).
2. Set the target, then its components and streams (lists without labels: `insert_row`, then `#0`).
3. Set what varies, on which column, and its bounds.

## Design spec

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_TYPE\{spec}` | `MOLE-FRAC`, `MASS-FRAC`, `MOLE-RECOV`, `MASS-RECOV`, `MOLE-FLOW`, `MASS-FLOW` | What is specified |
| `Input\VALUE\{spec}` | real | Target value |
| `Input\SPEC_COMPS\{spec}\{row}` | component | Components the target counts |
| `Input\SPEC_STREAMS\{spec}\{row}` | stream | Product streams the target applies to |

## Vary

| Path | Type | Purpose |
|---|---|---|
| `Input\VARTYPE\{vary}` | `D`, `RR`, `L1`, `DUTY`, `LPROD`, `VPROD`, `DV:D` | What is varied: a column spec, a stage duty, a side-product rate |
| `Input\VARY_COL\{vary}` | int | Column of the varied quantity |
| `Input\VARY_STAGE\{vary}` | int | Its stage, for a stage duty |
| `Input\LB\{vary}` | real | Lower bound |
| `Input\UB\{vary}` | real | Upper bound |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\CALC\{spec}` | real | Value reached by the spec |
| `Output\VAR_VAL\{vary}` | real | Varied quantity at the solution |
