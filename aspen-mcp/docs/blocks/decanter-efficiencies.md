# Decanter: efficiencies

Per-component factors on the liquid-liquid split. Paths are under `\Data\Blocks\{name}\`.

## Input | Efficiency

| Path | Type | Purpose |
|---|---|---|
| `Input\EFFIC\{comp}` | number | Efficiency of the component (default 1); every component has an entry |

`EFFIC` `WATER` 0.9 brought `B_K` of water to 0.9 times its value at 1.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\CEFF\{comp}` | number | Efficiency used per component |
| `Output\B_K\{comp}` | number | Distribution ratio after the efficiency |
