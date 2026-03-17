# Pump

Liquid pump. For gas compression use Compr instead.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| WS | IN | Work stream |
| P | OUT | Product |
| WD | OUT | Work duty |
| WS | OUT | Work stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\DELP` | float | Pressure increase |
| `\Data\Blocks\{name}\Input\PRES` | float | Discharge pressure |
| `\Data\Blocks\{name}\Input\EFF` | float | Pump efficiency (0-1) |

## Typical Setup Steps

1. Place: `place_block(session, 'P1', 'Pump')`
2. Pressure: `set_value(session, aspen_path='\Data\Blocks\P1\Input\PRES', value='5', unit='atm')`
3. Efficiency: `set_value(session, aspen_path='\Data\Blocks\P1\Input\EFF', value='0.75')`

## Gotchas

- Pump is for **liquids only**. Gas feed will cause errors.
- Use `Compr` for gas compression.
