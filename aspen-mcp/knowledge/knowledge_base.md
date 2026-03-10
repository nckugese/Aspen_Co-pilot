# Aspen Plus MCP Knowledge Base

Tips, gotchas, and patterns for building simulations via the Aspen Plus COM API through MCP.

---

## General Rules

- **Save before running** — Aspen Plus can crash with aggressive parameters. Always `save_simulation` before `run_simulation`.
- **Check inputs before running** — Always call `check_inputs` before `run_simulation` to catch missing or incomplete inputs.
- **Block/stream names** — Maximum **8 characters**, no leading underscores.
- **MHeatX cannot be placed via COM** — `Elements.Add()` fails; MHeatX requires GUI placement with stream count configuration.
- **Block type names** — Use SGXML captions (e.g. `Mixer`, `Flash2`, `RadFrac`) as COM block type identifiers.
- **MCP reconnect loses sessions** — Running `/mcp` creates a new AspenPlusManager; all tracked sessions are lost. You must reopen the simulation file.
- **Never guess basic operating conditions** — If temperature, pressure, flowrate, or composition data is missing from the source (e.g. patent, paper, user request), **always ask the user**. Do not assume or estimate these values. Other parameters (e.g. number of stages, efficiencies, convergence settings) are OK to use defaults or initial guesses.

---

## Block-Specific Knowledge

### Compr (Compressor)
- **Must set `OPT_SPEC` before setting outlet value** — e.g. set `OPT_SPEC` to `PRES` before setting the `PRES` value. Without `OPT_SPEC`, the block stays incomplete even if pressure is specified.
- **Efficiency depends on compressor type**:
  - **Isentropic type** → use `SEFF` (isentropic efficiency) or `MEFF` (mechanical efficiency).
  - **Positive Displacement type** → use `PEFF` (polytropic efficiency) or `MEFF` (mechanical efficiency).
  - Setting the wrong efficiency type for the selected model will leave the block incomplete.
- Required inputs: `OPT_SPEC`, outlet value (`PRES` or `TEMP`), and the appropriate efficiency for the type.
- Path example: `\Data\Blocks\{name}\Input\OPT_SPEC` → set to `PRES`, then `\Data\Blocks\{name}\Input\PRES` → set to target pressure.

### MCompr (Multi-stage Compressor)
- Same `OPT_SPEC` requirement as `Compr` — set specification type before the value.
- Additional inputs: number of stages (`NSTAGE`), intercooler specifications.

### RadFrac (Rigorous Distillation)
- **Operating specs limit** — RadFrac has only 2 operating specifications. You must clear one before setting another (e.g. clear `BASIS_BR` before setting `QN`).
- **Side duties (HEATER_DUTY)** — Stage-indexed entries must be created in the GUI first. COM cannot create new stage entries, only modify existing ones.
- **Feed convention** — `FEED_CONVEN` and `FEED_CONVE2` control `ABOVE-STAGE` vs `ON-STAGE` behavior.
- **Feed stage for bottom feed** — On an N-stage column with no reboiler, use stage `N+1` for the bottom feed.
- **Condenser/Reboiler types** — Set `CONDENSER` (e.g. `TOTAL`, `PARTIAL-V`) and `REBOILER` (e.g. `KETTLE`, `NONE`) early, as they affect stage numbering.

### Flash2 / Flash3
- Straightforward — specify 2 of: temperature, pressure, duty, vapor fraction.
- Flash3 produces three phases (vapor, liquid-1, liquid-2).

### Heater
- Simple heat exchanger — specify outlet temperature or duty, plus pressure (or pressure drop).

### HeatX (Two-stream Heat Exchanger)
- Requires both hot and cold side connections.
- Specify calculation mode: `DESIGN`, `RATING`, or `SIMULATION`.

### DSTWU (Shortcut Distillation)
- Quick column sizing — specify light key, heavy key, and recovery fractions.
- Good for initial estimates before switching to RadFrac.

### Valve
- Specify outlet pressure or pressure drop.
- Choose valve model: `ADIABATIC` (isenthalpic) or others.

### Pump
- Similar to Compr — specify outlet pressure or pressure increase, plus efficiency.

### FSplit (Stream Splitter)
- Specify split fractions for each outlet stream.
- Fractions must sum to 1.0 (or leave one unspecified as the balance).

### Mixer
- No required specifications beyond stream connections — just mixing.

---

## Stream Knowledge

- **FLOWBASE path** — Full path is `\Data\Streams\{name}\Input\FLOWBASE\MIXED` (not just `FLOWBASE`).
- **Changing FLOWBASE via COM** — Does NOT auto-switch `TOTFLOW` dimension (e.g. kmol/hr → kg/hr). The flow basis should be changed in the GUI for proper unit synchronization.
- **Component flows** — When specifying individual component flows, use `FLOW\MIXED\{component}` under the stream input.
- **Stream types** — Most streams are `MATERIAL`. Use `HEAT` for energy streams and `WORK` for work streams.

---

## Convergence & Simulation Tips

- **Feed temperature drastically affects convergence** — Especially in cryogenic systems (e.g. ethylene/ethane at -110°C). Wrong feed temperature causes the solver to converge to a poor local optimum. Always verify feed temperature matches process conditions.
- **Recycle loops** — Need tear streams for convergence. Aspen usually identifies them automatically, but you may need to provide good initial estimates.
- **Simulation sequence** — Aspen solves blocks in sequence. For recycles, it iterates until tear stream values converge.
- **Tear method selection** — Path: `\Data\Convergence\Conv-Options\Input\TEAR_METHOD`. Available methods:
  - `WEGSTEIN` — Default. Acceleration method, works well for most cases.
  - `DIRECT` — Direct substitution (no acceleration). Simplest but slowest.
  - `BROYDEN` — Quasi-Newton method using Broyden's update.
  - `NEWTON` — Full Newton's method. More robust for difficult convergence.
  - **When to switch**: If using Wegstein and the loop solver's Max Err/Tol oscillates (large positive/negative values that look like they trend toward zero but converge too slowly or stall), switch to `NEWTON` or `BROYDEN`.
- **Loop convergence diagnostics** — Check `ERR_TOL2` under each loop solver to see iteration history. Path: `\Data\Convergence\Convergence\{solver_name}\Output\ERR_TOL2`. Each child is an iteration (e.g. 7 children = 7 iterations). Values should trend toward zero; large oscillations (e.g. `621 → -117 → 106 → ... → -0.5`) indicate the solver is struggling but eventually converging. If values don't approach zero or the iteration count is very high, consider switching `TEAR_METHOD`.
- **Simulation-level run status** — `\Data\Results Summary\Run-Status\Output\PER_ERROR` contains the overall simulation messages (e.g. "The following Unit Operation blocks were completed with errors: STRIP"). This is the same text shown in the Aspen GUI Results Summary. Checked automatically by `run_simulation`.
- **Block error diagnostics** — After running, check each block's output:
  - `\Data\Blocks\{name}\Output\BLKSTAT` — 0 = OK, 1 = error
  - `\Data\Blocks\{name}\Output\BLKMSG` — short error summary
  - `\Data\Blocks\{name}\Output\PER_ERROR` — full detailed error (multi-line, indexed children)
  - These are checked automatically by `run_simulation` and reported in the output.
- **Solver failures** — If a block fails to converge:
  1. Check that all required inputs are specified (`check_inputs`).
  2. Verify feed conditions are reasonable.
  3. Try relaxing specifications (e.g. wider pressure range, higher tolerance).
  4. Try a different `TEAR_METHOD` if the loop oscillates without converging.
  5. Check block `PER_ERROR` for detailed error messages (e.g. "COLUMN DRIES UP" means wrong feed conditions or specs).

---

## Property Methods

- **Common methods**: `PENG-ROB` (hydrocarbons, gases), `NRTL` (polar/non-ideal liquids), `UNIQUAC` (liquid-liquid), `IDEAL` (ideal mixtures), `SRK` (gas processing).
- **Choose early** — Property method affects all thermodynamic calculations. Set it before adding blocks.
- **Binary interaction parameters** — Some methods (NRTL, UNIQUAC) require binary interaction parameters. Aspen auto-retrieves from databanks when available.

---

## COM API Patterns

- **Exploring the data tree** — Use `list_node_children` to navigate. Start from `\Data\Blocks`, `\Data\Streams`, `\Data\Properties`, etc.
- **Input vs Output** — Block inputs are under `\Data\Blocks\{name}\Input\...`, outputs under `\Data\Blocks\{name}\Output\...`.
- **Setting values with units** — Use the `unit` parameter in `set_block_value`, `set_stream_value`, or `set_node_value` to specify units (e.g. `unit="bar"`, `unit="C"`). The system handles conversion automatically.
- **Search before guessing** — Use `search_properties` to find the correct property name and path before attempting to set values.

---

## Workflow Best Practices

### Starting a New Project
- **Always use `create_new_simulation`** when starting from scratch. This copies the bundled `Blank_Simulation.bkp` to a new file named after the project (e.g. `create_new_simulation("ethylene_splitter", "D:/Projects")` → creates `D:/Projects/ethylene_splitter.bkp`).
- **Never modify the blank template directly** — it serves as the reusable starting point for all new simulations.
- If a simulation file already exists with that name, open it with `open_aspen_plus` instead.
- If no destination folder is given, the new file is created next to the blank template.

### Standard Workflow
1. **Create or open simulation** → `create_new_simulation` (new) or `open_aspen_plus` (existing)
2. **Set property method** → `set_property_method`
3. **Add components** → `add_component` (one at a time)
4. **Build flowsheet** → `place_block`, `place_stream`, `connect_stream`
5. **Configure blocks** → `set_block_value` or `set_node_value`
6. **Configure streams** → `set_stream_value` or `set_node_value`
7. **Check inputs** → `check_inputs`
8. **Save** → `save_simulation`
9. **Run** → `run_simulation`
10. **Read results** → `get_block_value`, `get_stream_value`, `get_node_value`
