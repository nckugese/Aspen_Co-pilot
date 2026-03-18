# RYield (Yield Reactor)

Reactor where you specify product yields directly. No reaction mechanism or stoichiometry needed.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| P | OUT | Product |
| HS | OUT | Heat stream out |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Specified temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Specified pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Specified heat duty |
| `\Data\Blocks\{name}\Input\VFRAC` | float | Specified vapor fraction (0–1) |
| `\Data\Blocks\{name}\Input\DELT` | float | Specified temperature change |
| `\Data\Blocks\{name}\Input\MASS_YIELD\{comp}` | float | Mass yield of each component |
| `\Data\Blocks\{name}\Input\MOLE_YIELD\{comp}` | float | Mole yield of each component |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\B_TEMP` | float | Outlet temperature |
| `\Data\Blocks\{name}\Output\B_PRES` | float | Outlet pressure |
| `\Data\Blocks\{name}\Output\QCALC` | float | Calculated heat duty |
| `\Data\Blocks\{name}\Output\QNET` | float | Net heat duty |
| `\Data\Blocks\{name}\Output\B_VFRAC` | float | Calculated vapor fraction |
| `\Data\Blocks\{name}\Output\B_IDELT` | float | Calculated temperature change |

## When to Use

- Known product distribution from experimental data.
- Complex processes where detailed kinetics/stoichiometry is unknown (e.g. coal gasification, pyrolysis).

## Typical Setup

1. Place: `place_block(session, 'R1', 'RYield')`
2. Temperature: `set_value(session, aspen_path='\Data\Blocks\R1\Input\TEMP', value='800', unit='C')`
3. Pressure: `set_value(session, aspen_path='\Data\Blocks\R1\Input\PRES', value='1', unit='atm')`
4. Set yields: `set_value(session, aspen_path='\Data\Blocks\R1\Input\MASS_YIELD\CO2', value='0.44')`

## Gotchas

- Yields must sum to 1.0 (mass basis) or be normalized.
- Does not use reaction sets — yields are specified directly.
- Use DELT (temperature change) as an alternative to specifying absolute TEMP.
