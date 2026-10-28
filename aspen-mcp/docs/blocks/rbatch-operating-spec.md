# RBatch operating specification

Paths are under `\Data\Blocks\{name}\`. The `TYPE` modes besides `T-SPEC` (Setup | Specifications), and the temperature controller. Clear `TEMP` (write `""`) when leaving `T-SPEC`.

Profiles are paired unlabelled lists (`#0`, `#1`, ...): one `insert_row` on the time list per point adds the same row to its partner list; one row number is one point.

## Temperature profile (`T-PROFILE`)

| Path | Type | Purpose |
|---|---|---|
| `Input\PROF_TIME\{row}` | TIME | Time of the point |
| `Input\PROF_TEMP\{row}` | TEMPERATURE | Reactor temperature at that time; linear in between |

## Coolant at a fixed temperature (`TCOOL-SPEC`)

| Path | Type | Purpose |
|---|---|---|
| `Input\COO_TEMP` | TEMPERATURE | Coolant temperature |
| `Input\COO_U` | HEAT-TRANS-C | Heat-transfer coefficient |
| `Input\COO_AREA` | AREA | Heat-transfer area |

## Duty (`DUTY-SPEC`, `DUTY-PROF`)

| Path | Type | Purpose |
|---|---|---|
| `Input\DUTY` | ENTHALPY-FLO | Constant duty; 0 is adiabatic |
| `Input\DPROF_TIME\{row}` | TIME | Time of the point |
| `Input\DPROF_DUTY\{row}` | ENTHALPY-FLO | Duty at that time |

## Temperature controller (Controllers sheet; `T-SPEC`, `T-PROFILE`)

| Path | Type | Purpose |
|---|---|---|
| `Input\GAIN` | real | Proportional gain |
| `Input\INT_TIME` | real | Integral time, s |
| `Input\DER_TIME` | real | Derivative time, s |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\DUTY_INST\{pt}` | ENTHALPY-FLO | Profile: duty at each point |
| `Output\TMAX` | TEMPERATURE | Highest temperature: the adiabatic rise with `DUTY` 0 |
