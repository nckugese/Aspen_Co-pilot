# RStoic (Stoichiometric Reactor)

Reactor with known stoichiometry and fractional conversion. No kinetics needed — specify reactions and conversions directly via internal tables.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| P | OUT | Product |
| HS | OUT | Heat stream out |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Specified temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Specified pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Specified heat duty |
| `\Data\Blocks\{name}\Input\VFRAC` | float | Specified vapor fraction (0–1) |
| `\Data\Blocks\{name}\Input\SPEC_OPT` | string | Specification option: `TP` (temp+pres), `TD` (temp+duty), etc. |
| `\Data\Blocks\{name}\Input\STOIC(rxn,substream,comp)` | float | Stoichiometric coefficient |
| `\Data\Blocks\{name}\Input\CONV(rxn,substream,comp)` | float | Fractional conversion of key component |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\B_TEMP` | float | Outlet temperature |
| `\Data\Blocks\{name}\Output\B_PRES` | float | Outlet pressure |
| `\Data\Blocks\{name}\Output\QCALC` | float | Calculated heat duty |
| `\Data\Blocks\{name}\Output\QNET` | float | Net heat duty |
| `\Data\Blocks\{name}\Output\B_VFRAC` | float | Calculated vapor fraction |
| `\Data\Blocks\{name}\Output\LIQ_RATIO` | float | First liquid / total liquid ratio |

## Stoichiometry Setup

RStoic uses its own internal stoichiometry tables, NOT external reaction sets. The STOIC and CONV nodes are indexed tables. Use `list_elements` to explore their structure after setting temperature/pressure.

## Typical Setup

1. Place: `place_block(session, 'R1', 'RStoic')`
2. Temperature: `set_value(session, aspen_path='\Data\Blocks\R1\Input\TEMP', value='150', unit='C')`
3. Pressure: `set_value(session, aspen_path='\Data\Blocks\R1\Input\PRES', value='5', unit='atm')`
4. Set stoichiometry and conversion via internal table nodes.

## Gotchas

- RStoic does **NOT** use the `add_reaction_set` / `add_reaction` workflow — those are for RCSTR/RPlug.
- Stoichiometry and conversion are set via internal table nodes, not reaction sets.
- Use `list_node_children` and `list_elements` to discover the correct paths.
