# BatchSep controllers

Paths are under `\Data\Blocks\{name}\`; `{ctl}` is the controller ID (Controllers form).

1. `add_element` on `Subobjects\Controllers` with an ID, e.g. `TC1`; its fields are keyed by that ID.
2. Set the measured variable (`PVTYPE`), the moved variable (`OPLOC`, `OPTYPE`), the set point, its range and the tuning.

The controller acts from the start of the batch, with no step change: holding stage 2 at 85 C by the reflux ratio gave more, less pure distillate than the same batch at a fixed reflux ratio of 3.

## Connections

| Path | Type | Purpose |
|---|---|---|
| `Input\PVTYPE\{ctl}` | `STAGE-TEMP`, `POT-TEMP`, `COND-TEMP`, `C-L-MOLEFLOW` | Measured variable |
| `Input\PVSTAGE\{ctl}` | int | Its stage (`STAGE-TEMP`) |
| `Input\OPLOC\{ctl}` | `SPLITTER`, `JACKET`, `CONDENSER` | Where the output acts |
| `Input\OPTYPE\{ctl}` | code | What it moves, e.g. `RFXRATIO` |

## Parameters

| Path | Type | Purpose |
|---|---|---|
| `Input\CONT_SPTEMP\{ctl}` | real | Set point of a temperature, in the global temperature unit |
| `Input\GAIN\{ctl}` | real | Proportional gain |
| `Input\INTEGRALTIME\{ctl}` | TIME | Integral time |
| `Input\DERIVTIME\{ctl}` | TIME | Derivative time |
| `Input\ACTION\{ctl}` | `DIRECT`, `REVERSE` | Output rises with the measurement, or falls |
| `Input\PVMINTEMP\{ctl}` | real | Measured range, low (temperature) |
| `Input\PVMAXTEMP\{ctl}` | real | Measured range, high (temperature) |
| `Input\OPMIN\{ctl}` | real | Output range, low |
| `Input\OPMAX\{ctl}` | real | Output range, high |
