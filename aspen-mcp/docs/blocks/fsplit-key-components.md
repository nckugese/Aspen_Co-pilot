# FSplit: key components

A flow or limit spec can count only some components (a key group): the outlet then carries that much of the key components, with the rest of the feed in the same proportion. Paths are under `\Data\Blocks\{name}\`.

1. Write the group number on the outlet: `Input\BASIS_KEYNO\{stream}`; this creates `Input\COMPS\{id}`.
2. `insert_row` on `Input\COMPS\{id}` with the substream as label (`MIXED`).
3. `insert_row` on `Input\COMPS\{id}\MIXED` once per component (rows `#0`, `#1`, ...), then write each component ID as the row's value; a component as a label is refused.
4. Give the outlet a flow or limit spec (e.g. `Input\BASIS_FLOW\{stream}`): it now counts the key components only.

| Path | Type | Purpose |
|---|---|---|
| `Input\BASIS_KEYNO\{stream}` | int | Key group used by the outlet's spec |
| `Input\COMPS\{id}\MIXED\{row}` | component ID | A component of key group `{id}` |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STREAMFRAC\{stream}` | fraction | Split fraction the key spec gave |
