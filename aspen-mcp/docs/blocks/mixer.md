# Mixer

Stream mixer — combines multiple inlet streams into one outlet. No required specs beyond connections.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed (multiple) |
| HS | IN | Heat stream |
| WS | IN | Work stream |
| PS | IN | Pseudo stream |
| P | OUT | Product |
| HS | OUT | Heat stream out |
| WS | OUT | Work stream out |
| PS | OUT | Pseudo stream out |
| WD | OUT | Work duty |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\PRES` | float | Outlet pressure (optional, defaults to min inlet) |

## Typical Setup

1. Place: `place_block(session, 'MIX1', 'Mixer')`
2. Connect streams — no additional configuration needed.
3. Optionally set outlet pressure.
