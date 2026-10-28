# Compr performance curves

Paths are under `\Data\Blocks\{name}\`. With `OPT_SPEC=USE-CURVE` the curves (head, pressure or power against inlet flow, plus efficiency) set the outlet; with `CALC_SPEED=YES` they set the shaft speed instead.

1. Set `OPT_SPEC=USE-CURVE` and the Curve Setup fields; write `INDEP_VAR` before any flow unit (until then the unit fields refuse every unit).
2. Per point: `insert_row` on `Input\H_FLOW\{curve}`, then `set_value` the flow on the new row `#0`, `#1`, ...; the row is renamed to its point number (1, 2, ...) and the same row is in `HEAD_DATA\{curve}`, where the head goes. The efficiency table (`EF_FLOW`, `EFF_DATA`) works the same way.

Every table needs at least 4 points; with 3 the block stays incomplete.

Each `DEP_VAR` has its own table pair and units: `HEAD` `HEAD_DATA`/`H_FLOW` (`HEAD_UNITS`), `PRAT` `PRATIO_DATA`/`PR_FLOW`, `PRES` `PRES_DATA`/`P_FLOW` (`PRES_UNITS`), `DELP` `DELP_DATA`/`DP_FLOW` (`DELP_UNITS`), `POWER` `POWER_DATA`/`PW_FLOW` (`POWER_UNITS`), `HEAD-COEF` `HEADC_DATA`/`HC_FLOW`; the flow unit is the flow key plus `_UNIT` (`PR_FLOW_UNIT`, ...).

`MULTIP`: `NCURVES` of 2 or more creates the rows `SHAFT_SPEED\1`, `\2`, ... (one speed per curve, tables keyed by the same curve number); `ACT_SH_SPEED` is the speed the block runs at. `SINGLE-REFE` needs `REF_SH_SPEED` (the curve's speed) and `ACT_SH_SPEED`.

`HEAD-COEF` takes flow divided by speed (`INDEP_VAR1=VOL-FLOW/N`, units such as `cum/hr/rpm`, for the efficiency table too) and needs `IMPELLER_DIA` and `ACT_SH_SPEED`.

`OPT_CFORMAT=POLY`: per curve `HEAD_COEF1`..`HEAD_COEF4\{curve}` (a + bQ + cQ^2 + dQ^3) plus the surge and stonewall flows `HEAD_SURGE\{curve}`, `HEAD_SWALL\{curve}`; efficiency the same with `EFF_COEF1`..`4`, `EFF_SURGE`, `EFF_SWALL`.

Without an efficiency table the block takes `SEFF` / `PEFF` from Setup, or 0.72 when blank. `OPT_DEP2=POWER` gives a power table (`POWER_DATA`/`PW_FLOW`) instead of the efficiency.

`CALC_SPEED=YES` (Setup | Calculation Options) with an outlet spec and a `SINGLE-REFE` curve: the block finds the shaft speed that meets the spec (`Output\SH_SPEED`).

## Performance Curves | Curve Setup

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_CFORMAT` | `TABLE`, `POLY` | Curves as point tables or polynomials |
| `Input\DEP_VAR` | `HEAD`, `HEAD-COEF`, `POWER`, `PRES`, `PRAT`, `DELP` | What the curve gives against flow |
| `Input\INDEP_VAR` | `VOL-FLOW`, `MASS-FLOW` | Flow variable of the curves |
| `Input\OPT_CTYPE` | `SINGLE-OPER`, `SINGLE-REFE`, `MULTIP` | One curve at the running speed, one curve at a reference speed (scaled by fan laws), or several speeds |
| `Input\NCURVES` | int | Number of curves |
| `Input\OPT_DEP2` | `EFF`, `POWER` | Second curve: efficiency or power |
| `Input\CALC_SPEED` | `NO`, `YES` | Use the curves to find the shaft speed (Setup \| Calculation Options) |

## Performance Curves | Curve Data and Efficiencies

| Path | Type | Purpose |
|---|---|---|
| `Input\H_FLOW\{curve}\{pt}` | flow | Flow of a point (rows: see above) |
| `Input\HEAD_DATA\{curve}\{pt}` | head | Head of that point, in `HEAD_UNITS` |
| `Input\H_FLOW_UNIT` | flow unit (e.g. `cum/hr`, `kg/hr`) | Unit of the head-table flows |
| `Input\HEAD_UNITS` | `KJ/KG`, `J/KG`, `M-KGF/KG`, `FT-LBF/LB`, `METER`, ... | Unit of the head |
| `Input\SHAFT_SPEED\{curve}` | FREQUENCY | Speed of a curve (`MULTIP`) |
| `Input\EF_FLOW\{curve}\{pt}` | flow | Flow of an efficiency point |
| `Input\EFF_DATA\{curve}\{pt}` | fraction | Efficiency of that point (isentropic or polytropic, as `TYPE`) |
| `Input\EF_FLOW_UNIT` | flow unit | Unit of the efficiency-table flows |

## Performance Curves | Operating Specs

| Path | Type | Purpose |
|---|---|---|
| `Input\ACT_SH_SPEED` | FREQUENCY | Speed the block runs at |
| `Input\REF_SH_SPEED` | FREQUENCY | Speed of a `SINGLE-REFE` curve |
| `Input\IMPELLER_DIA` | LENGTH | Impeller diameter (`HEAD-COEF`) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\SH_SPEED` | FREQUENCY | Shaft speed |
| `Output\ABVSRG` | percent | Margin above surge |
| `Output\BELSWL` | percent | Margin below stonewall |
