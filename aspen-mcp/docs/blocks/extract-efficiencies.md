# Extract efficiencies

Paths are under `\Data\Blocks\{name}\`.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_EFF_METH` | `STAGE`, `COMPONENT` | One efficiency per stage, or per component and stage |
| `Input\STAGE_EFF\{stage}` | fraction | Stage efficiency (rows labelled by stage) |

An entry holds for the stages below it up to the next entry.

| Path | Type | Purpose |
|---|---|---|
| `Input\COMP_EFF\{stage}\{comp}` | fraction | Component efficiency on a stage; a stage row, then a component row |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\COMP_EFF\{stage}\{comp}` | fraction | Efficiency used per stage and component |
