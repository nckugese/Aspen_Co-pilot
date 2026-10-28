# BatchSep initial and final conditions

Paths are under `\Data\Blocks\{name}\`. The state at time zero (Initial Conditions) and where holdups go at the end (Final Conditions).

## Main

`TOTAL` starts the column at total reflux with the charge in it.

`CHARGE` and `EMPTY` fill the column with an inert gas named in `INERT`; it must be a component, and the condenser must be `PARTIAL` (with `TOTAL` the inert has nowhere to go and the run fails).

With `EMPTY` the charge comes in during a step: a changed variable `STREAM` / `MOLE-FLOW` on the charge stream ([batchsep-operating-steps.md](batchsep-operating-steps.md)).

| Path | Type | Purpose |
|---|---|---|
| `Input\INERT` | component | Inert gas filling the column (`CHARGE`, `EMPTY`) |
| `Input\PINITIAL` | PRESSURE | Initial pressure |
| `Input\TINITIAL` | TEMPERATURE | Temperature of the inert gas at time zero |
| `Input\DRUMVOLFRAC` | fraction | Initial liquid fill of the reflux drum |

## Final Conditions

| Path | Type | Purpose |
|---|---|---|
| `Input\POTFINALCOND` | `PLACE`, `RECEIVER`, `RECYCLE` | Pot contents at the end: left in place, emptied into a receiver, or kept for the next batch |
| `Input\POTFINALREC` | receiver number | Receiver for `RECEIVER` |

With `RECEIVER` the pot contents end up in the distillate stream.

| Path | Type | Purpose |
|---|---|---|
| `Input\INTERNFINCON` | `PLACE`, `RECEIVER`, `RECYCLE` | Same for the column holdup |
| `Input\INTERNFINREC` | receiver number | Its receiver |
| `Input\DRUMFINALCON` | `PLACE`, `RECEIVER`, `RECYCLE` | Where the reflux-drum holdup goes |
