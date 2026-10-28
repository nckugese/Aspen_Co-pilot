# Dryer: drying curve

How fast the solids give up moisture (convective, spray and contact types): a constant rate down to the critical moisture, then a falling rate to the equilibrium moisture. Paths are under `\Data\Blocks\{name}\`; basics in [dryer.md](dryer.md).

A long enough dryer brings the product down to `EQUIL_SMC` (0.005 in the base convective run).

1. `DATA`: insert one unlabelled row per point into `SMC` (`insert_row`); `RATE` gets the same rows.
2. Write `SMC\#n` and `RATE\#n` per point, from 0 to 1 in both.

## Input | Drying Curve

| Path | Type | Purpose |
|---|---|---|
| `Input\CRIT_SMC` | ratio | Moisture where the falling-rate period starts |
| `Input\EQUIL_SMC` | ratio | Moisture in equilibrium with the gas, the lowest reachable |
| `Input\CURVE_SMC_B` | `DRY`, `WET` | `CRIT_SMC` and `EQUIL_SMC` per kg of dry (default) or wet solids |
| `Input\CURVE_MODEL` | `FUNCTION`, `DATA` | Falling-rate period as a function or as a table |
| `Input\SHAPE_FACTOR` | real | `FUNCTION`: shape of the falling-rate curve |
| `Input\SMC\{row}` | fraction | `DATA`: normalized moisture of point n (0 at equilibrium, 1 at critical) |
| `Input\RATE\{row}` | fraction | `DATA`: drying rate of point n relative to the constant rate |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\CRIT_MO_CONT` | ratio | Critical moisture used |
| `Output\EQU_MO_CONT` | ratio | Equilibrium moisture used |
