# Electrolyzer: efficiencies and crossover (shortcut model)

Specification | Specifications fields read by `MODEL_TYPE` `SHORTCUT`. Paths are under `\Data\Blocks\{name}\`; setup in [electrolyzer.md](electrolyzer.md).

## Efficiencies

| Path | Type | Purpose |
|---|---|---|
| `Input\EFF_TYPE` | `HHV`, `LHV`, `VOLTAGE` | Basis of the efficiency that sets the cell voltage |
| `Input\HHV_EFF_VAL` | fraction | Efficiency on the higher heating value (`HHV`) |
| `Input\LHV_EFF_VAL` | fraction | Efficiency on the lower heating value (`LHV`) |
| `Input\VLT_EFF_VAL` | fraction | Voltage efficiency (`VOLTAGE`) |
| `Input\FRD_EFF_VAL` | fraction | Faraday (current) efficiency |

## Crossover through the membrane

| Path | Type | Purpose |
|---|---|---|
| `Input\H_CROSS_METH` | `H-CROSS-FRAC`, `H-PERM-CONS` | How hydrogen leaking to the anode is set: as a share, or by a rate constant |
| `Input\H2_CROSS_F` | fraction | Share of the hydrogen that crosses to the anode (`H-CROSS-FRAC`) |
| `Input\H2_PERM_K` | MOLE-FLOW | Permeation constant (`H-PERM-CONS`) |
| `Input\W_CROSS_METH` | `W-CROSS-FRAC`, `W-PERM-COEF` | Water crossover: a fraction, or a drag coefficient |
| `Input\H2O_CROSS_F` | fraction | Share of the water that crosses to the cathode (`W-CROSS-FRAC`) |
| `Input\H2O_PERM_C` | number | Water molecules carried per proton (`W-PERM-COEF`, default 6) |

| Path | Type | Purpose |
|---|---|---|
| `Output\ELEC-POWER` | ELEC-POWER | Power drawn |
