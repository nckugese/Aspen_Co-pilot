# MCompr (Multi-stage Compressor)

Multi-stage compressor with intercoolers.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| S1F | IN | First stage feed |
| IF | IN | Intermediate feed |
| WS | IN | Work stream |
| HS | IN | Heat stream |
| FLS | OUT | Final stage product |
| LK | OUT | Liquid knockout |
| WD | OUT | Work duty |
| WS | OUT | Work stream out |
| HS | OUT | Heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TYPE` | string | `ISENTROPIC`, `POLYTROPIC` |
| `\Data\Blocks\{name}\Input\OPT_SPEC` | string | **Must set first**: `PRES`, `PRATIO` |
| `\Data\Blocks\{name}\Input\PRES` | float | Final discharge pressure |
| `\Data\Blocks\{name}\Input\NSTAGE` | int | Number of compression stages |
| `\Data\Blocks\{name}\Input\SEFF` | float | Isentropic efficiency |

## Gotchas

- Same `OPT_SPEC` requirement as Compr — set it before setting pressure.
- Must also specify number of stages and intercooler configuration.
