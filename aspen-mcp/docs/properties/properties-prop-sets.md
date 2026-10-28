# Property sets

A named list of properties with their qualifiers; reports, design specs, sensitivities and heating curves name it by ID.

Root: `\Data\Properties\Prop-Sets\{id}`

1. `add_element` on `\Data\Properties\Prop-Sets` with an ID.
2. Each property is a row of `Input\UNITS`: `insert_row`, then `set_label` with the property name (`TBUB`, `RHOMX`, `MUMX`, `VFRAC`, ...); an unknown name is refused.
3. Qualifier lists take no labels: `insert_row`, then `set_value` on `#0`, `#1`, ...

| Path | Type | Purpose |
|---|---|---|
| `Input\UNITS\{prop}` | property name (row label) | One property of the set; its unit cannot be written through the tree |
| `Input\SUBSTREAM` | `MIXED`, `ALL` | Substream the properties are computed for |
| `Input\PHASE\{row}` | `T`, `L`, `V`, `L1`, `L2`, `S` | Phase: total, liquid, vapor, first or second liquid, solid |
| `Input\COMPS\{row}` | component ID | Components a component property is given for |
| `Input\COMP_GROUPS\{row}` | ID | Component groups instead ([properties-comp-groups.md](properties-comp-groups.md)) |
| `Input\TEMP\{row}` | TEMPERATURE | Temperature to evaluate at |
| `Input\PRES\{row}` | PRESSURE | Pressure to evaluate at |
| `Input\SYSTEMP` | `YES`, `NO` | Also at the stream's own temperature |
| `Input\BASIS\{row}` | `WET`, `DRY` | With water, or water-free |

## Listing it with every stream

| Path | Type | Purpose |
|---|---|---|
| `\Data\Setup\ReportOptions\Stream-Report\Input\PROPERTIES\{row}` | ID | Prop-sets computed for every stream; insert a row first |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\STRM_UPP\{prop}\MIXED\{phase}` | real | One property in a stream; `{phase}` is `LIQUID` for `PHASE` `L` |
