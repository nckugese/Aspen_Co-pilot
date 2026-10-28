# Crystallizer: recirculation

A loop that draws slurry from the vessel through the heater and back. Paths are under `\Data\Blocks\{name}\`; basics in [crystallizer.md](crystallizer.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_REC` | `FRAC`, `FLOW`, `DELT` | Loop set by a fraction of the outlet (default), a flow, or the heater's temperature change |
| `Input\FRAC_RFLOW` | fraction | Recycled fraction of the vessel outflow |
| `Input\BASIS_FLOWR` | MOLE-FLOW | Loop flow |
| `Input\HEATER_DELT` | DELTA-T | Heater outlet minus inlet temperature |

`FRAC_RFLOW` 0.5 made the loop flow equal to the product flow.

| Path | Type | Purpose |
|---|---|---|
| `Output\SOL_FLOW` | MASS-FLOW | Loop flow |
