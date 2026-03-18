# Makeup (Stream Makeup)

Adds makeup material to a stream to maintain specified flow, composition, or property targets. Often used in recycle loops.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| M | IN | Makeup source |
| P | OUT | Product |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Specified temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Specified pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Specified duty |
| `\Data\Blocks\{name}\Input\T_EST` | float | Temperature estimate |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\SharedData\OutletTemperature` | float | Outlet flash temperature |
| `\Data\Blocks\{name}\SharedData\OutletPressure` | float | Outlet flash pressure |
| `\Data\Blocks\{name}\SharedData\OutletVaporFraction` | float | Outlet vapor fraction |
| `\Data\Blocks\{name}\SharedData\NetDuty` | float | Heat duty |

## Typical Setup

1. Place: `place_block(session, 'MK1', 'Makeup')`
2. Connect feed stream and makeup source.
3. Specify makeup targets (total flow, component flow, etc.).

## Gotchas

- Commonly used in recycle loops to replace lost material.
- Output paths use `SharedData` instead of the standard `Output` node.
