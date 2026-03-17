# RGibbs (Gibbs Free Energy Minimization Reactor)

Equilibrium reactor that minimizes Gibbs free energy. No reaction stoichiometry needed.

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

## When to Use

- Chemical equilibrium calculations without knowing reactions.
- Combustion, gasification, steam reforming.
- Phase equilibrium with simultaneous chemical equilibrium.

## Gotchas

- Does NOT require reaction definitions — it finds equilibrium automatically.
- May need to restrict products if unrealistic species appear in results.
- Computationally more expensive than RStoic or REquil.
