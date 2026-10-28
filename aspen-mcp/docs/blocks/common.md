# Blocks: common rules and shared forms

Applies to every block type. Each block file lists only its own fields.

## Paths

A block is `\Data\Blocks\{name}`. Its inputs are under `Input\`, its results under `Output\`; block files write paths relative to that node.

A list field adds one segment per index (`Input\FEED_STAGE\{stream}`); a two-index field adds two (`Input\X_EST\{stage}\{comp}`).

Write with `set_value`. Give `unit=` to enter the number in that unit; the field then reports that unit.

A field that keeps its unit in another keyword (HeatX `VALUE` in `SPECUN`) gets the unit written there.

Writing an empty string clears a field back to its default.

An option field accepts only its listed codes; any other text is refused.

`unit=` takes Aspen's unit names for the field's category (`get_node_unit_info` lists them; a unit that does not fit is refused with the closest names). `um` is read as `micron`; speeds of category INVERSE-TIME take `1/min`, not `rpm`.

## Writes that are refused or ignored

`set_value` writes only a node that exists: a list row not inserted yet or a subobject not created gives `Node not found`. Create it first ([elements](../mcp/elements.md)).

A value never switches the code that picks the specs (`SPEC_OPT`, `OPT_SPEC`, `OPT_DESIGN`, ...): write the code yourself. Values it does not name are kept but not used by the run.

A write that clashes with the current settings is refused and the old value stays. The error states the rule or the range (`must be between 0 and 1`); read it before trying another path.

Some fields take a value only once the field they depend on is set: write that one first. A set `PHASE` refuses `NPHASE` 2 or 3 until `PHASE` is cleared with `""`; a curve's flow-unit field refuses every unit until `INDEP_VAR` is written.

A spec that another spec already fills (FSplit `FRAC` or `BASIS_FLOW` of one outlet, Sep `FRACS` or `FLOWS` of one component) is not enterable: clear the one there with `""`, then write the other.

## List rows

Stage-, stream- or component-labelled lists: `insert_row` on the list, then `set_label` with the label, then `set_value` on `<list>\<label>`.

Stage labels are refused until `NSTAGE` is set.

A refused label (a word or a number outside the stages on a stage list, a stream or component that is not there) leaves the inserted row without a label: `remove_row` it. Stream and component labels are upper case: `f2` and `benzene` are refused (`f2 is not a valid value`). A stage label `2.5` is kept as `2`.

Lists without labels: `insert_row`, then `set_value` on `<list>\#0`, `#1`, ...; `set_label` on them is refused.

Some lists keyed by a stream (`FEED_STAGE\{stream}`, FSplit `FRAC\{stream}`) get their row when the stream is connected, with no `insert_row`; others (Sep `TEMP\{stream}`) still need one. Look for the row before inserting.

Lists shown in one GUI table share their rows: a row inserted (and labelled) in one appears in the others. Insert it once, then write each list; inserting the same label again is refused.

A two-index list needs one `insert_row` + `set_label` per index (`dimension=0`, then `dimension=1`).

## Subobjects

`add_element` on `\Data\Blocks\{name}\Subobjects\<collection>` with a new ID creates one (a pumparound, a heating curve, ...). Its fields then appear in the block's own Input, keyed by that ID: `Input\<KW>\{id}`.

`Subobjects\<collection>\{id}\Input` shows the same Input as the block; write through the block's `Input\` path.

`remove_element` deletes a subobject; `remove_row` deletes a list row.

## Block Options | Properties

| Path | Type | Purpose |
|---|---|---|
| `Input\OPSETNAME` | method name | Property method for this block only (overrides the global one) |
| `Input\HENRY_COMPS` | ID | Henry-components list used by this block |
| `Input\CHEMISTRY` | ID | Chemistry object used by this block |
| `Input\FRWATEROPSET` | method name | Thermodynamics used for the water-only phase |
| `Input\SOLU_WATER` | `0`, `1`, `2`, `3`, `4`, `5` | How water dissolving in the organic liquid is computed |

## Block Options | Simulation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\FLASH_METHOD` | `INSIDE-OUT`, `GIBBS` | Flash algorithm of the block |
| `Input\ENERGY_BAL` | `YES`, `NO` | Solve the energy balance (NO: mass balance only) |
| `Input\RESTART` | `YES`, `NO` | Start from the previous run's results |

## Block Options | Diagnostics

| Path | Type | Purpose |
|---|---|---|
| `Input\TERM_LEVEL` | int 0-10 | Detail of messages on the control panel |
| `Input\SIM_LEVEL` | int 0-10 | Detail of simulation messages in the history |
| `Input\PROP_LEVEL` | int 0-10 | Detail of property messages in the history |
| `Input\STREAM_LEVEL` | int 0-10 | Detail of stream messages in the history |

## Block Options | Report

| Path | Type | Purpose |
|---|---|---|
| `Input\REPORT` | `REPORT`, `NOREPORT` | Include the block in the report |
| `Input\INPUT` | `INPUT`, `NOINPUT` | Print the block's input |
| `Input\RESULTS` | `RESULTS`, `NORESULTS` | Print the block's results |
| `Input\TOTBAL` | `TOTBAL`, `NOTOTBAL` | Report the overall balance (mass, energy) |
| `Input\COMPBAL` | `COMPBAL`, `NOCOMPBAL` | Print the component balance |

## Utility

| Path | Type | Purpose |
|---|---|---|
| `Input\UTILITY_ID` | ID | Utility (`\Data\Utilities\{id}`) that serves the block's duty; single-duty blocks |

Set the utility itself up as in [utilities](../utilities/utilities.md). After a run the block reports its share:

| Path | Type | Purpose |
|---|---|---|
| `Output\UTIL_COST` | COST-RATE | Cost of the utility this block uses |
| `Output\UTIL_DUTY` | ENTHALPY-FLO | Duty the utility serves in this block |
| `Output\UTL_USAGE` | MASS-FLOW | Utility flow this block takes |

## Running

`run_simulation` refuses a model in which a block is input-incomplete or has an open required port, and names the block; Aspen would solve none of the blocks.

IDs: at most 8 characters: letters, digits and `-` (Aspen also takes `+`, `#` and `$`) ([IDs](../setup/setup.md#ids)). `place_block` and `place_stream` refuse a longer ID or one with `_` and name one that fits. A stream that gets such an ID another way stops the run at a `_` (`run_simulation` refuses the model and names the stream), and with a longer ID gets no results.

Block and stream names are stored in upper case (`place_block` `b1` makes `B1`); a name already taken, in any case, is refused.

When a run returns no status, `run_simulation` quotes the errors of the engine history (`.his`), which name the cause, and lists the blocks left without results.

## Results

`Output\BLKSTAT` reads 0 after a run in which the block solved without error.
