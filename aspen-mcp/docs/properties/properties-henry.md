# Henry components

Dissolved gases whose liquid solubility the property method takes from Henry's law.

Root: `\Data\Components\Henry-Comps\{id}`

1. `add_element` on `\Data\Components\Henry-Comps` with an ID.
2. `insert_row` on `Input\CID`, then `set_value` on `CID\#0`, `#1`, ...; the list takes no labels.
3. Name the set in `GHEN` for every block, or in one block's `Input\HENRY_COMPS` ([common.md](../blocks/common.md)).

| Path | Type | Purpose |
|---|---|---|
| `Input\CID\{row}` | component ID | A component handled by Henry's law |
| `\Data\Properties\Specifications\Input\GHEN` | ID | Henry set of the whole flowsheet |

Henry constants need no input: the run's input carries the databank values for CO2 in water.

Named on a block, the set goes into that block's property options and not into the global ones.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\MOLEFRAC\MIXED\CO2` | fraction | CO2 left dissolved in the flash liquid |
