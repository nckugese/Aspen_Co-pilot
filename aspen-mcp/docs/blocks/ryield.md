# RYield (Yield Reactor)

Reactor where you specify product yields directly. No reaction mechanism needed.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| P | OUT | Product |
| HS | OUT | Heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Reactor temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Reactor pressure |
| `\Data\Blocks\{name}\Input\MASS_YIELD\{comp}` | float | Mass yield of each component |
| `\Data\Blocks\{name}\Input\MOLE_YIELD\{comp}` | float | Mole yield of each component |

## When to Use

- Known product distribution from experimental data.
- Complex processes where detailed kinetics/stoichiometry is unknown (e.g. coal gasification, pyrolysis).

## Gotchas

- Yields must sum to 1.0 (mass basis) or be normalized.
- Does not use reaction sets — yields are specified directly.
