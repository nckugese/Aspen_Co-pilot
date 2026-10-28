# MultiFrac flow ratios and flow specs

Paths are under `\Data\Blocks\{name}\`. Each one holds a flow by adjusting a stage duty, so it adds no column spec.

## Flow ratios

1. `add_element` on `Subobjects\Flow Ratios` with an ID (`1`); fields are keyed by it.

| Path | Type | Purpose |
|---|---|---|
| `Input\FLOW_R_COL\{id}` | int | Column of the flow in the numerator |
| `Input\FLOW_R_STAGE\{id}` | int | Its stage |
| `Input\FLOW_R_PHASE\{id}` | `L`, `V` | Its phase |
| `Input\BASE_COL\{id}` | int | Column of the flow in the denominator |
| `Input\BASE_STAGE\{id}` | int | Its stage |
| `Input\BASE_PHASE\{id}` | `V`, `L` | Its phase |
| `Input\BASIS_RATIO\{id}` | ratio | Ratio to hold |
| `Input\OPT_FR_ADJ\{id}` | `DUTY` | What is adjusted: a stage duty |
| `Input\Q_COL\{id}` | int | Column of the adjusted duty |
| `Input\Q_STAGE\{id}` | int | Stage of the adjusted duty |

## Holding the liquid or vapor flow of a stage

1. Insert a row on `BASIS_L_SPEC\{col}` (liquid) or `BASIS_V_SPEC\{col}` (vapor) and label it with the stage; the other fields of that stage then appear.

| Path | Type | Purpose |
|---|---|---|
| `Input\BASIS_L_SPEC\{col}\{stage}` | flow | Liquid leaving the stage |
| `Input\OPT_LSPEC\{col}\{stage}` | `STAGE` | The adjusted duty sits on a stage |
| `Input\L_SPEC_QCOL\{col}\{stage}` | int | Column of the adjusted duty |
| `Input\L_SPEC_QSTAG\{col}\{stage}` | int | Stage of the adjusted duty |
| `Input\BASIS_V_SPEC\{col}\{stage}` | flow | Vapor leaving the stage; `OPT_VSPEC`, `V_SPEC_QCOL`, `V_SPEC_QSTAG` as for liquid |

The vapor spec converged with its duty one stage above (vapor of stage 3, duty on stage 2); with the duty on the same stage or the one below the column was rejected as singular.

A flow-spec duty cannot sit on a stage that already has a side duty (`HEATER_DUTY`).
