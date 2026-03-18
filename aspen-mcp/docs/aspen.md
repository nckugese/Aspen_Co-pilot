# Aspen Plus Operations Index

When you need to configure a specific Aspen Plus object, read the corresponding doc file below.

## General Rules

- **Save before running** — Aspen Plus can crash with aggressive parameters. Always `save_simulation` before `run_simulation`.
- **Check inputs before running** — Always call `check_inputs` before `run_simulation` to catch missing or incomplete inputs.
- **Block/stream names** — Maximum **8 characters**, no leading underscores.
- **Block type names** — Use SGXML captions (e.g. `Mixer`, `Flash2`, `RadFrac`) as COM block type identifiers.
- **MHeatX cannot be placed via COM** — `Elements.Add()` fails; MHeatX requires GUI placement with stream count configuration.
- **MCP reconnect loses sessions** — Running `/mcp` creates a new AspenPlusManager; all tracked sessions are lost. You must reopen the simulation file.
- **Never guess basic operating conditions** — If temperature, pressure, flowrate, or composition data is missing from the source (e.g. patent, paper, user request), **always ask the user**. Do not assume or estimate these values. Other parameters (e.g. number of stages, efficiencies, convergence settings) are OK to use defaults or initial guesses.

## Standard Workflow

1. **Create or open simulation** → `create_new_simulation(project_name, folder)` (new) or `open_aspen_plus(file_path)` (existing)
2. **Add components** → `add_component(session, 'ETHANOL')` (one at a time)
3. **Set property method** → `set_property_method(session, 'PENG-ROB')`
4. **Build flowsheet** → `place_block`, `place_stream`, `connect_stream`
5. **Configure blocks** → `set_value` with block paths or property lookup
6. **Configure streams** → `set_value` with stream paths or property lookup
7. **Check inputs** → `check_inputs(session)`
8. **Save** → `save_simulation(session)`
9. **Run** → `run_simulation(session)`
10. **Read results** → `get_value` with output paths

## Blocks (Unit Operations)

See [blocks/index.md](blocks/index.md) for all block types and their documentation.

## Streams

See [streams.md](streams.md) for stream configuration (MATERIAL, HEAT, WORK).

## Reactions

See [reactions.md](reactions.md) for reaction sets, stoichiometry, and kinetics.

## Generic Elements Tools

See [elements.md](elements.md) for low-level COM element manipulation (list_elements, add_element, insert_row, etc.).

## Properties

See [properties.md](properties.md) for property methods, components, and databank operations.

## Model Analysis Tools

See [sensitivity.md](sensitivity.md) for sensitivity analysis setup (vary, define, tabulate).

## Convergence

See [convergence.md](convergence.md) for simulation convergence, tear methods, and diagnostics.
