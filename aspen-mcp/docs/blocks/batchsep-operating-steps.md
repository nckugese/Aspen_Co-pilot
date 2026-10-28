# BatchSep operating steps

Paths are under `\Data\Blocks\{name}\`; `{step}` is the step name, `{row}` a row `#0`, `#1`, ... (Operating Steps form).

1. `add_element` on `Subobjects\Operating Steps` with a name, once per step.
2. Changed variables: `insert_row` on `Input\TRIGGERLOC\{step}`, set the location, then `LOCPARAM`, then the value field for that parameter (same row).
3. A trigger end: set `OPS_ENDCOND\{step}` to `TRIGGER`, `insert_row` on `Input\SC_LOC\{step}`, set `OP_ACTIVE2` `YES`, then location, `TRIGGER`, `TRIG_COND` and the value.

## Changed variables

| Path | Type | Purpose |
|---|---|---|
| `Input\TRIGGERLOC\{step}\{row}` | `SPLITTER`, `JKHEATING`, `STREAM`, `LD-RECEIVER`, `CLHEATING`, `XHHEATING`, `CONDENSER`, `POT` | Where the change applies |
| `Input\LOCPARAM\{step}\{row}` | code | What changes, e.g. `RR` (`SPLITTER`), `DUTY` / `MED-TEMP` (`JKHEATING`), `MOLE-FLOW` (`STREAM`) |
| `Input\OPS_VALUE\{step}\{row}` | real | New value of a ratio such as `RR` |
| `Input\OPS_DUTYVAL\{step}\{row}` | ENTHALPY-FLO | New duty |
| `Input\OPS_TEMPVAL\{step}\{row}` | TEMPERATURE | New temperature (`MED-TEMP`) |
| `Input\OPS_MSFLVAL\{step}\{row}` | MASS-FLOW | New mass flow (`MED-MASSFLOW`) |
| `Input\OPS_STRM\{step}\{row}` | stream | Stream for `STREAM` |
| `Input\OPS_MLFLVAL\{step}\{row}` | MOLE-FLOW | Its new mole flow (`MOLE-FLOW`) |
| `Input\NVRECV\{step}\{row}` | receiver number | Receiver the distillate goes to (`LD-RECEIVER`) |
| `Input\NDISTRECV` | int | Number of distillate receivers |

A feed on `In_F(IN)` enters at `FEED_STAGE` only while a step gives it a flow (`STREAM` / `MOLE-FLOW`).

## End of a step

| Path | Type | Purpose |
|---|---|---|
| `Input\OPS_ENDCOND\{step}` | `ELAPSED`, `TRIGGER` | End after `OPS_DURATION`, or when a trigger fires |
| `Input\MAXDURATION\{step}` | TIME | Longest a triggered step may run |
| `Input\SC_LOC\{step}\{row}` | `POT`, `CONDENSER`, `STAGE`, `DRUM` | Where the trigger looks |
| `Input\TRIGGER\{step}\{row}` | `TEMPERATURE`, `PRESSURE`, `L-MOLEFRAC`, `L-MASSFRAC`, `L-MOLEHLDUP` | Variable watched |
| `Input\TRIG_COMP\{step}\{row}` | component | Component for a fraction |
| `Input\TRIG_COND\{step}\{row}` | `BELOW`, `ABOVE` | Comparison of the variable with the value |
| `Input\TRIG_MOLEFR\{step}\{row}` | fraction | Value for `L-MOLEFRAC` |
| `Input\TRIG_TEMP\{step}\{row}` | TEMPERATURE | Value for `TEMPERATURE` |

A triggered step ends when its trigger fires: with a pot benzene-fraction trigger the step stopped well inside its 5 hr limit and collected less distillate than a 1-hour step.

## Multiple batches (Operating Steps | Multiple Batches)

| Path | Type | Purpose |
|---|---|---|
| `Input\BATCHESNO` | real | Batches run in a row |
| `Input\ENDCONDITION` | `FIXED`, `MASS-CHANGE`, `MOLE-CHANGE` | Stop after `BATCHESNO`, or when holdups stop changing |
| `Input\MAXBATCHES` | real | Most batches with a change criterion |
