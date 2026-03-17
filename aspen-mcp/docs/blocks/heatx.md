# HeatX (Two-stream Heat Exchanger)

Rigorous two-stream heat exchanger with hot and cold sides.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| H | IN | Hot stream in |
| C | IN | Cold stream in |
| H | OUT | Hot stream out |
| C | OUT | Cold stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\CALC_MODE` | string | `DESIGN`, `RATING`, `SIMULATION` |
| `\Data\Blocks\{name}\Input\DUTY` | float | Heat duty |
| `\Data\Blocks\{name}\Input\AREA` | float | Heat transfer area |
| `\Data\Blocks\{name}\Input\U` | float | Overall heat transfer coefficient |

## Gotchas

- Requires both hot and cold side connections.
- Choose calculation mode before setting other parameters.
- MHeatX (multi-stream) cannot be placed via COM.
