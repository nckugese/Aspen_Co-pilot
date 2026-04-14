# MCompr (Multi-Stage Compressor)

Multi-stage compressor with intercoolers between stages.

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

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TYPE` | string | Model type: `ISENTROPIC`, `POLYTROPIC` |
| `\Data\Blocks\{name}\Input\OPT_SPEC` | string | Spec type — **must set first**: `PRES`, `PRATIO` |
| `\Data\Blocks\{name}\Input\NSTAGE` | int | Number of compression stages |
| `\Data\Blocks\{name}\Input\PRES` | float | Final discharge pressure |
| `\Data\Blocks\{name}\Input\SEFF` | float | Isentropic efficiency (0–1) |

> **Important:** Set `OPT_SPEC` before setting the discharge pressure — same requirement as Compr.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\B_PRES2` | float | Outlet pressure |
| `\Data\Blocks\{name}\Output\QCALC2` | float | Total work |
| `\Data\Blocks\{name}\Output\DUTY_OUT` | float | Total cooling duty |
| `\Data\Blocks\{name}\Output\WNET` | float | Net work required |
| `\Data\Blocks\{name}\Output\QNET` | float | Net cooling duty |

## Typical Setup

1. Place: `place_block(session, 'MC1', 'MCompr')`
2. Stages: `set_value(session, aspen_path='\Data\Blocks\MC1\Input\NSTAGE', value='3')`
3. Type: `set_value(session, aspen_path='\Data\Blocks\MC1\Input\TYPE', value='ISENTROPIC')`
4. **OPT_SPEC first**: `set_value(session, aspen_path='\Data\Blocks\MC1\Input\OPT_SPEC', value='PRES')`
5. Pressure: `set_value(session, aspen_path='\Data\Blocks\MC1\Input\PRES', value='30', unit='atm')`
6. Efficiency: `set_value(session, aspen_path='\Data\Blocks\MC1\Input\SEFF', value='0.75')`

## Gotchas

- Same `OPT_SPEC` requirement as Compr — set it before setting pressure.
- Must specify number of stages and intercooler configuration.
- Liquid knockout streams (LK) collect any condensed liquid from intercoolers.
