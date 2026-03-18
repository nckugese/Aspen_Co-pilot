# Pipe (Single-Segment Pipe)

Single-segment pipe model for pressure drop and heat transfer calculations in piping systems.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| P | OUT | Product |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\PIPE_METH` | string | Pipe pressure drop method |
| `\Data\Blocks\{name}\Input\LENGTH` | float | Pipe length |
| `\Data\Blocks\{name}\Input\IN_DIAM` | float | Inner diameter |
| `\Data\Blocks\{name}\Input\ELEVATION` | float | Pipe rise (elevation change) |
| `\Data\Blocks\{name}\Input\ANGLE` | float | Pipe angle |
| `\Data\Blocks\{name}\Input\ROUGHNESS` | float | Pipe wall roughness |
| `\Data\Blocks\{name}\Input\T_OUT` | float | Outlet temperature (if heat transfer specified) |
| `\Data\Blocks\{name}\Input\H_T_COEFF` | float | Heat transfer coefficient |
| `\Data\Blocks\{name}\Input\FLUX` | float | Heat flux per unit length |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\DPTOTL` | float | Total pressure drop |
| `\Data\Blocks\{name}\Output\DPFRIC` | float | Frictional pressure drop |
| `\Data\Blocks\{name}\Output\DPELEV` | float | Elevation pressure drop |
| `\Data\Blocks\{name}\Output\DPACC` | float | Acceleration pressure drop |
| `\Data\Blocks\{name}\Output\DUTY` | float | Heat duty |
| `\Data\Blocks\{name}\Output\EQUIV-LEN` | float | Equivalent length |

## Typical Setup

1. Place: `place_block(session, 'PIPE1', 'Pipe')`
2. Length: `set_value(session, aspen_path='\Data\Blocks\PIPE1\Input\LENGTH', value='100', unit='meter')`
3. Diameter: `set_value(session, aspen_path='\Data\Blocks\PIPE1\Input\IN_DIAM', value='0.1', unit='meter')`

## Gotchas

- Use Pipeline for multi-segment piping systems.
- Includes fittings (enlargements, contractions, orifices) as additional inputs.
- Also supports solids conveying calculations.
