# Decanter (Liquid-Liquid Separator)

Liquid-liquid phase separator (no vapor product).

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| L1 | OUT | First liquid |
| L2 | OUT | Second liquid |
| HS | OUT | Heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Heat duty |

## When to Use

- Liquid-liquid extraction systems.
- Requires property method with LLE capability.
