# HeatX

Two-stream heat exchanger, shortcut or detailed shell-and-tube. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `H(IN)`, `H(OUT)` hot side, `C(IN)`, `C(OUT)` cold side; all four need a stream, except on a side a utility replaces ([heatx-utilities.md](heatx-utilities.md)).

`DESIGN`, `RATING` and `MAX-FOULING` need `SPEC` and `VALUE`; `SIMULATION` needs `AREA` (or `UA`) instead.

`VALUE` has no unit of its own: it is read in the unit `SPECUN` names, whose default depends on `SPEC` (`C` for a temperature spec, `cal/sec` for `DUTY`). `set_value` with `unit=` on `VALUE` puts that unit (e.g. `F`, `kW`) in `SPECUN`; a unit `SPECUN` does not take (`kW` on a temperature) is refused and nothing is written.

`VFRAC-HOT` and `VFRAC-COLD` take a vapor fraction; `SPECUN` is not used for them, so write `VALUE` without `unit=`.

In `SIMULATION`, `UA` works only with `U_OPTION=CONSTANT`; with the default `PHASE` the block ends with zero duty (BLKSTAT 2).

`PRES_HOT` / `PRES_COLD`: 0 keeps the inlet pressure, a negative value is a drop, a positive one the outlet pressure.

Geometry fields (`LENGTH`, `PITCH`, ...) matter only with `MODE=DETAILED`; a shortcut block runs without them.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\MODE` | `SHORTCUT`, `DETAILED` | Model: shortcut (U and LMTD), or detailed shell-and-tube ([heatx-geometry.md](heatx-geometry.md)) |
| `Input\PROGRAM_MODE` | `DESIGN`, `RATING`, `SIMULATION`, `MAX-FOULING` | Calculation: size the area, check a given area, solve outlets from the area, or find the fouling the area allows |
| `Input\SPEC` | `T-HOT`, `T-COLD`, `DUTY`, `MIN-OUT-TAPP`, `DELT-HOT`, `DELT-COLD`, `DEGSUP-COLD`, `DEGSUB-HOT`, `VFRAC-HOT`, `VFRAC-COLD`, `DECR-HOT`, `INCR-COLD` | What `VALUE` fixes: an outlet temperature, the duty, the outlet approach, a temperature change, superheat or subcooling, an outlet vapor fraction |
| `Input\VALUE` | real (unit from `SPECUN`) | Value of the spec |
| `Input\SPECUN` | unit name | Unit `VALUE` is read in |
| `Input\TYPE` | `COUNTERCURRENT`, `COCURRENT`, `MULTIPASS`, `CROSSFLOW`, `CALC-NSHELLS` | Flow arrangement; `CALC-NSHELLS` finds the number of multipass shells in series |
| `Input\NUM_SHELLS` | real | Shell count for `TYPE=MULTIPASS` |
| `Input\AREA` | AREA | Heat-transfer area (`RATING`, `SIMULATION`, `MAX-FOULING`) |
| `Input\UA` | UA | U times area, in place of `AREA` (a block takes one of the two) |
| `Input\MIN_TAPP` | DELTA-T | Smallest temperature approach allowed |
| `Input\PRES_HOT` | PRESSURE | Hot outlet pressure, or drop when negative |
| `Input\PRES_COLD` | PRESSURE | Cold outlet pressure, or drop when negative |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\HX_DUTY` | ENTHALPY-FLO | Duty |
| `Output\HOT_TEMP` | TEMPERATURE | Hot outlet temperature |
| `Output\COLD_TEMP` | TEMPERATURE | Cold outlet temperature |
| `Output\HX_AREAC2` | AREA | Area the duty requires |
| `Output\HX_AREAP` | AREA | Area given or used |
| `Output\HX_OVERD` | percent | Over-design of the given area (`RATING`) |
| `Output\HX_UA` | UA | U times area |
| `Output\HX_DTLM` | DELTA-T | LMTD after correction |
| `Output\HX_FMTD` | ratio | LMTD correction factor |
| `Output\HX_NSHLS` | count | Shells in series |

More: [U methods and film coefficients](heatx-u-methods.md), [shell and tube geometry](heatx-geometry.md), [baffles and nozzles](heatx-baffles-nozzles.md), [LMTD correction](heatx-lmtd.md), [pressure drop](heatx-pressure-drop.md), [convergence and report](heatx-convergence.md), [T-Q curve and zones](heatx-tq-curve.md), [heating curves](heatx-hcurves.md), [per-side thermodynamics and phases](heatx-properties.md), [utility on one side](heatx-utilities.md).

Not covered: Dynamics (Aspen Dynamics only); EDR options, EDR file, EDR property curves, EDR browser and results (shell-and-tube, air cooler, plate), Convert to rigorous, Size exchanger, Rigorous sizing, Specify geometry (EDR rigorous models: need an EDR input file; `MODE` keeps `SHORTCUT` or `DETAILED` when another code is written); EO options (equation-oriented options, not checked); User subroutines (user Fortran subroutines); TASC geometry (older TASC geometry fields, not checked).
