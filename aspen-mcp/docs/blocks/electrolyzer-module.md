# Electrolyzer: module scope

`MODEL_SCOPE` `MODULE` adds product gas cleanup to the stack: the two products leave at the purities you set. Paths are under `\Data\Blocks\{name}\`; setup in [electrolyzer.md](electrolyzer.md).

Only `ALKALINE` cells take `MODULE`, and all four compositions (hydrogen and oxygen in each outlet) must be given before the input is complete.

Fix the temperature (`TQ_SPEC` `TEMPERATURE`): an adiabatic module failed to find its outlet temperature.

## Specification | Module

| Path | Type | Purpose |
|---|---|---|
| `Input\CALC_MAKEUP` | `YES`, `NO` | Makeup mode: `YES` with an electrical spec, `NO` without one |

With `YES` the feed stream's water flow is recalculated to match the production.

With `NO` nearly all the fed water is split and the power is a result.

| Path | Type | Purpose |
|---|---|---|
| `Input\MODULE_BASIS` | `MOLE`, `MASS` | Basis of the product compositions |
| `Input\H2_FRAC_MOL\{stream}` | fraction | Hydrogen in an outlet, one entry per outlet stream (`H2_FRAC_MAS` on a mass basis) |
| `Input\O2_FRAC_MOL\{stream}` | fraction | Oxygen in an outlet (`O2_FRAC_MAS`) |
| `Input\PROD_FL_OPT` | `CALC-PROD-FL` | Product flows computed from the compositions |

| Path | Type | Purpose |
|---|---|---|
| `Output\ELEC-POWER` | ELEC-POWER | Power drawn |
