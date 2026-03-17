# Flash2 (Two-phase Flash)

Two-outlet flash separator (vapor + liquid).

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| V | OUT | Vapor |
| L | OUT | Liquid |
| WD | OUT | Work duty |
| HS | OUT | Heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Flash temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Flash pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Heat duty |
| `\Data\Blocks\{name}\Input\VFRAC` | float | Vapor fraction |

## Specification

Specify 2 of: temperature, pressure, duty, vapor fraction. Most common: temperature + pressure.

## Typical Setup Steps

1. Place: `place_block(session, 'F1', 'Flash2')`
2. Temperature: `set_value(session, aspen_path='\Data\Blocks\F1\Input\TEMP', value='25', unit='C')`
3. Pressure: `set_value(session, aspen_path='\Data\Blocks\F1\Input\PRES', value='1', unit='atm')`
