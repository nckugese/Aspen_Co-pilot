# MCompr performance curves

Paths are under `\Data\Blocks\{name}\`. With `OPT_SPEC=NCURVES` each stage follows a performance map (head, or another quantity, plus efficiency against inlet flow) instead of a pressure spec. `{map}` is a map number, `{curve}` a curve in it, `{pt}` a point. Coolers are set as in [mcompr.md](mcompr.md).

1. Set `OPT_SPEC=NCURVES`, `NMAP`, `OPT_CTYPE`, `NCURVES`, `INDEPVAR` and the unit fields; create the stage rows as in [mcompr.md](mcompr.md).
2. Per map and curve: `insert_row` on `Input\H_FLOW` with label `{map}`, then on `Input\H_FLOW\{map}` with label `{curve}`. The same rows appear in `HEAD_DATA`.
3. Per point: `insert_row` on `Input\H_FLOW\{map}\{curve}`, `set_value` the flow on the new row `#0`, `#1`, ... (it becomes point 1, 2, ...), then the head on `HEAD_DATA\{map}\{curve}\{pt}`. The efficiency table (`EF_FLOW`, `EFF_DATA`) is built the same way.
4. Point each stage at its map: `insert_row` on `Input\S_MAPNO` with label `{stage}`, then `set_value` the map number. Without it the block stays incomplete.

Without an efficiency table a stage takes `SEFF` / `PEFF` from Setup, or 0.72 when blank.

`DEP_VAR` picks the table pair: `HEAD` `H_FLOW`/`HEAD_DATA` (`HEAD_UNITS`), `HEAD-COEF` `HC_FLOW`/`HEADC_DATA`, `POWER` `PW_FLOW`/`POWER_DATA` (`POWER_UNITS`), `PRES` `P_FLOW`/`PRES_DATA` (`PRES_UNITS`), `PRAT` `PR_FLOW`/`PRATIO_DATA`, `DELP` `DP_FLOW`/`DELP_DATA` (`DELP_UNITS`); each flow key plus `_UNIT` is its unit field.

`SINGLE-REFE`: the curves hold at `REF_SH_SPEED\{stage}` and the stage runs at `ACT_SH_SPEED\{stage}` (fan laws). `MULTIP`: one speed per curve in `SHAFT_SPEED\{map}\{curve}` (rows created like the tables) and `ACT_SH_SPEED\{stage}`.

`OPT_CFORMAT=POLY`: per map and curve `HEAD_COEF1`..`HEAD_COEF4\{map}\{curve}` (a + bQ + cQ^2 + dQ^3) with the surge and stonewall flows `HEAD_SURGE`, `HEAD_SWALL`; the efficiency uses `EFF_COEF1`..`4`, `EFF_SURGE`, `EFF_SWALL`. Rows are created like the tables (map, then curve).

## Performance Curves | Setup

| Path | Type | Purpose |
|---|---|---|
| `Input\NMAP` | int | Number of maps |
| `Input\OPT_CTYPE` | `SINGLE-OPER`, `SINGLE-REFE`, `MULTIP` | One curve at the running speed, one curve at a reference speed, or several curves at different speeds |
| `Input\NCURVES` | int | Curves per map |
| `Input\OPT_CFORMAT` | `TABLE`, `POLY` | Curves as point tables or polynomials |
| `Input\DEP_VAR` | `HEAD`, `HEAD-COEF`, `POWER`, `PRES`, `PRAT`, `DELP` | What the curves give against flow |
| `Input\INDEPVAR` | `VOL-FLOW`, `MASS-FLOW` | Flow variable of the curves |

## Performance Curves | Curve Data and Efficiencies

| Path | Type | Purpose |
|---|---|---|
| `Input\H_FLOW_UNIT` | flow unit (e.g. `cum/hr`) | Unit of the head-table flows |
| `Input\HEAD_UNITS` | `KJ/KG`, `J/KG`, `M-KGF/KG`, `FT-LBF/LB`, `METER`, ... | Unit of the heads |
| `Input\H_FLOW\{map}\{curve}\{pt}` | flow | Flow of a point |
| `Input\HEAD_DATA\{map}\{curve}\{pt}` | head | Head of that point |
| `Input\EF_FLOW_UNIT` | flow unit | Unit of the efficiency-table flows |
| `Input\EF_FLOW\{map}\{curve}\{pt}` | flow | Flow of an efficiency point |
| `Input\EFF_DATA\{map}\{curve}\{pt}` | fraction | Efficiency of that point (isentropic or polytropic, as `TYPE`) |
| `Input\SHAFT_SPEED\{map}\{curve}` | FREQUENCY | Speed of a curve (`MULTIP`) |

## Performance Curves | Stage Specs

| Path | Type | Purpose |
|---|---|---|
| `Input\S_MAPNO\{stage}` | int | Map the stage uses |
| `Input\ACT_SH_SPEED\{stage}` | FREQUENCY | Speed the stage runs at (`SINGLE-REFE`, `MULTIP`) |
| `Input\REF_SH_SPEED\{stage}` | FREQUENCY | Speed the curves were measured at (`SINGLE-REFE`) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_PRES\{stage}` | PRESSURE | Discharge pressure each stage reached |
| `Output\HEAD_CAL\{stage}` | HEAD | Head from the map |
| `Output\EFFICIENCY\{stage}` | fraction | Efficiency from the map |
| `Output\ABVSRG\{stage}` | percent | Distance above surge |
| `Output\BELSWL\{stage}` | percent | Distance below stonewall |
| `Output\SH_SPEED\{stage}` | FREQUENCY | Shaft speed |
