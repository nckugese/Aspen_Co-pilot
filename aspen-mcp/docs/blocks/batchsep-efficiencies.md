# BatchSep efficiencies

Paths are under `\Data\Blocks\{name}\` (Efficiencies form).

| Path | Type | Purpose |
|---|---|---|
| `Input\EFFMETHOD` | `IDEAL`, `COMPONENT` | Equilibrium stages, or efficiencies per stage and component |
| `Input\EFFTYPE` | `MURPHREE`, `VAPORIZATION` | Murphree or vaporization efficiency |
| `Input\COMP_EFF\{stage}\{comp}` | real | Efficiency of a component on a stage; every stage and component has an entry, 1 by default |

Murphree 0.7 lowers the distillate purity against the ideal base run.
