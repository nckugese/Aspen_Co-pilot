# Tree elements: generic tools

Tools that list, create and remove nodes of the Aspen data tree when no dedicated tool covers the object. Paths, units and list rows of blocks: [blocks/common.md](../blocks/common.md).

## Create, then fill

`set_value` only changes a node that exists; on a missing one it returns `Node not found: <path>`. Create the node first, then write it:

| Missing | Create with | Then |
|---|---|---|
| an object in a folder (block, stream, reaction set, design spec, ...) | `add_element(folder, "NAME!TYPE")` | `set_value` on its `Input\...` |
| a block's subobject (pumparound, internals section, ...) | `add_element` on `\Data\Blocks\{name}\Subobjects\<collection>` with an ID | `set_value` on `Input\<KW>\{id}` |
| a row of a list | `insert_row(list)` | `set_label`, then `set_value` on `<list>\<label>`; or `set_value` on `<list>\#n` for a list without labels |

## Tools

| Tool | Does |
|---|---|
| `list_elements(path)` | Children of a node: index, name, value; on a leaf, its value |
| `list_node_children(path)` | Children with their values; a child holding a table shows its entry count |
| `add_element(path, name)` | Adds a child; `NAME!TYPE` sets its record type (`B1!Heater`, `R1!POWERLAW`) |
| `remove_element(path, name)` | Removes the child with that name |
| `insert_row(path, dimension=0)` | Adds a row at the end of `dimension`; returns its index |
| `set_label(path, index, label, dimension=0)` | Gives row `index` a label |
| `remove_row(path, index, dimension=0)` | Removes row `index` (0-based); an index past the end is refused |
| `get_node_attribute(path, attribute)` | Reads one attribute, by name or number (below) |
| `set_node_attribute(path, attribute, value)` | Writes one attribute without touching the value (e.g. `BASIS`) |

Under `\Data\Blocks` and `\Data\Streams` `add_element` upper-cases the name. A name already used in the folder, in any case, is refused: `remove_element` the old one first to replace it.

A block named like an existing Design-Spec, Calculator, Transfer or Measurement is refused.

`insert_row` takes the row count of that dimension as the new index. A two-index list needs one `insert_row` + `set_label` per dimension.

Attribute names: `VALUE` 0, `UNITROW` 2, `UNITCOL` 3, `OPTIONLIST` 5, `RECORDTYPE` 6, `ENTERABLE` 7, `UPPERLIMIT` 8, `LOWERLIMIT` 9, `VALUEDEFAULT` 10, `USERENTERED` 11, `COMPSTATUS` 12, `BASIS` 13, `INOUT` 14, `PROMPT` 19.

## Snapshot and diff

Learn a setup from a demonstration in the Aspen GUI (the observation-knowledge-extraction skill):

1. `snapshot_tree(session, root_path)`: returns an id (`<session>#<n>`) and the node count.
2. The user makes the change in the GUI.
3. `snapshot_tree` again on the same `root_path`.
4. `diff_snapshot(session, id_before, id_after)`.

| Parameter | Default | Purpose |
|---|---|---|
| `root_path` | | Subtree recorded, kept narrow (a block's `Input`) |
| `input_only` | `True` | Leave out every `Output` branch |
| `count_only` | `False` | Only count the nodes under `root_path` (a hint to narrow above 4000) |
| `label` | | A note kept with the snapshot |

Each node keeps its value, unit, record type, basis, user-entered flag, default, limits and option list. The diff lists changed nodes (each differing item `old -> new`), added nodes (value, record type, unit, basis) and removed nodes. Snapshots live in the server's memory; a restart drops them.

To reproduce a diff: a changed value is a `set_value` on the printed path (copy component-keyed paths as printed); an added row or object is created first (`insert_row`, `add_element`, or the object's own tool), then filled; a record type is given when the object is created (`NAME!TYPE`, or the tool's type argument). A change in `userentered` alone is bookkeeping, not a setting.

## Objects with their own recipes

Reaction sets, stoichiometry and kinetics: [reactions](../reactions/). Sensitivity: [analysis](../analysis/). Design specs and calculators: [flowsheeting](../flowsheeting/). A reactor's reaction-set list `RXN_ID`: the reactor's block file ([rcstr.md](../blocks/rcstr.md), [rplug.md](../blocks/rplug.md)).
