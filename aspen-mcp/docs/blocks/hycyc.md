# HyCyc (Hydrocyclone)

Hydrocyclone for liquid-solid separation using centrifugal force in a liquid medium.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed (slurry) |
| OF | OUT | Overflow (fines) |
| UF | OUT | Underflow (coarse) |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\MODEL` | string | Hydrocyclone model |
| `\Data\Blocks\{name}\Input\CALC_MODE` | string | Operating mode (design/rating) |
| `\Data\Blocks\{name}\Input\METHOD` | string | Efficiency correlation (Plitt, Nageswararao) |
| `\Data\Blocks\{name}\Input\SOLID_SPLIT` | float | Fraction of solids to underflow |
| `\Data\Blocks\{name}\Input\SHARPNESS` | float | Separation sharpness |
| `\Data\Blocks\{name}\Input\EFF` | float | Separation efficiency |
| `\Data\Blocks\{name}\Input\DIAM` | float | Hydrocyclone diameter |
| `\Data\Blocks\{name}\Input\NCYCLONE` | float | Number of hydrocyclones |
| `\Data\Blocks\{name}\Input\DES_PDROP` | float | Design pressure drop |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\PDRP` | float | Pressure drop |
| `\Data\Blocks\{name}\Output\DIAM_OUT` | float | Calculated diameter |
| `\Data\Blocks\{name}\Output\D50` | float | D50 of separation curve |
| `\Data\Blocks\{name}\Output\NUMBER` | int | Calculated number of cyclones |
| `\Data\Blocks\{name}\Output\CEFF` | float | Overall separation efficiency |
| `\Data\Blocks\{name}\Output\SFRAC` | float | Fraction of solids to underflow |

## Typical Setup

1. Place: `place_block(session, 'HC1', 'HyCyc')`
2. Model and mode selection.
3. Set diameter or efficiency target.
