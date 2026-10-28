# RadFrac design specs

Paths are under `\Data\Blocks\{name}\`. A design spec is met by varying one of the column's own specs.

1. `add_element` on `Subobjects\Design Specs` with an ID (`1`), and on `Subobjects\Vary` with an ID (`1`).
2. Set the target, then its components and streams (lists without labels: `insert_row`, then `#0`).
3. Set what varies and its bounds; it must be one of the two specs already set on the column.

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_TYPE\{spec}` | `MOLE-FRAC`, `MASS-FRAC`, `MOLE-RECOV`, `MASS-RECOV`, `MOLE-FLOW`, `MASS-FLOW` | What is specified |
| `Input\VALUE\{spec}` | real | Target value |
| `Input\SPEC_COMPS\{spec}\{row}` | component | Components the target counts |
| `Input\SPEC_STREAMS\{spec}\{row}` | stream | Product streams the target applies to |
| `Input\VARTYPE\{vary}` | `D`, `B`, `RR`, `BR`, `D:F`, `B:F`, `L1`, `VN` | Column spec that is varied |
| `Input\LB\{vary}` | real | Lower bound (after `VARTYPE`) |
| `Input\UB\{vary}` | real | Upper bound (after `VARTYPE`) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\CALC\{spec}` | real | Value reached by the spec |
| `Output\VAR_VAL\{vary}` | real | Varied spec at the solution |
