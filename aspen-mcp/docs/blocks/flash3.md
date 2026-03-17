# Flash3 (Three-phase Flash)

Three-outlet flash separator (vapor + liquid-1 + liquid-2). For liquid-liquid-vapor systems.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| V | OUT | Vapor |
| L1 | OUT | First liquid |
| L2 | OUT | Second liquid |
| HS | OUT | Heat stream out |

## Key Input Paths

Same as Flash2:

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Flash temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Flash pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Heat duty |
| `\Data\Blocks\{name}\Input\VFRAC` | float | Vapor fraction |

## When to Use

- Systems with two immiscible liquid phases (e.g. water + organic).
- Requires a property method that supports liquid-liquid equilibrium (e.g. NRTL, UNIQUAC).
