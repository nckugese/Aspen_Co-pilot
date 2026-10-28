# FluidBed: operation

The bed is one temperature (`TYPE` `ISOTHERMAL`, the default). Paths are under `\Data\Blocks\{name}\`; basics in [fluidbed.md](fluidbed.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\TEMP_OPT` | `INLETTEMP`, `SPETEMP` | Bed temperature from the mixed inlets plus `DUTY`, or given |
| `Input\DUTY` | ENTHALPY-FLO | Heat added to the bed (`INLETTEMP`, default 0) |
| `Input\TEMP` | TEMPERATURE | Bed temperature (`SPETEMP`) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash (default 2) |
| `Input\PHASE` | `V`, `L`, `S` | The phase when `NPHASE` is 1 |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\TEMP` | TEMPERATURE | Bed temperature |
