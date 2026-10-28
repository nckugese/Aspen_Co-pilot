# PetroFrac pumparounds

Paths are under `\Data\Blocks\{name}\`. A pumparound draws liquid from a main-column stage, cools or heats it and returns it to another stage.

1. `add_element` on `Subobjects\Pumparounds` with an ID, e.g. `1`; its fields are keyed by that ID.
2. Set the draw and return stages and the type.
3. `PARTIAL` takes a flow and one thermal spec (temperature, temperature change or duty). `TOTAL` locks the flow, and once one thermal spec is set the other two lock.

A `TOTAL` draw returned above its draw stage leaves the stages below dry; return it below.

A pumparound back to stage 1 can replace the condenser (`CTYPE` `NONE-TOPPA`); one on the bottom stages can replace the reboiler (`RTYPE` `NONE-BOTPA`).

| Path | Type | Purpose |
|---|---|---|
| `Input\DRAW\{id}` | int | Draw stage |
| `Input\RETURN\{id}` | int | Return stage |
| `Input\TYPE\{id}` | `PARTIAL`, `TOTAL` | Part of the stage liquid, or all of it |
| `Input\BASIS_PAFLW\{id}` | MOLE-FLOW | Pumparound flow (`PARTIAL`) |
| `Input\PA_TEMP\{id}` | TEMPERATURE | Return temperature |
| `Input\PA_DELT\{id}` | DELTA-T | Return minus draw temperature |
| `Input\PA_DUTY\{id}` | ENTHALPY-FLO | Heat added (negative: removed) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\PA_DUTY_OUT\{id}` | ENTHALPY-FLO | Pumparound duty |
| `Output\PA_TEMP_OUT\{id}` | TEMPERATURE | Return temperature |
| `Output\PA_DELT_OUT\{id}` | DELTA-T | Temperature change |
| `Output\PA_LIQ_FLOW\{id}` | MOLE-FLOW | Pumparound flow |
