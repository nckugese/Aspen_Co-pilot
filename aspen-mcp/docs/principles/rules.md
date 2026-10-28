# Principle rules (fallback)

In learning mode, a group that carries no `principle` key gets one from this table: the type
of a block and the field a `set` or `sweep` step writes on it. Nothing else is read -- not the
block's other settings, not block or model names. A chip found this way says so in its tooltip.
No match: no chip. In learning mode `workbench_edit` names the headed groups that change the
model and get no key either way.

Fields are paths under `\Data\Blocks\{name}\` ([blocks/](../blocks/index.md)). A field also
matches the rows under it (`Input\FEED_STAGE` covers `Input\FEED_STAGE\{stream}`). Types and
fields match without regard to case. Each row maps to one key; the first matching row wins.

| Block type | Fields | Key |
|---|---|---|
| RadFrac | `Input\BASIS_RR`, `Input\BASIS_BR`, `Input\BASIS_L1`, `Input\BASIS_VN`, `Input\Q1`, `Input\QN` | `reflux_vs_duty` |
| RadFrac | `Input\NSTAGE`, `Input\FEED_STAGE` | `stages_separation` |
| RadFrac | `Input\BASIS_D`, `Input\BASIS_B`, `Input\D:F`, `Input\B:F` | `mass_balance` |
| RadFrac | `Input\PRES1` | `relative_volatility` |
| DSTWU | `Input\RR` | `reflux_vs_duty` |
| DSTWU | `Input\NSTAGE`, `Input\RECOVL`, `Input\RECOVH` | `stages_separation` |
| DSTWU | `Input\PTOP` | `relative_volatility` |
| Distl | `Input\RR` | `reflux_vs_duty` |
| Distl | `Input\NSTAGE`, `Input\FEED_LOC` | `stages_separation` |
| Distl | `Input\D_F` | `mass_balance` |
| Distl | `Input\PTOP` | `relative_volatility` |
| Flash2, Flash3 | `Input\TEMP`, `Input\PRES`, `Input\VFRAC` | `flash_vle` |
| Flash2, Flash3 | `Input\DUTY` | `energy_balance` |
| Heater | `Input\TEMP`, `Input\DUTY`, `Input\VFRAC`, `Input\DELT`, `Input\DEGSUB`, `Input\DEGSUP` | `energy_balance` |
| HeatX | `Input\MIN_TAPP`, `Input\AREA`, `Input\VALUE` | `heat_recovery` |
| RStoic | `Input\CONV`, `Input\EXTENT` | `conversion_selectivity` |
| RCSTR | `Input\VOL`, `Input\RES_TIME`, `Input\TEMP` | `conversion_selectivity` |
| RPlug | `Input\LENGTH`, `Input\DIAM`, `Input\NTUBE`, `Input\REAC_TEMP` | `conversion_selectivity` |
| REquil, RGibbs | `Input\TEMP`, `Input\PRES` | `conversion_selectivity` |
| FSplit | `Input\FRAC` | `recycle_purge` |

Never inferred, because type and field cannot tell them apart from the rows above:
`absorption_factor`, `henry_law` (an absorber is a RadFrac like any column) and `azeotrope`.
The AI attaches those itself.
