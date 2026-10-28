# RadFrac analysis and report options

Paths are under `\Data\Blocks\{name}\`.

| Path | Type | Purpose |
|---|---|---|
| `Input\TARGET` | `TARGET`, `NOTARGET` | Column targeting on or off |
| `Input\HYDANAL` | `HYDANAL`, `NOHYDANAL` | Hydraulic analysis on or off |
| `Input\KEY_SELECT` | `K-VALUE`, `SPLIT-FRACTI`, `COMP-PROFILE`, `USER` | How targeting picks the light and heavy keys |

## Report

| Path | Type | Purpose |
|---|---|---|
| `Input\PROFILE` | `PROFILE`, `NOPROFILE` | Stage profiles in the report |
| `Input\HYDRAULIC` | `HYDRAULIC`, `NOHYDRAULIC` | Hydraulics in the report |
| `Input\TRAY_OPTION` | `BRIEF`, `INCL-TRAYS`, `ALL-TRAYS` | Which stages the report lists |
| `Input\FORMAT` | `PROFILE`, `STAGE`, `COMBINED` | Layout of the stage report |
| `Input\ORDER` | `TOP-DOWN`, `BOTTOM-UP` | Order of the stages in the report |

## Results (with `TARGET`)

| Path | Type | Purpose |
|---|---|---|
| `Output\EXERGY\{stage}` | ENTHALPY-FLO | Exergy per stage from targeting |
| `Output\ENTHALPY\{stage}` | ENTHALPY-FLO | Enthalpy per stage from targeting (temperature-enthalpy profile) |
| `Output\B_TEMP4\{stage}` | TEMPERATURE | Stage temperature on the targeting profile |
