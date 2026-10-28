# MultiFrac efficiencies

Paths are under `\Data\Blocks\{name}\`.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_EFF_METH` | `STAGE`, `COMPONENT` | One efficiency per stage, or per stage and component |
| `Input\EFF` | `VAPOR`, `MURPHREE` | Kind of efficiency |
| `Input\STAGE_EFF\{col}\{stage}` | fraction | Stage efficiency (row: `insert_row` + `set_label` the stage on `STAGE_EFF\{col}`) |
| `Input\COMP_EFF\{col}\{stage}\{comp}` | fraction | Component efficiency (two labels on `COMP_EFF\{col}`: the stage on index 0, the component on index 1) |
