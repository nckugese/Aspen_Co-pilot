# RPlug (Plug Flow Reactor)

Tubular plug flow reactor with rigorous kinetics. Requires an external reaction set (POWERLAW or LHHW).

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| C | IN | Coolant in |
| P | OUT | Product |
| C | OUT | Coolant out |
| HS | OUT | Heat stream out |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\NTUBE` | int | Number of tubes |
| `\Data\Blocks\{name}\Input\LENGTH` | float | Reactor length |
| `\Data\Blocks\{name}\Input\DIAM` | float | Reactor diameter |
| `\Data\Blocks\{name}\Input\PDROP` | float | Pressure drop at reactor inlet |
| `\Data\Blocks\{name}\Input\RXN_ID` | table | Selected reaction set(s) |

> Reactor geometry (LENGTH + DIAM) is required. NTUBE defaults to 1 if not set.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\QCALC` | float | Heat duty |
| `\Data\Blocks\{name}\Output\TMIN` | float | Minimum reactor temperature |
| `\Data\Blocks\{name}\Output\TMAX` | float | Maximum reactor temperature |
| `\Data\Blocks\{name}\Output\RES_TIME` | float | Residence time |
| `\Data\Blocks\{name}\Output\COOLANT_TIN` | float | Thermal fluid inlet temperature |
| `\Data\Blocks\{name}\Output\COOLANT_VIN` | float | Thermal fluid inlet vapor fraction |

## Assigning a Reaction Set

Same pattern as RCSTR:
```
list_elements(session, '\Data\Blocks\R1\Input\RXN_ID')
→ [0] #0 = None

set_value(session, aspen_path='\Data\Blocks\R1\Input\RXN_ID\#0', value='RXN1')
```

## Typical Setup

1. Place: `place_block(session, 'R1', 'RPlug')`
2. Length: `set_value(session, aspen_path='\Data\Blocks\R1\Input\LENGTH', value='5', unit='meter')`
3. Diameter: `set_value(session, aspen_path='\Data\Blocks\R1\Input\DIAM', value='0.1', unit='meter')`
4. Create reaction set: `add_reaction_set(session, 'RXN1', 'POWERLAW')`
5. Add reaction: `add_reaction(session, 'RXN1', 1, reactants={...}, products={...}, phase='V')`
6. Set kinetics: `set_value(session, aspen_path='\Data\Reactions\Reactions\RXN1\Input\PRE_EXP\1', value='3.6e15')`
7. Assign to block: `set_value(session, aspen_path='\Data\Blocks\R1\Input\RXN_ID\#0', value='RXN1')`

## Gotchas

- Must specify reactor geometry (length + diameter).
- Requires kinetic reaction set (POWERLAW or LHHW).
- Has coolant ports for heat exchange — can model co-current or counter-current cooling.
