# RadFrac efficiencies

Paths are under `\Data\Blocks\{name}\`.

Without entries every stage has efficiency 1.

| Path | Type | Purpose |
|---|---|---|
| `Input\EFF` | `MURPHREE`, `VAPOR` | Efficiency type |
| `Input\OPT_EFF_METH` | `STAGE`, `COMPONENT` | Given per stage or per component |
| `Input\STAGE_EFF\{stage}` | fraction | Stage efficiency |

Stages between two entries take interpolated values.

| Path | Type | Purpose |
|---|---|---|
| `Input\COMP_EFF\{stage}\{comp}` | fraction | Component efficiency on a stage (`OPT_EFF_METH=COMPONENT`) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\EFFICIENCY\{stage}\{comp}` | fraction | Efficiency used on a stage |
