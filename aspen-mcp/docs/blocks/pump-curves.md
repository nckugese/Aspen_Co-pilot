# Pump performance curves

Paths are under `\Data\Blocks\{name}\`. With `OPT_SPEC=USE-CURVE` the block reads its head (or another variable) and its efficiency off curves against the inlet flow; `{k}` is the curve number (1 for one curve).

1. Write `OPT_SPEC=USE-CURVE`, then `OPT_CTYPE`: that creates curve 1 (`NCURVES` becomes 1).
2. Write `DEP_VAR` and `INDEP_VAR` (`INDEP_VAR1` for `HEAD-COEF`); the flow-unit fields accept a unit only after `INDEP_VAR` is set.
3. Set the units, e.g. `H_FLOW_UNIT` and `HEAD_UNITS`.
4. For point i (from 0): `insert_row` on `Input\H_FLOW\{k}`, write the flow to its row `#i`, then the head to `Input\HEAD_DATA\{k}\<i+1>`. The efficiency table `EF_FLOW` / `EFF_DATA` works the same way.

Tables by `DEP_VAR`: `HEAD` `H_FLOW`/`HEAD_DATA`; `POWER` `PW_FLOW`/`POWER_DATA`; `PRES` `P_FLOW`/`PRES_DATA`; `PRAT` `PR_FLOW`/`PRATIO_DATA`; `DELP` `DP_FLOW`/`DELP_DATA`; `HEAD-COEF` `HC_FLOW`/`HEADC_DATA`. Each x column has its unit field (`PW_FLOW_UNIT`, `P_FLOW_UNIT`, ...) and the y units are `POWER_UNITS`, `PRES_UNITS`, `DELP_UNITS`.

`OPT_CFORMAT=POLY` replaces the tables by y = c1 + c2 Q + c3 Q^2 + c4 Q^3 with Q in the flow unit: `HEAD_COEF1`..`HEAD_COEF4` (`\{k}`), `EFF_COEF1`..`EFF_COEF4`, and `POWER_COEF*`, `PRES_COEF*`, `PRATIO_COEF*`, `DELP_COEF*`, `HEADC_COEF*` for the other variables.

Without an efficiency curve the block takes `EFF` from Setup, or estimates one when that is blank.

`HEAD-COEF` curves need `IMPELLER_DIA` and `ACT_SH_SPEED` ([pump-speed.md](pump-speed.md)).

## Performance Curves | Curve Setup

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_CFORMAT` | `TABLE`, `POLY` | Curves as tables or polynomials |
| `Input\OPT_CTYPE` | `SINGLE-OPER`, `SINGLE-REFE`, `MULTIP` | One curve at the operating speed, one at a reference speed, or one per speed ([pump-speed.md](pump-speed.md)) |
| `Input\NCURVES` | int | Number of curves (`MULTIP`) |
| `Input\DEP_VAR` | `HEAD`, `HEAD-COEF`, `POWER`, `PRES`, `PRAT`, `DELP` | Variable the curve gives |
| `Input\INDEP_VAR` | `VOL-FLOW`, `MASS-FLOW` | Flow the curve is read against |
| `Input\INDEP_VAR1` | `FLOW-COEF`, `VOL-FLOW/N` | Flow for `HEAD-COEF`: flow coefficient, or flow over speed |
| `Input\SPLINE_FIT` | `HERMITE`, `LINEAR`, `HARWELL` | Interpolation between table points (default `HERMITE`) |

## Performance Curves | Curve Data

| Path | Type | Purpose |
|---|---|---|
| `Input\H_FLOW_UNIT` | flow unit (e.g. `cum/hr`, `kg/hr`) | Unit of the head-curve flow |
| `Input\HEAD_UNITS` | `METER`, `FT`, `J/KG`, `KJ/KG`, ... | Unit of the head |
| `Input\H_FLOW\{k}\#i` | real | Flow of each point |
| `Input\HEAD_DATA\{k}\<i+1>` | real | Head of each point |
| `Input\HEAD_COEF1\{k}` | real | c1 of the head polynomial (`HEAD_COEF2`..`4` alike) |
| `Input\HC_FLOW_UNIT` | flow per speed unit (e.g. `cum/hr/rpm`) | Unit of the x column for `VOL-FLOW/N` |

## Performance Curves | Efficiencies

| Path | Type | Purpose |
|---|---|---|
| `Input\EF_FLOW_UNIT` | flow unit | Unit of the efficiency-curve flow |
| `Input\EF_FLOW\{k}\#i` | real | Flow of each point |
| `Input\EFF_DATA\{k}\<i+1>` | fraction | Efficiency of each point |
| `Input\EFF_COEF1\{k}` | real | c1 of the efficiency polynomial (`EFF_COEF2`..`4` alike) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\HEAD_CAL` | HEAD | Head read off the curve |
| `Output\CEFF` | fraction | Efficiency read off the curve |
