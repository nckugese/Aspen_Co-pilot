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
| `\Data\Streams\{name}\Input\FLOW\MIXED\{comp}` | float | Component flow (primary way to set composition) |
| `\Data\Streams\{name}\Input\FLOWBASE` | string | Flow basis: `MOLE`, `MASS`, `VOLUME` |

## Composition Basis

The `FLOW\MIXED` node has a `BASIS` attribute that controls how component values are interpreted.
Default is `MOLE-FLOW`. To switch to mole fractions:

```
set_node_attribute(session, aspen_path='\Data\Streams\FEED\Input\FLOW\MIXED', attribute='BASIS', value='MOLE-FRAC')
```

Valid BASIS values: `MOLE-FLOW`, `MASS-FLOW`, `MOLE-FRAC`, `MASS-FRAC`

After changing BASIS, set `FLOW\MIXED\{comp}` with the corresponding values (fractions or flows).

> **Note:** There are no separate `MOLE-FRAC\MIXED\{comp}` or `MASS-FRAC\MIXED\{comp}` nodes. Composition is always set via `FLOW\MIXED\{comp}` — the BASIS attribute determines the interpretation.

## Output Paths (after simulation)

| Path | Type | Description |
|------|------|-------------|
| `\Data\Streams\{name}\Output\TOT_FLOW` | float | Total flow (output) |
| `\Data\Streams\{name}\Output\RES_TEMP` | float | Temperature (output) |
| `\Data\Streams\{name}\Output\RES_PRES` | float | Pressure (output) |
| `\Data\Streams\{name}\Output\MOLEFLOW\MIXED\{comp}` | float | Component mole flow (output) |
| `\Data\Streams\{name}\Output\MOLEFRAC\MIXED\{comp}` | float | Component mole fraction (output) |

## Typical Setup Steps

1. Place: `place_stream(session, 'FEED', 'MATERIAL')`
2. Temperature: `set_value(session, stream_name='FEED', stream_type='MATERIAL', property_name='temperature', value='25', unit='C')`
3. Pressure: `set_value(session, stream_name='FEED', stream_type='MATERIAL', property_name='pressure', value='1', unit='atm')`
4. Total flow: `set_value(session, stream_name='FEED', stream_type='MATERIAL', property_name='total_flow', value='100', unit='kmol/hr')`
5. Component flow: `set_value(session, stream_name='FEED', stream_type='MATERIAL', property_name='component_flow', value='50', unit='kmol/hr', extra_params={"component": "ETHANOL"})`

Or with direct paths (component flow):
```
set_value(session, aspen_path='\Data\Streams\FEED\Input\TEMP\MIXED', value='25', unit='C')
set_value(session, aspen_path='\Data\Streams\FEED\Input\FLOW\MIXED\ETHANOL', value='50', unit='kmol/hr')
```

Or with mole fractions:
```
set_node_attribute(session, aspen_path='\Data\Streams\FEED\Input\FLOW\MIXED', attribute='BASIS', value='MOLE-FRAC')
set_value(session, aspen_path='\Data\Streams\FEED\Input\TOTFLOW\MIXED', value='100', unit='kmol/hr')
set_value(session, aspen_path='\Data\Streams\FEED\Input\FLOW\MIXED\ETHANOL', value='0.5')
set_value(session, aspen_path='\Data\Streams\FEED\Input\FLOW\MIXED\WATER', value='0.3')
```

## Gotchas

- Input paths have `\MIXED` suffix (substream name).
- To change composition basis, use `set_node_attribute` on `FLOW\MIXED` with attribute `BASIS` — do NOT use the `FLOWBASE` or `BASIS` leaf nodes directly (they will throw `AE_UNDERSPEC` errors).
- When using mole/mass fractions, still need to set `TOTFLOW` for total flow rate.
