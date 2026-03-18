# REquil (Equilibrium Reactor)

Chemical and phase equilibrium reactor with specified equilibrium reactions. Faster than RGibbs when you know which reactions occur.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| V | OUT | Vapor product |
| L | OUT | Liquid product |
| HS | OUT | Heat stream out |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Specified temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Specified pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Specified heat duty |
| `\Data\Blocks\{name}\Input\VFRAC` | float | Specified vapor fraction (0–1) |
| `\Data\Blocks\{name}\Input\EXT_SPEC\1` | float | Molar extent of reaction (products generation) |
| `\Data\Blocks\{name}\Input\DELT\1` | float | Temperature approach for equilibrium |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\B_TEMP` | float | Outlet temperature |
| `\Data\Blocks\{name}\Output\B_PRES` | float | Outlet pressure |
| `\Data\Blocks\{name}\Output\QCALC` | float | Calculated heat duty |
| `\Data\Blocks\{name}\Output\QNET` | float | Net heat duty |
| `\Data\Blocks\{name}\Output\B_VFRAC` | float | Calculated vapor fraction |

## When to Use

- Known reactions that reach equilibrium.
- Faster than RGibbs when you know which reactions occur.
- Two product streams (vapor + liquid).

## Typical Setup

1. Place: `place_block(session, 'R1', 'REquil')`
2. Temperature: `set_value(session, aspen_path='\Data\Blocks\R1\Input\TEMP', value='500', unit='C')`
3. Pressure: `set_value(session, aspen_path='\Data\Blocks\R1\Input\PRES', value='1', unit='atm')`

## Gotchas

- Requires specifying equilibrium reactions (unlike RGibbs which finds them automatically).
- Temperature approach (DELT) allows you to offset from true equilibrium.
