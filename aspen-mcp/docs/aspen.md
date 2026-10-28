# Aspen Plus docs index

Start here, pick the one folder the task needs, and read only the section it calls for.

## How the files are written

- Each table row is one field: path, type or codes, purpose. Every row was checked live on Aspen Plus V15.
- Block files write paths relative to `\Data\Blocks\{name}`. Other object files say their root once near the top (`Root: \Data\Streams\{id}`); their rows (`Input\...`, `Output\...`) are relative to it. Join the two for a full path.
- `{...}` is a name or index you fill in; `#0`, `#1` is a list row.
- A file's last line, "Not covered", lists what was not checked. Do not guess those paths: use the observation-knowledge-extraction skill.
- Error messages, their causes and fixes are in [error-history.md](error-history.md), not in the object files.

## General rules

- Never guess the operating conditions (temperature, pressure, flow, composition). When the source does not give them, ask the user. Stage counts, efficiencies and convergence settings may start from defaults.
- IDs: at most 8 characters of letters, digits and `-` ([setup/setup.md](setup/setup.md#ids)).
- `place_block` takes the type names used in [blocks/index.md](blocks/index.md) (`Mixer`, `Flash2`, `RadFrac`).
- Writing, list rows, units and refused writes work the same for every block: [blocks/common.md](blocks/common.md). Creating rows and objects with the generic tools: [mcp/elements.md](mcp/elements.md).
- Run `check_inputs` before `run_simulation`; it names the missing field ([mcp/check-inputs.md](mcp/check-inputs.md)).
- Restarting the server (an `/mcp` reconnect) forgets every open session: open the file again.

## Standard workflow

1. Create or open: `create_new_simulation(project_name, destination_folder, mode)` or `open_aspen_plus(file_path, mode)`.
2. Components: `add_component`, then the method: `set_property_method` ([properties/](properties/properties.md)).
3. Flowsheet: `place_block`, `place_stream`, `connect_stream`; then `layout_flowsheet` once the topology is done.
4. Specs: `set_value` on block and stream paths ([blocks/](blocks/index.md), [streams/](streams/streams.md)).
5. `check_inputs`, then `run_simulation`; on errors follow the aspen-error-troubleshooting skill.
6. Results: `get_value` on `Output\` paths; then `save_simulation`.

Building or changing a whole process: follow the aspen-process-workflow skill (workbench or conversation, then phases).

## Folders

| Folder | What |
|---|---|
| [blocks/](blocks/index.md) | Every unit operation, one general file each plus advanced forms; shared rules in [common.md](blocks/common.md) |
| [setup/](setup/setup.md) | Global options: stream class, unit sets, IDs, simulation options, run mode and status, report, PSD mesh, stream prices |
| [utilities/](utilities/utilities.md) | Steam, water, electricity and other utilities; costs per block |
| [properties/](properties/properties.md) | Components, property method, Henry components, chemistry and electrolytes, property sets, component groups |
| [streams/](streams/streams.md) | Material streams; flash options, solids, heat and work streams, tear estimates |
| [reactions/](reactions/reactions.md) | Reaction sets: power law, equilibrium, LHHW, general, reactive distillation, polymer kinetics |
| [convergence/](convergence/convergence.md) | Default methods, tear streams, convergence blocks, sequences and order |
| [flowsheeting/](flowsheeting/flowsheeting.md) | Design specs, calculators, transfers, balances; the shared define and vary rows |
| analysis/ | [Sensitivity](analysis/sensitivity.md), Aspen's own [optimization and constraints](analysis/optimization.md), [data fit](analysis/data-fit.md) and its [regression](analysis/data-fit-regression.md) |
| mcp/ | The server's own tools: [optimize](mcp/optimize/index.md) (external optimizers), [Aspen Workbench](mcp/workbench/index.md), [generic element tools](mcp/elements.md), [check_inputs](mcp/check-inputs.md), [pinch analysis](mcp/pinch-analysis.md) |
| [principles/](principles/index.md) | Principle cards a workbench group or step can carry in learning mode |
| [learned/](learned/index.md) | Inbox of features learned by demonstration, until they move into their folder |
| [error-history.md](error-history.md) | Known error messages with cause and fix (read by `run_simulation`'s diagnosis) |
