# PetroFrac side heaters

Paths are under `\Data\Blocks\{name}\`. A fixed duty on a main-column stage.

1. `insert_row` on `Input\HEATER_DUTY` and `set_label` with the stage number, then set the duty.

| Path | Type | Purpose |
|---|---|---|
| `Input\HEATER_DUTY\{stage}` | ENTHALPY-FLO | Heat added on that stage (negative: removed) |

| Path | Type | Purpose |
|---|---|---|
| `Output\DUTY5\{stage}` | ENTHALPY-FLO | Heat added per stage, the condenser on stage 1 |
