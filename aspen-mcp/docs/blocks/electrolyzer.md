# Electrolyzer

Water electrolysis stack, alkaline or PEM: water in, a hydrogen-rich cathode product and an oxygen-rich anode product out. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `FA(IN)` anode feed, `FC(IN)` cathode feed, `FS(IN)` feed split over both sides, `PA(OUT)` anode product (oxygen), `PC(OUT)` cathode product (hydrogen), `HS(IN)`/`HS(OUT)` heat streams, `PS(IN)` power stream.

Setup used in the runs: components H2O, H2 and O2 (water, hydrogen, oxygen) with NRTL; water fed at 60 C and 1 atm.

To run it needs `NSTACKS`, `NCELLS`, a feed, both outlets, the value `PI_SPEC` selects and the one `TQ_SPEC` selects (`HEAT_DUTY` 0 for adiabatic).

`ALKALINE` takes one feed on `FS(IN)` or two on `FA(IN)` and `FC(IN)`; `FA(IN)` alone leaves the input incomplete. `PEM` takes `FA(IN)` or `FS(IN)`.

## Setup | Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\CELL_TYPE` | `ALKALINE`, `PEM` | Cell technology |
| `Input\MODEL_TYPE` | `SHORTCUT`, `RIGOROUS`, `CURVES` | Calculation: from efficiencies, from cell geometry and kinetics ([rigorous](electrolyzer-rigorous.md)), or from voltage curves ([curves](electrolyzer-curves.md)) |
| `Input\MODEL_SCOPE` | `STACK`, `MODULE` | The stack alone, or a module with set product purities ([module](electrolyzer-module.md)) |
| `Input\FEED_LOC\{stream}` | `ANODE`, `STACK`, `CATHODE` | Side a feed enters; filled in from the feed's port |

## Specification | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\NSTACKS` | int | Stacks in parallel |
| `Input\NCELLS` | int | Cells per stack |
| `Input\PI_SPEC` | `POWER`, `CURRENT`, `CURRENTDNSTY`, `H2-PROD-RATE` | Which electrical quantity is fixed |
| `Input\POWER` | ELEC-POWER | Total power (`POWER`) |
| `Input\CURRENT` | CURRENT | Total current (`CURRENT`) |
| `Input\CURR_DENSITY` | CURRENT-DENS | Current density (`CURRENTDNSTY`), with `ACTUAL_AREA` |
| `Input\ACTUAL_AREA` | AREA | Active area of one cell |
| `Input\H2_PROD_RATE` | MASS-FLOW | Hydrogen made (`H2-PROD-RATE`) |
| `Input\TQ_SPEC` | `DUTY`, `TEMPERATURE` | Energy spec |
| `Input\HEAT_DUTY` | ENTHALPY-FLO | Heat added (`DUTY`) |
| `Input\TEMPERATURE` | TEMPERATURE | Operating temperature (`TEMPERATURE`) |
| `Input\PDROP_SPEC` | `FIXED`, `CELL-PRESS`, `CORRELATION` | Outlet pressure per side, one pressure for the cell, or a drop correlation (rigorous model only) |
| `Input\PRES_ANODE` | PRESSURE | Anode side (`FIXED`) |
| `Input\PRES_CATH` | PRESSURE | Cathode side (`FIXED`) |
| `Input\PRES_CELL` | PRESSURE | Both sides (`CELL-PRESS`) |

Pressure values above 0 are the outlet pressure; 0 or below is a drop from the feed pressure.

`CELL-PRESS` gives both outlets the `PRES_CELL` pressure.

Voltages, efficiencies and production rates appear only on the GUI Results form, with no tree path: read the hydrogen made from the `PC(OUT)` stream.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\ELEC-POWER` | ELEC-POWER | Power drawn |
| `Output\DUTY` | ENTHALPY-FLO | Heat duty (with `TQ_SPEC` `TEMPERATURE`) |

More: [efficiencies and crossover](electrolyzer-shortcut.md), [rigorous model](electrolyzer-rigorous.md), [performance curves](electrolyzer-curves.md), [module](electrolyzer-module.md).

Not covered: Module product-flow specs SPC-H2-FLOW / SPC-O2-FLOW (the input stayed incomplete in every combination tried); Results form values (voltages, efficiencies, rates) (GUI only, no tree path).
