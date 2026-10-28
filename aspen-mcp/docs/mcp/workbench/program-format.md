# Program format

A block program is a JSON list of statements `{"do": <kind>, ...}`, the `program` / `insert` of `workbench_edit`. Every statement gets an `id` (`s` + 7 hex) when it has none or a duplicate; `workbench_read` shows them, and `after_id` / `remove_ids` take them. Paths are exact tree paths: look each one up in the docs, never guess. A value without `unit` is taken in the field's current unit.

```json
[
  {"do": "def", "name": "recovery", "params": ["pg", "made"], "expr": "pg / made * 100"},
  {"do": "set", "path": "\\Data\\Streams\\FEED\\Input\\PRES\\MIXED", "value": 25, "unit": "atm",
   "why": "Feed at the column's design pressure"},
  {"do": "seek", "path": "\\Data\\Blocks\\COL1\\Input\\BASIS_D", "lower": 496, "upper": 504,
   "measure": "purity", "target": 0.995, "as": "D",
   "body": [
     {"do": "run"},
     {"do": "read", "path": "\\Data\\Streams\\BOTM\\Output\\MOLEFRAC\\MIXED\\PROPYL1", "as": "purity"},
     {"do": "read", "path": "\\Data\\Streams\\BOTM\\Output\\MOLEFLOW\\MIXED\\PROPYL1", "as": "pg_bot"},
     {"do": "calc", "as": "rec", "expr": "recovery(pg_bot, 50)", "unit": "%"}]},
  {"do": "if", "left": {"expr": "rec - 99"}, "op": ">=", "right": 0,
   "then": [{"do": "log", "text": "D = {D}, recovery {rec} %"}],
   "else": [{"do": "optimize", "algorithm": "afmcbo", "eval_budget": 150,
             "variables": [{"path": "\\Data\\Blocks\\COL1\\Input\\BASIS_RR", "lower": 0.1, "upper": 2}],
             "objectives": [{"path": "\\Data\\Blocks\\COL1\\Output\\REB_DUTY", "direction": "minimize"}],
             "constraints": [{"path": "\\Data\\Streams\\BOTM\\Output\\MOLEFRAC\\MIXED\\PROPYL1", "lower": 0.99}]}]}
]
```

## Statements

| `do` | Fields (`?` optional, default in brackets) | Purpose |
|---|---|---|
| `set` | `path`, `value` or `expr`, `unit`?, `basis`? | Write an input. `expr` writes the expression's value; `basis` (`MOLE`, `MASS`, ...) sets a flow's basis with it, and `unit` must then be one of that basis. A value starting with `=` typed in the window is an expression |
| `run` | `reinit`? | Run the simulation; `reinit` first goes back to initial estimates. Sets `last_run_ok`: 1 after a run that ended ok or with warnings only, else 0 |
| `read` | `path`, `as` (`value`) | Store a value and its unit in a variable. In a check it reads the value as it stands |
| `calc` | `as` (`value`), `expr`, `unit`? | Compute a variable; `unit` is only a label for tables and charts |
| `def` | `name`, `params`, `expr` | A function usable in any expression, wherever the `def` sits; may call itself |
| `log` | `text` | A log line; `{name}` takes the variable's value (`?` and a warning when it has none) |
| `if` | `left` (`{"path"}`, `{"var"}` or `{"expr"}`), `op` (`>` `>=` `<` `<=` `==` `!=`), `right` (a number or an expression), `then`, `else` | Branch; a side with no value takes `else` |
| `repeat` | `times`, `body` | Loop; `i` counts from 1 |
| `until` | `cond`, `max`? (100), `body` | Loop while `cond` is false, tested before each pass; a condition with no value counts as false |
| `sweep` | `path`, `from`, `to`, `steps`, `unit`?, `as`? (`sweep_value`), `finish`?, `body` | Set `path` to `steps` evenly spaced values, both ends included, running `body` after each |
| `seek` | `path`, `lower`, `upper`, `measure`, `target`, `unit`?, `tol`?, `max`? (30), `as`? (`seek_value`), `finish`?, `body` | Design spec: the value of `path` in [lower, upper] that brings the expression `measure` to `target`, running `body` for each try (false position, Illinois; a failed run bisects). `tol` defaults to 1e-6 × max(1, abs(target)). Stops at once when the two bounds do not bracket the target, giving the measure at both |
| `optimize` | `algorithm` (`afmcbo`), `eval_budget`, `variables`, `objectives`, `constraints`, `options`?, `seed`?, `finish`? | Run the `optimize` tool ([optimize](../optimize/index.md)). Variable `{"path", "lower", "upper", "type"?: "int"}`; objective `{"path" or "expr", "direction"}` (`minimize` by default); constraint `{"path" or "expr", "lower" and/or "upper"}`. Results under `~/.aspen-mcp/workbench/runs/<tab id>/` |
| `table` | `title`, `rows`?, `row_label`?, `columns` | A results table: one row per name in `rows` (none: one row), the names in a first column headed `row_label`. Column `{"label"?, "path"}` (its unit comes with it; no label: the window names it by its field) or `{"label", "expr", "unit"?}`; `{row}` in a path or expression stands for the row's name. In a loop the last pass wins: for every pass use a loop table |
| `table` (loop) | `title`, `loop`, `vars`? | A loop's results as a table, after the loop: one row per pass, the loop variable then `vars` (none: every recorded variable). `loop` is the loop statement's `id` |
| `plot` | `title`, `x_from`?, `x_to`?, `y_from`?, `y_to`?, `xlabel`?, `ylabel`?, `var`? (`x`), `points`? (60, 2 to 400), `series` | A chart. Series `{"loop", "ycols", "xcol"?, "label"?, "color"?, "dash"?}` (a data line: a loop's results, one line per `ycols` name, x the loop variable unless `xcol`; place the plot after the loop), `{"label", "expr", "from"?, "to"?, "color"?, "dash"?}` (a curve, `expr` in `x`) or `{"label", "x"}` (a vertical line). Ranges are expressions; no x range: the data lines' extent (required without data lines); no y range fits the lines. `x` is the plot's own, a program variable of that name is left as it was |
| `save` | `path`? | Save the model to its own file, or as `path` (`.bkp`, `.apw`, `.apwz`; relative to the model's folder; `{name}` takes a variable). After a save as, the session works in the new file. Only `.bkp`, `.apw` and `.apwz` are accepted; a `path` that is an existing file outside the model's folder, and not the session's own model, is refused: the step fails, nothing is saved, and the message says to ask the user to save it from the workbench window instead |
| `proc` | `name`, `params`?, `body` | A procedure, top level only; runs only when called |
| `call` | `name`, `args`? | Run a procedure: each arg (an expression) sets the matching param first. Calls nest 20 deep |
| `pinch` | `dtmin`? (10), `auto`? (true), `exclude`?, `streams`?, `matches`? (true), `as`? (`pinch`), `title`? | Heat-integration targets of the model as it stands ([Pinch](#pinch)) |
| `place` | `block` + `type`, or `stream` + `type`? (`MATERIAL`, `HEAT`, `WORK`) | Place a block or a stream (names and types only; settings are `set` steps) |
| `connect` | `stream`, `block`, `port` | Connect a stream to a block's port |
| `remove` | `block`, or `stream`, or `stream` + `block` + `port` | Remove a block or a stream; with all three, only take the stream off that port |
| `component` | `add` or `remove` | Add or remove a component (removing drops its inputs in every stream) |
| `method` | `method` | Set the property method |
| `group` | `title`?, `why`?, `principle`? | A heading: the top-level steps after it, to the next heading or the end, are one group ([proposals.md](proposals.md#groups)). Top level only, no body, changes nothing. `title` one line, cut to 60 characters |
| `yourturn` | `path`, `hint`, `expect`? `{"op", "value"}`, `answer`?, `as`? (`yourturn_value`) | A manual step: the run waits for the user to set this input and press Done ([runs.md](runs.md#manual-steps)). `path` must be an input; `hint` one line, cut to 300 characters; `expect.op` as `if`'s, `>=` by default for a number or `{variable}`, `==` for text |

The five flowsheet statements (`place`, `connect`, `remove`, `component`, `method`) run the MCP tools' own code and are recorded as those tools; names, ports and the stream type are upper-cased. They and `yourturn` cannot sit in a loop or in a procedure called from one.

## Keys any statement may carry

| Key | Purpose |
|---|---|
| `id` | Statement id (added when missing) |
| `why` | One sentence on why the step is there: shown under the block, recorded as the reason of what the step changes. One line, cut to 300 characters |
| `off` | `true`: the step (and an `if`'s or loop's body with it) is left out of runs and checks. Only `true` is kept |
| `principle` | Up to 2 keys of the principle library (`docs/principles/<key>.md`; lower-case letters, digits, `_`) |
| `tech` | `true`: listed with a group's technical steps. `read`, `calc`, `def`, `log`, `table`, `plot`, `pinch` are technical without it |
| `record` | Loops only: the variables kept as table columns (`*` or none: all) |

Every loop (`repeat`, `until`, `sweep`, `seek`) leaves a table: one row per pass, the loop variable first, then the program variables with their units (or only `record`'s, plus `last_run_ok` and a design spec's measure).

## Variables

All variables share one namespace. Set by: `read` / `calc` (`as`), `sweep` and `seek` (`as`), `repeat` / `until` (`i`), `run` (`last_run_ok`), `call` (its params), `yourturn` (`as`), `pinch` (prefix `as`, below). A `seek` whose `measure` is an expression, not a variable name, also sets `measure`.

## Expressions

Python-like arithmetic over the variables, at most 500 characters, evaluated by a whitelist:

- `+ - * / // %`, power `^` or `**`, comparisons (chains allowed), `and or not`, `a if c else b`; numbers only
- functions `abs min max round sum mean sqrt exp ln log log10 log2 sin cos tan asin acos atan atan2 sinh cosh tanh floor ceil pow hypot sign clamp(x, lo, hi)`, constants `pi e inf`, and the program's `def`s

A missing input (a failed read or run), a division by zero or a math domain error gives "no value": the step logs why and loops go on, leaving a gap. `set` refuses to write "no value".

## Optimize goals as expressions

An objective or constraint may be `{"expr", "paths"?: {name: path}, "direction" | "lower" | "upper"}`. The optimizer runs its own simulations, so each name is replaced by a path before it starts: a name in `paths` stands for that path in this expression only; any other variable is traced back through the `read` and `calc` statements that run straight before the step, `def`s inlined. A variable set in a loop or `if` before the step, by `sweep` / `seek` / `call`, or only after the step is refused before anything runs. Functions allowed here: `abs min max sqrt exp log ln log10 sin cos tan pow floor ceil`.

```json
{"do": "read", "path": "\\Data\\Blocks\\HX1\\Output\\QCALC", "as": "q1"},
{"do": "read", "path": "\\Data\\Blocks\\COL\\Output\\REB_DUTY", "as": "q2"},
{"do": "calc", "as": "energy", "expr": "q1 + q2"},
{"do": "optimize", "algorithm": "nsga2", "eval_budget": 30,
 "variables": [{"path": "\\Data\\Blocks\\COL\\Input\\BASIS_RR", "lower": 1, "upper": 3}],
 "objectives": [{"expr": "energy", "direction": "minimize"}],
 "constraints": [{"expr": "q2 / q1", "upper": 3}]}
```

## Where a program leaves the model

| Step | `finish` (first = default) |
|---|---|
| `sweep` | `restore`, `last` |
| `seek` | `last`, `restore` |
| `optimize` | `restore`, `best`, `last` |

Later steps of the same program see what a sweep or optimize left (its last value or last evaluated point). When the program ends (done, stopped or failed), every input a `restore` step wrote goes back to its value before the first such step, and the model runs once more if it ran since. `last` keeps the last value; `best` writes the best feasible point and runs once. A later `set` of the same path, or the user's inspector edit while the run is paused, keeps that value. A step stopped or failed part-way is always put back.

`workbench_read` `model_state`: `kind` `restored`, `kept`, `mixed`, `partial` (a value could not be written back), `unknown` (session gone), with `restored`, `kept`, `failed` lists and `text`.

## Checks

A check (`workbench_run(dry_run=True)`) runs every step without changing the model: loops make one pass, `read` reads the current value, `run`, `save` and `optimize` only say what they would do. A real run starts with the same checks and stops before writing anything on an error. Each problem has a `level` (`error` stops a run, `warn`, `info`), a `code` and its words in both languages.

| Code | Level | Meaning |
|---|---|---|
| `not_found` | error | a written path, or a manual step's, does not exist (a result path exists only after a first run) |
| `not_enterable` | error | a written path is a result, not an input (the stream input meant is named); warn for a manual step's field, which a mode field may enable first |
| `bad_unit` | error | the unit is not one of the field's |
| `expr` | error | an expression does not parse or calls an unknown function |
| `call` | error | a call to a missing procedure, or with the wrong number of values |
| `name` | error | an `as` or `record` name is not a valid name |
| `save_ext` | error | a save path that is not `.bkp`, `.apw` or `.apwz` |
| `pinch` | error | a `streams` row without `name`, `t_in`, `t_out` or `duty` |
| `optimize` | error | an optimize goal with neither path nor expression, or one that cannot be traced |
| `table` | error | a table without columns, a column with neither path nor expression, or a loop table naming no loop of the program |
| `plot` | error | a chart without lines, a data line naming no loop of the program or no `ycols`, or no x range and no data line |
| `exists` | error | a block or stream of that name exists already |
| `bad_id` | error | a new block or stream ID over 8 characters or with a character other than letters, digits and `-` (Aspen refuses it, or cuts it and the stream gets no results); it names an ID that fits. A `workbench_edit` that writes such a place step is refused; a place step the program had already passes |
| `missing`, `gone` | error | the object does not exist, or an earlier step removed it |
| `type_unknown` | warn | a block type not in the port table: Aspen judges it when the step runs |
| `stream_type` | error | a stream type other than `MATERIAL`, `HEAT`, `WORK` |
| `port` | error | the block type has no such port (its ports are listed) |
| `occupied` | warn | the port holds another stream, which is taken off and left unconnected |
| `moves` | warn | the stream's end moves to this port from another |
| `loop` | error | the stream's other end is on the same block |
| `energy` | error | a heat or work stream on a material port, or the reverse |
| `same_port` | info | the stream is on that port already |
| `not_on_port` | error | a disconnect of a stream that is not on that port |
| `loose` | warn | removing the block leaves its streams unconnected at that end |
| `comp_exists` | error | the component is listed already (label, alias or databank name) |
| `comp_missing` | error | removing a component that is not listed |
| `comp_flows` | warn | removing a component drops its inputs in every stream |
| `label` | info | the component is listed under another label |
| `clash` | error | a block named like an existing Design-Spec, Calculator, Transfer or Measurement |
| `method` | warn | a property method the check does not know: Aspen judges it |
| `in_loop`, `in_loop_call` | error | a flowsheet step in a loop, or in a procedure called from one |
| `yt_in_loop`, `yt_in_loop_call` | error | a manual step in a loop, or in a procedure called from one |
| `group_nested` | warn | a group heading not at the top level: ignored |
| `group_title` | warn | a group heading without a title: named from its steps |
| `group_empty` | warn | a group heading with no step before the next heading or the end |
| `principle_unknown` | warn | a principle key not in the library: not shown |

The flowsheet steps and manual steps are checked against the flowsheet as the earlier steps leave it, so a `set` on a block an earlier step places is fine. In learning mode a check also warns of steps that change the model without a `why`.

## Pinch

`pinch` computes heat recovery targets from the values in Aspen when it runs, so it can follow a `run`, sit in a sweep or come after an optimization. With `auto` it collects:

| Block type | Stream name | Temperatures | Duty |
|---|---|---|---|
| Heater | the block's name | `\Data\Streams\{in}\Output\TEMP_OUT\MIXED` to the same of its outlet | `\Data\Blocks\{name}\Output\QCALC` |
| RadFrac condenser | `{name}-cond` | `\Data\Blocks\{name}\Output\B_TEMP\1`, isothermal | `Output\COND_DUTY` |
| RadFrac reboiler | `{name}-reb` | `Output\B_TEMP\{NSTAGE}`, isothermal | `Output\REB_DUTY` |

- A heater needs exactly one inlet and one outlet with a temperature, else it is left out (named in the log); zero duties are skipped; `exclude` lists blocks to leave out. HeatX blocks are not collected.
- `streams` adds rows `{"name", "t_in", "t_out", "duty", "type"?, "block"?, "part"?}`: each value a path (converted to C and kW) or an expression (taken as C and kW). Cooling down is hot, heating up cold; an isothermal row is hot when its duty is negative, unless `type` (`hot`, `cold`) says. `block` (and `part` `cond` / `reb`) places a row on the flowsheet's heat plans when its name is not a block's.
- ΔTmin is split equally between the two sides. Results: the targets, the stream table, the composite and grand composite curves, and with `matches` the minimum-match exchanger suggestions above and below the pinch.
- Variables (kW, C): `pinch_qh`, `pinch_qc`, `pinch_recovery`, `pinch_hot_now`, `pinch_cold_now`, `pinch_t_hot`, `pinch_t_cold`; `as` replaces the `pinch` prefix.
- A check only lists the streams found.

The pinch tools themselves: [pinch-analysis.md](../pinch-analysis.md).
