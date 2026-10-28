# Analyzer: property sets

Lists property sets whose values the block reports for the analysed copy. Paths are under `\Data\Blocks\{name}\`.

Each set may hold only one property. A set with two makes the input translator stop with a severe error, and the GUI run just returns no results.

1. Make a property set with one property: `add_element` on `\Data\Properties\Prop-Sets` with an ID, then a row in its `Input\UNITS` list labelled with the property name (e.g. `RHOMX`).
2. `insert_row` on `Input\PSETNAME`, then write the set ID to `PSETNAME\#0`; the next set goes in row `#1`.

| Path | Type | Purpose |
|---|---|---|
| `Input\PSETNAME\{row}` | property-set ID | The set reported in this row |
| `Input\PROP\{row}` | property name | Filled in from the set; no need to write it |
| `Input\PSUBSTRM\{row}` | `MIXED` | Substream (default MIXED) |
| `Input\UNITS\{row}` | unit string | Display unit for this row; the Output value keeps the run units |
| `Input\SCALE\{row}` | real | Scale factor for the shown value (default 1) |
| `Input\LOWER_BOUND\{row}` | real | Lower bound for the shown value |
| `Input\UPPER_BOUND\{row}` | real | Upper bound for the shown value |

A set already in the list is refused in a second row.

`UNITS` changes only the display: the value under `Output` stays in the run's unit set.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\ANALPROP\RHOMX\MIXED\TOTAL\WET\#0\1\PS-1` | property | Value of PS-1's RHOMX |

The path is `Output\ANALPROP\<property>\MIXED\<phase>\WET\<component>\1\<set ID>`; `TOTAL` and `#0` stand for the whole mixture.

A set with a phase and a per-component property gives one value per phase (`VAPOR`, `LIQUID`) and component.
