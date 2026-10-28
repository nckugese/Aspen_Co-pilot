# RGibbs

Equilibrium reactor: the outlet is the composition with the lowest Gibbs energy at the set conditions, so no reactions or kinetics are entered. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `P(OUT)` products (one stream per phase found), `HS(IN)` heat stream in, `HS(OUT)` heat stream out.

To run it needs `PRES` plus `TEMP` (or `DUTY` with `SPEC_OPT` `DUTY`); every component counts as a possible product unless the products list says otherwise ([rgibbs-products.md](rgibbs-products.md)).

Leave `PRES` empty and the run still starts, but the block ends in error (BLKSTAT 1).

Leave `TEMP` empty under `SPEC_OPT` `TEMP` and the block solves adiabatic: no duty is reported and the outlet cools below the 500 C feed as the reforming takes up heat.

`PRES` of zero or less is a drop from the feed pressure: -0.2 bar on a 1 atm feed gives 0.813 bar.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_CHEMEQ` | `PHASE-ONLY`, `PHASE-CHEM`, `RESTRICT`, `CALC-TAPP` | What is solved: phases only, phases plus chemical equilibrium (default), restricted equilibrium, or the approach found from `TEMP` + `DUTY` ([rgibbs-restricted.md](rgibbs-restricted.md)) |
| `Input\SPEC_OPT` | `TEMP`, `DUTY` | Thermal spec: outlet temperature or heat duty |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\PRES` | PRESSURE | Outlet pressure; zero or less is a drop |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty (`SPEC_OPT` `DUTY`, or beside `TEMP` under `CALC-TAPP`) |
| `Input\NPHASE` | int | Most fluid phases searched; 2 or more lets a liquid form beside the vapor |
| `Input\VAPOR` | `YES`, `NO` | Whether a vapor phase may appear among the products |

`PHASE-ONLY` leaves the feed unreacted: 10 kmol/hr methane in, 10 out, no hydrogen.

`SPEC_OPT` `DUTY` with 600 kW gives an outlet between the feed temperature and 800 C.

`CALC-TAPP` takes `TEMP` and `DUTY` together and stops the reaction short of equilibrium so the duty is met: at 800 C and 600 kW, far more methane is left than at full equilibrium.

With two `P(OUT)` streams, `NPHASE` 2 at 60 C puts the gas in the first and the condensed water in the second.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\B_VFRAC` | fraction | Share of the outlet that is gas |
| `Output\NPHASE_OUT` | int | Fluid phases found |
| `Output\MOLEFLMX\{phase}` | MOLE-FLOW | Flow of each phase found (labels such as `VAPOR`) |
| `Output\PLACED-STRM\{phase}` | ID | Outlet stream that took that phase |

More: [products, inerts and outlet streams](rgibbs-products.md), [restricted equilibrium](rgibbs-restricted.md), [atom matrix, convergence and estimates](rgibbs-convergence.md).

Not covered: Dynamics (Aspen Dynamics only); Solid solutions (SOLID, NPSOL) (not checked: with SOLID YES and no solid-solution phase data the input stays incomplete); Hydrate check (HYDRATE_CHEC) (salt hydrates of electrolyte systems, not checked).
