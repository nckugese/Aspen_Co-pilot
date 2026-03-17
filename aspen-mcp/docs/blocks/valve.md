# Valve

Pressure reduction valve (throttling).

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| P | OUT | Product |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\P_OUT` | float | Outlet pressure |
| `\Data\Blocks\{name}\Input\DP` | float | Pressure drop |

## Typical Setup Steps

1. Place: `place_block(session, 'V1', 'Valve')`
2. Outlet pressure: `set_value(session, aspen_path='\Data\Blocks\V1\Input\P_OUT', value='1', unit='atm')`
