# RStoic (Stoichiometric Reactor)

Reactor with known stoichiometry and conversion. No kinetics needed — specify fractional conversion directly.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| P | OUT | Product |
| HS | OUT | Heat stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TEMP` | float | Reactor temperature |
| `\Data\Blocks\{name}\Input\PRES` | float | Reactor pressure |
| `\Data\Blocks\{name}\Input\DUTY` | float | Heat duty |
| `\Data\Blocks\{name}\Input\VFRAC` | float | Vapor fraction |
| `\Data\Blocks\{name}\Input\SPEC_OPT` | string | `TP` (temp+pres), `TD` (temp+duty), etc. |
| `\Data\Blocks\{name}\Input\STOIC(rxn,substream,comp)` | float | Stoichiometric coefficient |
| `\Data\Blocks\{name}\Input\CONV(rxn,substream,comp)` | float | Fractional conversion of key component |

## Stoichiometry Setup

RStoic uses its own internal stoichiometry tables, NOT external reaction sets. The STOIC and CONV nodes are indexed tables. Use `list_elements` to explore their structure after setting temperature/pressure.

## Gotchas

- RStoic does NOT use the `add_reaction_set` / `add_reaction` workflow — those are for RCSTR/RPlug.
- Stoichiometry and conversion are set via internal table nodes, not reaction sets.
- Use `list_node_children` and `list_elements` to discover the correct paths.
