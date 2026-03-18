# Screen

Screen separator for classifying solids by particle size on a vibrating screen.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| OVER | OUT | Oversize |
| UNDER | OUT | Undersize |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\STRENGTH` | float | Separation strength |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\EFF` | float | Overall efficiency |
| `\Data\Blocks\{name}\Output\TAGGART_EFF` | float | Taggart overall efficiency |
| `\Data\Blocks\{name}\Output\OVERSZ_EFF` | float | Oversize efficiency |
| `\Data\Blocks\{name}\Output\UNDERSZ_EFF` | float | Undersize efficiency |
| `\Data\Blocks\{name}\Output\FINES_D50` | float | Fines PSD median value |

## Typical Setup

1. Place: `place_block(session, 'SCR1', 'Screen')`
2. Set separation strength.
3. Define mesh/aperture sizes in the block's sub-nodes.
