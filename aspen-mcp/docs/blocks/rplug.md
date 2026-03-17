# RPlug (Plug Flow Reactor)

Tubular plug flow reactor with kinetics. Requires a reaction set.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| C | IN | Coolant in |
| P | OUT | Product |
| C | OUT | Coolant out |
| HS | OUT | Heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Inlet temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Operating pressure |
| `\Data\Blocks\{name}\Input\LENGTH` | float | Reactor length |
| `\Data\Blocks\{name}\Input\DIAM` | float | Reactor diameter |
| `\Data\Blocks\{name}\Input\NTUBES` | int | Number of tubes |
| `\Data\Blocks\{name}\Input\RXN_ID` | table | Selected reaction set(s) |

## Assigning a Reaction Set

Same pattern as RCSTR:
```
list_elements(session, '\Data\Blocks\R1\Input\RXN_ID')
→ [0] #0 = None

set_value(session, aspen_path='\Data\Blocks\R1\Input\RXN_ID\#0', value='RXN1')
```

## Gotchas

- Must specify reactor geometry (length + diameter or volume).
- Requires kinetic reaction set (POWERLAW or LHHW).
- Has coolant ports for heat exchange — can model co-current or counter-current cooling.
