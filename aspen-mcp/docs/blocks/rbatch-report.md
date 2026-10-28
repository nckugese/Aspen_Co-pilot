# RBatch report

Paths are under `\Data\Blocks\{name}\`. Profiles in the report and property sets tabulated along them (Report form).

| Path | Type | Purpose |
|---|---|---|
| `Input\PROFILE` | `PROFILE`, `NOPROFILE` | Time profiles in the report |

Property sets: `insert_row` on the list, then write a property-set ID to `#0`, `#1`, ...

| Path | Type | Purpose |
|---|---|---|
| `Input\PR_PROP\{row}` | ID | Property sets on the reactor profile |
| `Input\PV_PROP\{row}` | ID | Property sets on the vent profile |
| `Input\PA_PROP\{row}` | ID | Property sets on the accumulator profile |
