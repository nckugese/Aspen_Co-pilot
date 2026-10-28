# Compr

Compressor or turbine for a gas: one stage, given an outlet spec and an efficiency, or performance curves. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `P(OUT)` product; `WS(IN)`, `WD(OUT)`, `WS(OUT)` take work streams and may stay empty. A work stream on `WS(OUT)` carries the net work (its `Output\POWER_OUT`).

To run it needs `TYPE`, `OPT_SPEC` and the field `OPT_SPEC` names; `MODEL_TYPE` starts as `COMPRESSOR`.

Writing `PRES` (or `DELP`, `PRATIO`, `POWER`) does not set `OPT_SPEC`: the block stays incomplete until `OPT_SPEC` names it. The order of the two writes does not matter.

The isentropic types (`ISENTROPIC`, `GPSA-ISENTROP`, `ASME-ISENTROP`) read `SEFF`; the polytropic and positive-displacement types read `PEFF`. The other field is ignored, and with the matching one blank the block runs at 0.72.

`MODEL_TYPE=TURBINE`: `PRES` below the inlet, `PRATIO` below 1, `DELP` and `POWER` as positive numbers (the drop and the power delivered; negative ones are refused). `WNET` then comes out negative.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\MODEL_TYPE` | `COMPRESSOR`, `TURBINE` | Compressor, or turbine (expander) |
| `Input\TYPE` | `ISENTROPIC`, `GPSA-ISENTROP`, `ASME-ISENTROP`, `GPSA-POLYTROP`, `ASME-POLYTROP`, `INT-POLYTROP`, `POS-DISP`, `INT-POS-DISP` | Model: isentropic (plain, GPSA or ASME method), polytropic (GPSA, ASME, or piecewise integration [compr-integration.md](compr-integration.md)), positive displacement (plain or integrated) |
| `Input\OPT_SPEC` | `PRES`, `DELP`, `PRATIO`, `POWER`, `USE-CURVE` | Outlet spec: pressure, pressure change, ratio, power, or performance curves ([compr-curves.md](compr-curves.md)) |
| `Input\PRES` | PRESSURE | Outlet pressure |
| `Input\DELP` | PDROP | Pressure rise (compressor) or drop (turbine) |
| `Input\PRATIO` | ratio | Outlet over inlet pressure |
| `Input\POWER` | POWER | Power taken (compressor) or delivered (turbine) |
| `Input\SEFF` | fraction | Isentropic efficiency |
| `Input\PEFF` | fraction | Polytropic efficiency |
| `Input\MEFF` | fraction | Mechanical efficiency: brake power = fluid power / `MEFF` |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\WNET` | POWER | Net work (negative for a turbine) |
| `Output\IND_POWER` | POWER | Power given to the fluid |
| `Output\BRAKE_POWER` | POWER | Shaft (brake) power |
| `Output\POWER_ISEN` | POWER | Isentropic power |
| `Output\POC` | PRESSURE | Outlet pressure |
| `Output\PRES_RATIO` | ratio | Pressure ratio |
| `Output\TOC` | TEMPERATURE | Outlet temperature |
| `Output\TOS` | TEMPERATURE | Isentropic outlet temperature |
| `Output\EPC` | fraction | Efficiency used (isentropic or polytropic) |
| `Output\HEAD_CAL` | HEAD | Head developed |
| `Output\FEED_VFLOW` | VOLUME-FLOW | Inlet volume flow |
| `Output\Z_OUT` | ratio | Outlet compressibility factor |

More: [calculation options](compr-calculation.md), [piecewise integration](compr-integration.md), [power loss](compr-power-loss.md), [convergence](compr-convergence.md), [performance curves](compr-curves.md), [curve scaling and fitting](compr-curve-adjust.md).

Not covered: Dynamics (Aspen Dynamics only); User subroutines (user Fortran subroutines); Surge curve (surge-line coefficients: written and run, but the reported surge flow did not change); Extended polynomial and user curves (`OPT_CFORMAT` codes `EXT-POLY` and `USER-CURVES`, not checked); Free water (`BLKOPFREWAT`, not checked); Design-condition correction (`OPT_DESIGN`) (`PIN_DESIGN` and `TIN_DESIGN` read back but never reach the run: `CORR-FACTOR` stops on missing design conditions, `CORR-FLOW` and `DIMENSIONLES` give an efficiency above 1).
