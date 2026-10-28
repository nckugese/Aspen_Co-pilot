# RadFrac pumparounds

Paths are under `\Data\Blocks\{name}\`. A pumparound draws from one stage and returns to another.

1. `add_element` on `Subobjects\Pumparounds` with an ID, e.g. `P-1`; its fields are keyed by that ID.
2. Set draw and return stages, phase and type.
3. `PARTIAL` takes a flow and one thermal spec. With `TOTAL` the flow is locked, and once one thermal spec is set the other thermal fields lock.

A `TOTAL` liquid draw returned above its draw stage leaves the stages below dry; return it below.

| Path | Type | Purpose |
|---|---|---|
| `Input\SOURCE_STAGE\{pa}` | int | Draw stage |
| `Input\DEST_STAGE\{pa}` | int | Return stage |
| `Input\DRAW_PHASE\{pa}` | `L` | Phase drawn |
| `Input\TYPE\{pa}` | `PARTIAL`, `TOTAL` | Part of the phase, or all of it |
| `Input\BASIS_CSFLOW\{pa}` | flow | Pumparound flow |
| `Input\CS_TEMP\{pa}` | TEMPERATURE | Return temperature |
| `Input\CS_DELT\{pa}` | DELTA-T | Return minus draw temperature |
| `Input\CS_DUTY\{pa}` | ENTHALPY-FLO | Heat added (negative: removed) |
| `Input\NPHASE\{pa}` | int | Phases in the return flash; 2 unlocks `CS_VFRAC` |
| `Input\CS_VFRAC\{pa}` | fraction | Return vapor fraction; enterable once `NPHASE\{pa}` is 2 |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\DUTY4\{pa}` | ENTHALPY-FLO | Pumparound duty |
| `Output\B_TEMP3\{pa}` | TEMPERATURE | Return temperature |
| `Output\LIQ_FLOW3\{pa}` | MOLE-FLOW | Pumparound flow |
