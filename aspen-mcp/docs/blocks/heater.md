# Heater (Heater / Cooler)

Simple heater or cooler. Specify outlet conditions or heat duty.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| P | OUT | Product |
| WD | OUT | Work duty |
| HS | OUT | Heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Outlet temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Outlet pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Heat duty |
| `\Data\Blocks\{name}\Input\VFRAC` | float | Outlet vapor fraction (0-1) |

## Specification

Specify 2 of: temperature, pressure, duty, vapor fraction. Most common: temperature + pressure.

## Typical Setup Steps

1. Place: `place_block(session, 'H1', 'Heater')`
2. Temperature: `set_value(session, aspen_path='\Data\Blocks\H1\Input\TEMP', value='40', unit='C')`
3. Pressure: `set_value(session, aspen_path='\Data\Blocks\H1\Input\PRES', value='1.5', unit='atm')`
