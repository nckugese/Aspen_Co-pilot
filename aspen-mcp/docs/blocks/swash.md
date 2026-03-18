# Swash (Solid Washer)

Solid washing model for removing contaminants from solids using a wash liquid.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed (solids + liquid) |
| WASH | IN | Wash liquid |
| P | OUT | Washed product |
| FILT | OUT | Filtrate |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\LS_RATIO` | float | Liquid-to-solids mass ratio |
| `\Data\Blocks\{name}\Input\MIX_EFF` | float | Mixing efficiency |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\BYPASS` | float | Bypass fraction |
| `\Data\Blocks\{name}\Output\B_TEMP` | float | Outlet temperature |
| `\Data\Blocks\{name}\Output\QCALC` | float | Heat duty |
| `\Data\Blocks\{name}\Output\QNET` | float | Net duty |

## Typical Setup

1. Place: `place_block(session, 'SW1', 'Swash')`
2. L/S ratio: `set_value(session, aspen_path='\Data\Blocks\SW1\Input\LS_RATIO', value='3')`
3. Mixing efficiency: `set_value(session, aspen_path='\Data\Blocks\SW1\Input\MIX_EFF', value='0.9')`
