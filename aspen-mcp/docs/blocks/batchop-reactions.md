# BatchOp reactions

Paths are under `\Data\Blocks\{name}\`. Kinetic reactions in the pot (Kinetics form; `REACSYS` `YES` on Setup | Specifications).

1. Set `REACSYS` to `YES`.
2. `insert_row` on `Input\RXN_ID`, then write a reaction-set ID to `RXN_ID\#0` (one row per set).

| Path | Type | Purpose |
|---|---|---|
| `Input\RXN_ID\{row}` | ID | Kinetic reaction set (for example a POWERLAW set) |
| `Input\CATWT` | MASS | Catalyst mass (Setup \| Specifications) |
| `Input\AGITATOR` | `NO`, `YES` | Agitator data for the kinetics |
| `Input\IMPELLER_RAT` | FREQUENCY | Impeller speed |
| `Input\IMPELLER_DIA` | LENGTH | Impeller diameter |
| `Input\IMPELLER_POW` | POWER | Impeller power |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\MO_FRAC_REAC\{pt}\{comp}` | fraction | Profile: pot mole fraction; ethyl acetate rose from 0 in the rxn run |
