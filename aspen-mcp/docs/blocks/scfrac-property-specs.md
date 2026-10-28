# SCFrac property specs

Paths are under `\Data\Blocks\{name}\`. A spec on a product property (e.g. API gravity) reads it from a property set.

1. `add_element` on `\Data\Properties\Prop-Sets` with an ID, e.g. `PS-1`.
2. `insert_row` on its `Input\UNITS` with the property name as the label, e.g. `API`: one scalar property per set.
3. On the spec row set `SPECTYPE`, then `SPEC_STREAM` and `PROPERTY`; `PROP-DIFF` and `PROP-RATIO` also take the base fields.

| Path | Type | Purpose |
|---|---|---|
| `Input\PROPERTY\{spec}` | Prop-Set ID | Property of `SPEC_STREAM` |
| `Input\BASE_STREAM\{spec}` | stream | Base product: spec value minus (`PROP-DIFF`) or over (`PROP-RATIO`) its value |
| `Input\BASE_PROPERT\{spec}` | Prop-Set ID | Property of the base product |
| `Input\FLASH\{spec}` | `NO`, `YES` | Flash the product at each iteration before reading the property |
