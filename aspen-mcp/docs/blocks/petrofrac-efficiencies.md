# PetroFrac efficiencies

Paths are under `\Data\Blocks\{name}\`. Stage efficiencies of the main column (strippers have their own, keyed by the stripper ID).

| Path | Type | Purpose |
|---|---|---|
| `Input\EFF` | `MURPHREE`, `VAPOR` | Efficiency type |
| `Input\OPT_EFF_METH` | `STAGE`, `COMPONENT`, `SECTION` | Given per stage, per stage and component, or per section |
| `Input\STAGE_EFF\{stage}` | fraction | Stage efficiency (`STAGE`; rows labelled by stage) |

Stages between two entries take interpolated values.

| Path | Type | Purpose |
|---|---|---|
| `Input\COMP_EFF_IN\{stage}\{comp}` | fraction | Component efficiency on a stage (`COMPONENT`) |
| `Input\STEFF_STAGE1\{id}` | int | First stage of a section (`SECTION`) |
| `Input\STEFF_STAGE2\{id}` | int | Section ends at this stage |
| `Input\STEFF_SEC\{id}` | fraction | Efficiency used on every stage of the range |

Section rows need a label (`set_label` with a section number, `1`, `2`, ...): an unlabelled row leaves the block incomplete.

## Strippers

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_SEFF_MET\{stripper}` | `STAGE` | Stripper efficiencies given per stage |
| `Input\STR_STAGE_EF\{stripper}\{stage}` | fraction | Stripper stage efficiency (rows labelled by stripper stage) |

Strippers have no `EFF` of their own: the column's applies, and `Output\ST_EFF_TYPE\{stripper}` reports it.

## Thermal efficiency

| Path | Type | Purpose |
|---|---|---|
| `Input\INCL_THEFF` | `YES`, `NO` | Use thermal efficiencies |
| `Input\OPT_TEFF_MET` | `STAGE`, `SECTION` | Given per stage or per section |
| `Input\THERM_EFF1` | `VAPOR`, `LIQUID` | Phase the thermal efficiency applies to |
| `Input\STAGE_THEFF\{stage}` | fraction | Thermal efficiency of a stage |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\COMP_EFF\{stage}\{comp}` | fraction | Efficiency used on a stage |
