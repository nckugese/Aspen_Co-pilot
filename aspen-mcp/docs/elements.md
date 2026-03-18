# Generic Elements Tools

Low-level COM element manipulation tools for any operation not covered by high-level tools.

## Available Tools

| Tool | COM Operation | Description |
|------|--------------|-------------|
| `list_elements(path)` | `Count + Item(i)` | List all elements: index, name, value |
| `add_element(path, name)` | `Elements.Add(name)` | Add element. Use `NAME!TYPE` for typed elements |
| `remove_element(path, name)` | `Elements.Remove(name)` | Remove element by name |
| `insert_row(path, dim)` | `InsertRow` | Insert table row (returns index) |
| `set_label(path, index, label, dim)` | `SetLabel` | Set label on a table row |
| `remove_row(path, index, dim)` | `RemoveRow` | Remove table row by index |

## When to Use Which

| Situation | Tool |
|-----------|------|
| Don't know what's inside a node | `list_elements` |
| Add a block/stream/reaction set | `add_element` with `NAME!TYPE` |
| Remove a block/stream | `remove_element` |
| Add to a table | `insert_row`, then `set_label` if the dimension supports labels |
| Remove from a table by index | `remove_row` |
| Node has a pre-existing empty element | `list_elements` → `set_value` on the element |

## Common Patterns

### Pattern 1: Select a reaction set for RCSTR/RPlug
```
list_elements(session, '\Data\Blocks\R1\Input\RXN_ID')
→ [0] #0 = None

set_value(session, aspen_path='\Data\Blocks\R1\Input\RXN_ID\#0', value='RXN1')
```

### Pattern 2: Add typed elements
```
add_element(session, '\Data\Blocks', 'PUMP1!Pump')
add_element(session, '\Data\Streams', 'S1!MATERIAL')
add_element(session, '\Data\Reactions\Reactions', 'RXN1!POWERLAW')
```

### Pattern 3: Explore → Understand → Act
When encountering an unknown node:
1. `list_node_children(path)` — see all child names and values
2. `list_elements(path)` — see element collection structure
3. Decide: `set_value`, `add_element`, or `insert_row` based on structure

### Pattern 4: Insert row then label
```
insert_row(session, '\Data\Blocks\R1\Input\RXN_ID')
→ Inserted row at ... index=0.

set_label(session, '\Data\Blocks\R1\Input\RXN_ID', 0, 'CRACKING')
→ Set label 'CRACKING' at ... index=0.
```
Some dimensions don't support labels (e.g. Sensitivity VARY tables) — just skip `set_label` for those.

### Pattern 5: Connect stream to block port
```
# Port connection uses chained Elements access internally
connect_stream(session, block_name='B1', stream_name='S1', port_name='F(IN)', block_type='Heater')
```
