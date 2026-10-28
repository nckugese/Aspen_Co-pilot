# SSplit: key components

A flow spec can count only some components of a substream (a key group): the outlet then gets that flow of the key components, with the other components in the feed's proportion. Paths are under `\Data\Blocks\{name}\`.

1. Write the group number on the outlet and substream, `Input\BASIS_KEYNO\{stream}\{substream}`; this creates `Input\COMPS\{id}`.
2. `insert_row` on `Input\COMPS\{id}` once per component (rows `#0`, `#1`, ...) and write each component ID as the row's value; these rows take no label.
3. Give that cell a flow, `Input\BASIS_FLOW\{stream}\{substream}`: it now counts the key components only.

| Path | Type | Purpose |
|---|---|---|
| `Input\BASIS_KEYNO\{stream}\{substream}` | int | Key group used by the cell's flow spec |
| `Input\COMPS\{id}\{row}` | component ID | A component of key group `{id}` |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STREAMFRAC\{stream}\{substream}` | fraction | Fraction of the substream the key spec gave |
