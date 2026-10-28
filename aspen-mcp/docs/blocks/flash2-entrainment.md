# Flash2: entrainment

Liquid or solids carried over into the vapor outlet. Paths are under `\Data\Blocks\{name}\`.

## Input | Entrainment

| Path | Type | Purpose |
|---|---|---|
| `Input\ENTRN` | fraction | Share of the equilibrium liquid sent into the vapor outlet |
| `Input\VAPOR\{substream}` | fraction | Share of a solid substream (e.g. `CISOLID`) sent into the vapor outlet; the rest leaves with the liquid |

The flash itself is unchanged: the vapor outlet gets the equilibrium vapor plus `ENTRN` of the liquid.

`VAPOR\CISOLID` 0.2 sent 2 of the 10 kmol/hr of calcite to `V(OUT)` and 8 to `L(OUT)`.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_VFRAC` | fraction | Vapor fraction of the flash (before entrainment) |
