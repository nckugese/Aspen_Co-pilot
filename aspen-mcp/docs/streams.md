# Streams

## Stream Types

| Type | Description | Typical Use |
|------|------------|-------------|
| MATERIAL | Material flow (mass/mole/volume) | Process streams |
| HEAT | Energy stream | Heat integration |
| WORK | Work/power stream | Compressor/pump work |

## Key Input Paths (MATERIAL stream)

| Path | Type | Description |
|------|------|-------------|
| `\Data\Streams\{name}\Input\TEMP\MIXED` | float | Temperature |
| `\Data\Streams\{name}\Input\PRES\MIXED` | float | Pressure |
| `\Data\Streams\{name}\Input\TOTFLOW\MIXED` | float | Total flow rate |
| `\Data\Streams\{name}\Input\FLOW\MIXED\{comp}` | float | Component flow |
| `\Data\Streams\{name}\Input\MOLE-FRAC\MIXED\{comp}` | float | Mole fraction |
| `\Data\Streams\{name}\Input\MASS-FRAC\MIXED\{comp}` | float | Mass fraction |
| `\Data\Streams\{name}\Input\FLOWBASE\MIXED` | string | Flow basis: `MOLE`, `MASS`, `VOLUME` |

## Output Paths (after simulation)

| Path | Type | Description |
|------|------|-------------|
| `\Data\Streams\{name}\Output\TOT_FLOW\MIXED` | float | Total flow (output) |
| `\Data\Streams\{name}\Output\TEMP\MIXED` | float | Temperature (output) |
| `\Data\Streams\{name}\Output\PRES\MIXED` | float | Pressure (output) |
| `\Data\Streams\{name}\Output\MOLEFLOW\MIXED\{comp}` | float | Component mole flow (output) |
| `\Data\Streams\{name}\Output\MOLEFRAC\MIXED\{comp}` | float | Component mole fraction (output) |

## Typical Setup Steps

1. Place: `place_stream(session, 'FEED', 'MATERIAL')`
2. Temperature: `set_value(session, stream_name='FEED', stream_type='MATERIAL', property_name='temperature', value='25', unit='C')`
3. Pressure: `set_value(session, stream_name='FEED', stream_type='MATERIAL', property_name='pressure', value='1', unit='atm')`
4. Total flow: `set_value(session, stream_name='FEED', stream_type='MATERIAL', property_name='total_flow', value='100', unit='kmol/hr')`
5. Component flow: `set_value(session, stream_name='FEED', stream_type='MATERIAL', property_name='component_flow', value='50', unit='kmol/hr', extra_params={"component": "ETHANOL"})`

Or with direct paths:
```
set_value(session, aspen_path='\Data\Streams\FEED\Input\TEMP\MIXED', value='25', unit='C')
set_value(session, aspen_path='\Data\Streams\FEED\Input\FLOW\MIXED\ETHANOL', value='50', unit='kmol/hr')
```

## Gotchas

- Input paths have `\MIXED` suffix (substream name).
- `FLOWBASE` change via COM does NOT auto-switch `TOTFLOW` units — change flow basis in the GUI.
- When specifying individual component flows, total flow must match (or use mole/mass fractions instead).
