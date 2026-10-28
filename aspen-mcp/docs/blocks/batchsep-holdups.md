# BatchSep holdups

Paths are under `\Data\Blocks\{name}\`. How stage holdups and pressure drops are found (Setup | Pressure, Holdups).

| Path | Type | Purpose |
|---|---|---|
| `Input\PRESHOLDUP` | `CALCULATED`, `FIXED`, `FLOOD-CALC` | Holdups and drops from the hydraulics, given by you, or given plus a flooding check on the internals |
| `Input\DIN` | LENGTH | Column inner diameter used by the hydraulics (`CALCULATED`) |

## Given holdups (`FIXED`)

| Path | Type | Purpose |
|---|---|---|
| `Input\MMLR` | MOLES | Holdup in the condenser and reflux |

1. `insert_row` on `Input\ENDSTAGE`; the same row of `LHLDP` holds the liquid holdup of the stages down to that stage.

| Path | Type | Purpose |
|---|---|---|
| `Input\ENDSTAGE\{row}` | int | Last stage of the range |
| `Input\LHLDP\{row}` | MOLES | Liquid holdup per stage in the range |
