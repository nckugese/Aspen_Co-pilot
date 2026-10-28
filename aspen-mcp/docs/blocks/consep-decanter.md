# ConSep decanter

Paths are under `\Data\Blocks\{name}\`. A decanter splits the condensed top vapor into two liquids; for a heterogeneous azeotrope such as water with benzene.

`DECANTER` is refused unless `IPHASE` is `VLL`: set `IPHASE` first.

## Input | Specifications (decanter)

| Path | Type | Purpose |
|---|---|---|
| `Input\SPECTYPE` | `SP-REFLUX`, `VAPOR-COMP`, `REFLUX-COMP` | Decanter spec: reflux from the first liquid only, or a set top-vapor or reflux composition |
| `Input\COMP` | component | Component the decanter spec is about |
| `Input\VALUE` | fraction | Its mole fraction in the top vapor or in the reflux |

`SP-REFLUX` sends back none of the second liquid (`FRACTION\4` = 0).

`VAPOR-COMP` sets the column top vapor (`X9`), `REFLUX-COMP` the reflux (`X8`).

## Results (after a run)

Composition vectors are indexed by selected component (1-3).

| Path | Type | Purpose |
|---|---|---|
| `Output\X5\{i}` | fraction | First liquid |
| `Output\X6\{i}` | fraction | Second liquid |
| `Output\X8\{i}` | fraction | Reflux |
| `Output\X9\{i}` | fraction | Column top vapor (`X4` the vapor in equilibrium with the liquids) |
| `Output\FRACTION\3` | fraction | Share of the first liquid refluxed (`FRACTION\4` the second) |
