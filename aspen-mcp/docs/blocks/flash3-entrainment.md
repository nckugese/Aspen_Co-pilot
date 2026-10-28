# Flash3: entrainment

Liquid carried over into the vapor outlet. Paths are under `\Data\Blocks\{name}\`.

## Input | Entrainment

| Path | Type | Purpose |
|---|---|---|
| `Input\ENTR1` | fraction | Share of the first liquid sent into the vapor outlet |
| `Input\ENTR2` | fraction | Share of the second liquid sent into the vapor outlet |

The flash itself is unchanged: the vapor outlet gets the equilibrium vapor plus `ENTR1` of the first liquid and `ENTR2` of the second.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_VFRAC` | fraction | Vapor fraction of the flash (before entrainment) |
