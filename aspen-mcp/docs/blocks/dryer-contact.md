# Dryer: contact

`DRYER_TYPE` = `CONTACT`: heat reaches the solids through a heated surface; a gas inlet is optional. Paths are under `\Data\Blocks\{name}\`; basics in [dryer.md](dryer.md).

Without `GAS(IN)` the evaporated water leaves alone through `EXHAUST(OUT)`.

`OPT_HEATTRAN` `EQUIL` only runs without a gas inlet; with one the block stops with an error.

## Input | Specifications and Mass/Heat Transfer

| Path | Type | Purpose |
|---|---|---|
| `Input\LENGTH` | LENGTH | Dryer length |
| `Input\SURFACE_AREA` | AREA | Area where gas and solids exchange heat |
| `Input\OPT_INDHEAT` | `INDHEAT1`, `INDHEAT2` | Wall heat as a duty, or from wall temperature, area and coefficient |
| `Input\INDIRECTHEAT` | ENTHALPY-FLO | `INDHEAT1`: heat through the wall |
| `Input\INDHEATAREA` | AREA | `INDHEAT2`: heated wall area |
| `Input\INDHEATTEMP` | TEMPERATURE | `INDHEAT2`: wall temperature |
| `Input\INDHTRANSWS` | HEAT-TRANS-C | `INDHEAT2`: wall-to-solids coefficient |
| `Input\OPT_HEATTRAN` | `COEFF`, `EQUIL` | Gas-solids heat transfer by `ALPHAG`, or gas and solids at equilibrium |
| `Input\ALPHAG` | HEAT-TRANS-C | `COEFF`: the gas-to-solids value (W/sqm-K) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EVAP_RATE2` | MASS-FLOW | Moisture evaporated |
| `Output\OUSOL_MO_CON` | ratio | Product moisture, kg per kg dry solids |
| `Output\EXGT` | TEMPERATURE | Exhaust temperature |
