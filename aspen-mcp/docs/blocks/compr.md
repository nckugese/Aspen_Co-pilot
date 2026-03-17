# Compr (Compressor / Turbine)

Single-stage compressor or turbine for gas compression/expansion.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| WS | IN | Work stream in |
| P | OUT | Product |
| WD | OUT | Work duty out |
| WS | OUT | Work stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TYPE` | string | `ISENTROPIC`, `POLYTROPIC`, `POSITIVE-DIS` |
| `\Data\Blocks\{name}\Input\OPT_SPEC` | string | **Must set first**: `PRES`, `TEMP`, `POWER`, `PRATIO` |
| `\Data\Blocks\{name}\Input\PRES` | float | Discharge pressure (when OPT_SPEC=PRES) |
| `\Data\Blocks\{name}\Input\TEMP` | float | Discharge temperature (when OPT_SPEC=TEMP) |
| `\Data\Blocks\{name}\Input\POWER` | float | Power (when OPT_SPEC=POWER) |
| `\Data\Blocks\{name}\Input\PRATIO` | float | Pressure ratio (when OPT_SPEC=PRATIO) |
| `\Data\Blocks\{name}\Input\SEFF` | float | Isentropic efficiency (0-1) |
| `\Data\Blocks\{name}\Input\PEFF` | float | Polytropic efficiency (0-1) |
| `\Data\Blocks\{name}\Input\MEFF` | float | Mechanical efficiency (0-1) |

## Typical Setup Steps

1. Place: `place_block(session, 'COMP1', 'Compr')`
2. Type: `set_value(session, aspen_path='\Data\Blocks\COMP1\Input\TYPE', value='ISENTROPIC')`
3. **OPT_SPEC first**: `set_value(session, aspen_path='\Data\Blocks\COMP1\Input\OPT_SPEC', value='PRES')`
4. Pressure: `set_value(session, aspen_path='\Data\Blocks\COMP1\Input\PRES', value='30', unit='atm')`
5. Efficiency: `set_value(session, aspen_path='\Data\Blocks\COMP1\Input\SEFF', value='0.75')`

## Gotchas

- **Must set OPT_SPEC before setting the outlet value** — without it, the block stays incomplete.
- Efficiency type must match compressor TYPE:
  - ISENTROPIC → `SEFF`
  - POLYTROPIC / POSITIVE-DIS → `PEFF`
- Setting the wrong efficiency type leaves the block incomplete.
- For Pump (liquid), use the Pump block instead.
