# Vscrub (Venturi Scrubber)

Venturi scrubber for removing fine particles from gas streams using liquid droplets.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| GAS | IN | Gas feed |
| LIQ | IN | Scrubbing liquid |
| GOUT | OUT | Clean gas |
| LOUT | OUT | Liquid + collected solids |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\SCRUB_TYPE` | string | Scrubber type |
| `\Data\Blocks\{name}\Input\MODE` | string | Operating mode |
| `\Data\Blocks\{name}\Input\MODEL` | string | Calculation method |
| `\Data\Blocks\{name}\Input\SOLID_SPLIT` | float | Fraction of solids to liquid outlet |
| `\Data\Blocks\{name}\Input\SHARPNESS` | float | Separation sharpness |
| `\Data\Blocks\{name}\Input\EFF` | float | Separation efficiency |
| `\Data\Blocks\{name}\Input\GAS_VEL` | float | Gas velocity at throat |
| `\Data\Blocks\{name}\Input\DIAM_THROAT` | float | Throat diameter |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\SOLD_RECOV` | float | Fraction of solids collected |
| `\Data\Blocks\{name}\Output\D50` | float | D50 of separation curve |
| `\Data\Blocks\{name}\Output\PDRP` | float | Calculated pressure drop |
| `\Data\Blocks\{name}\Output\EFF_OUT` | float | Calculated separation efficiency |
| `\Data\Blocks\{name}\Output\VELOCITY` | float | Gas velocity at throat |
| `\Data\Blocks\{name}\Output\SAUTER_DIAM` | float | Sauter mean drop diameter |
| `\Data\Blocks\{name}\Output\DIAM` | float | Calculated throat diameter |

## Typical Setup

1. Place: `place_block(session, 'VS1', 'Vscrub')`
2. Type and model selection.
3. Set throat geometry or gas velocity.
