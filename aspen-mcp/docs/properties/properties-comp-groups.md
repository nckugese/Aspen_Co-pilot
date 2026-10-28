# Component groups

A named set of components; prop-set qualifiers and other fields that take a group name it by ID.

Root: `\Data\Components\Comp-Groups\{id}`

1. `add_element` on `\Data\Components\Comp-Groups` with an ID.
2. A list: `insert_row` on `Input\L1\MIXED`, then `set_value` on `#0`, `#1`, ...
3. A range: `insert_row` + `set_label` on `Input\T2\MIXED` with the first component, then `set_value` with the last; the group holds every component between them in the component list.

| Path | Type | Purpose |
|---|---|---|
| `Input\L1\MIXED\{row}` | component ID | A member of a listed group |
| `Input\T2\MIXED\{comp}` | component ID | Last member of a range starting at the row's label |

A prop-set qualified by a group reports its members only.

A range gives each component from the first to the last.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\STRM_UPP\MOLEFRAC\MIXED\LIQUID\{comp}` | fraction | Mole fraction of that member in the liquid |
