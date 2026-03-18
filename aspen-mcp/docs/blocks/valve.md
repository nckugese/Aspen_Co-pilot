# Valve

Pressure reduction (throttling) valve. Models isenthalpic flash at a lower outlet pressure.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| P | OUT | Product |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\P_OUT` | float | Specified outlet pressure |
| `\Data\Blocks\{name}\Input\P_DROP` | float | Specified pressure drop |
| `\Data\Blocks\{name}\Input\MODE` | string | Calculation type (`DESIGN` or `RATING`) |
| `\Data\Blocks\{name}\Input\OPT_DESIGN` | string | Valve pressure spec in design mode |
| `\Data\Blocks\{name}\Input\OPT_RATING` | string | Valve pressure spec in rating mode |
| `\Data\Blocks\{name}\Input\VAL_POSN` | float | Valve % opening (rating mode) |
| `\Data\Blocks\{name}\Input\FLO_COEF` | float | Flow coefficient Cv (rating mode) |

> In design mode (default), specify either `P_OUT` or `P_DROP`. In rating mode, specify valve characteristics and position.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\P_OUT_OUT` | float | Calculated outlet pressure |
| `\Data\Blocks\{name}\Output\VALVE_DP` | float | Calculated pressure drop |
| `\Data\Blocks\{name}\Output\VALVE_POSN` | float | Calculated valve % opening |
| `\Data\Blocks\{name}\Output\CHOKE_POUT` | float | Choked outlet pressure |
| `\Data\Blocks\{name}\Output\CAV_INDX` | float | Cavitation index |

## Typical Setup

1. Place: `place_block(session, 'V1', 'Valve')`
2. Outlet pressure: `set_value(session, aspen_path='\Data\Blocks\V1\Input\P_OUT', value='1', unit='atm')`
