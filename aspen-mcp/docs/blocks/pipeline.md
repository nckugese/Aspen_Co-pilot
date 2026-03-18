# Pipeline (Multi-Segment Pipeline)

Multi-segment pipeline model. Models long pipelines with varying elevation, diameter, and thermal environment along the length.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| P | OUT | Product |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\PIPE_METH` | string | Pipeline pressure drop method |
| `\Data\Blocks\{name}\Input\P_INLET` | float | Specified inlet pressure |
| `\Data\Blocks\{name}\Input\T_INLET` | float | Specified inlet temperature |

> Pipeline segments with geometry (length, diameter, elevation, roughness) are defined per-segment in the block's sub-nodes.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\B_PRES_IN` | float | Calculated inlet pressure |
| `\Data\Blocks\{name}\Output\B_TEMP_IN` | float | Calculated inlet temperature |
| `\Data\Blocks\{name}\Output\B_PRES_OUT` | float | Outlet pressure |
| `\Data\Blocks\{name}\Output\B_TEMP_OUT` | float | Outlet temperature |
| `\Data\Blocks\{name}\Output\MASSFLOW` | float | Mass flow rate |
| `\Data\Blocks\{name}\Output\GAS_FLOW` | float | Stock tank gas flow |
| `\Data\Blocks\{name}\Output\OIL_FLOW` | float | Stock tank oil flow |
| `\Data\Blocks\{name}\Output\WATER_FLOW` | float | Stock tank water flow |
| `\Data\Blocks\{name}\Output\ENTH_BAL` | float | Heat duty |
| `\Data\Blocks\{name}\Output\HOLDUP_OUT2` | float | Total liquid holdup |

## Typical Setup

1. Place: `place_block(session, 'PL1', 'Pipeline')`
2. Inlet conditions: `set_value(session, aspen_path='\Data\Blocks\PL1\Input\P_INLET', value='50', unit='atm')`
3. Define pipeline segments with geometry.

## Gotchas

- Use Pipe for single-segment piping. Pipeline is for multi-segment systems.
- Supports petroleum pipeline calculations (oil, gas, water holdup).
- Also supports solids conveying.
