# Pump

Liquid pump for pressure increase. For gas compression, use Compr instead.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| WS | IN | Work stream |
| P | OUT | Product |
| WD | OUT | Work duty |
| WS | OUT | Work stream out |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\PUMP-TYPE` | string | Model type |
| `\Data\Blocks\{name}\Input\PRES` | float | Specified discharge pressure |
| `\Data\Blocks\{name}\Input\DELP` | float | Specified pressure increase |
| `\Data\Blocks\{name}\Input\PRATIO` | float | Specified pressure ratio |
| `\Data\Blocks\{name}\Input\POWER` | float | Specified power required |
| `\Data\Blocks\{name}\Input\EFF` | float | Pump efficiency (0–1) |
| `\Data\Blocks\{name}\Input\DEFF` | float | Driver efficiency (0–1) |

> Specify one pressure spec (PRES, DELP, PRATIO, or POWER) plus an efficiency.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\FLUID_POWER` | float | Fluid power |
| `\Data\Blocks\{name}\Output\BRAKE_POWER` | float | Calculated brake power |
| `\Data\Blocks\{name}\Output\ELEC_POWER` | float | Electricity |
| `\Data\Blocks\{name}\Output\VFLOW` | float | Volumetric flow rate |
| `\Data\Blocks\{name}\Output\POC` | float | Calculated discharge pressure |
| `\Data\Blocks\{name}\Output\PDRP` | float | Calculated pressure change |
| `\Data\Blocks\{name}\Output\PRES_RATIO` | float | Calculated pressure ratio |
| `\Data\Blocks\{name}\Output\HEAD_CAL` | float | Head developed |
| `\Data\Blocks\{name}\Output\CEFF` | float | Pump efficiency used |
| `\Data\Blocks\{name}\Output\WNET` | float | Net work required |

## Typical Setup

1. Place: `place_block(session, 'P1', 'Pump')`
2. Pressure: `set_value(session, aspen_path='\Data\Blocks\P1\Input\PRES', value='5', unit='atm')`
3. Efficiency: `set_value(session, aspen_path='\Data\Blocks\P1\Input\EFF', value='0.75')`

## Gotchas

- Pump is for **liquids only**. Gas feed will cause errors — use `Compr` for gas compression.
- If no efficiency is set, Aspen uses a default of 1.0 (ideal pump).
