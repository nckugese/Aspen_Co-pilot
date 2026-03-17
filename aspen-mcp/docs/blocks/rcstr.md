# RCSTR (Continuous Stirred Tank Reactor)

Kinetic reactor with perfect mixing. Requires a reaction set with kinetic parameters.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| VI | IN | Vapor inlet |
| P | OUT | Product |
| HS | OUT | Heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Reactor temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Reactor pressure |
| `\Data\Blocks\{name}\Input\VOLUME` | float | Reactor volume (when SPEC_TYPE=TOT-VOL) |
| `\Data\Blocks\{name}\Input\RES_TIME` | float | Residence time (when SPEC_TYPE=RES-TIME) |
| `\Data\Blocks\{name}\Input\SPEC_OPT` | string | Thermal spec: `TEMP`, `DUTY`, `VFRAC` |
| `\Data\Blocks\{name}\Input\SPEC_TYPE` | string | Size spec: `TOT-VOL`, `RES-TIME` |
| `\Data\Blocks\{name}\Input\PHASE` | string | Valid phases: `V`, `L`, `V-L` |
| `\Data\Blocks\{name}\Input\NPHASE` | int | Number of phases (1 or 2) |
| `\Data\Blocks\{name}\Input\RXN_ID` | table | Selected reaction set(s) |
| `\Data\Blocks\{name}\Input\KINETICS` | string | Primary kinetics set name |

## Assigning a Reaction Set

The RXN_ID node has a pre-existing empty element. Use `list_elements` to see it, then `set_value` to assign:

```
list_elements(session, '\Data\Blocks\R1\Input\RXN_ID')
→ [0] #0 = None

set_value(session, aspen_path='\Data\Blocks\R1\Input\RXN_ID\#0', value='CRACKING')
```

## Typical Setup Steps

1. Place block: `place_block(session, 'R1', 'RCSTR')`
2. Set temperature: `set_value(session, aspen_path='\Data\Blocks\R1\Input\TEMP', value='850', unit='C')`
3. Set pressure: `set_value(session, aspen_path='\Data\Blocks\R1\Input\PRES', value='1.7', unit='atm')`
4. Set volume: `set_value(session, aspen_path='\Data\Blocks\R1\Input\VOLUME', value='10')`
5. Create reaction set: `add_reaction_set(session, 'RXN1', 'POWERLAW')`
6. Add reaction: `add_reaction(session, 'RXN1', 1, reactants={...}, products={...}, phase='V')`
7. Set kinetics: `set_value(session, aspen_path='\Data\Reactions\Reactions\RXN1\Input\PRE_EXP\1', value='3.6e15')`
8. Assign to block: `set_value(session, aspen_path='\Data\Blocks\R1\Input\RXN_ID\#0', value='RXN1')`

## Gotchas

- Must set VOLUME or RES_TIME (not VOL — VOL is a different parameter)
- PHASE defaults to `V` (vapor only). Set to `V-L` for two-phase reactions.
- NPHASE must match PHASE setting (1 for V or L, 2 for V-L).
