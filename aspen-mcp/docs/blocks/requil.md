# REquil (Equilibrium Reactor)

Chemical and phase equilibrium reactor with specified reactions.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| V | OUT | Vapor product |
| L | OUT | Liquid product |
| HS | OUT | Heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Reactor temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Reactor pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Heat duty |

## When to Use

- Known reactions that reach equilibrium.
- Faster than RGibbs when you know which reactions occur.
- Two product streams (vapor + liquid).
