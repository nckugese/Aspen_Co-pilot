# Decanter

Splits a liquid feed into two liquid phases at a set temperature or duty; no vapor outlet. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: feed on `F(IN)`; the liquids leave on `L1(OUT)` and `L2(OUT)`; heat streams on `HS(IN)` / `HS(OUT)`.

To run it needs `PRES` plus `TEMP`, or `SPEC_OPT` `DUTY` plus `DUTY`; a fresh block has `SPEC_OPT` `TEMP`.

Without a key component the block assigns the liquids itself; for an organic-water feed it can put the organic liquid on `L1(OUT)` and the water-rich one on `L2(OUT)`. Set a key component when the assignment matters.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_OPT` | `TEMP`, `DUTY` | Second spec next to pressure: temperature or heat duty |
| `Input\PRES` | PRESSURE | Pressure; a negative value is a drop from the feed pressure |
| `Input\TEMP` | TEMPERATURE | Temperature (`TEMP`) |
| `Input\DUTY` | ENTHALPY-FLO | Heat added (`DUTY`); 0 is adiabatic |

`DUTY` 0 gives `QCALC` 0 and a temperature found by the block.

`PRES` -0.1 bar gives an outlet 0.1 bar below the feed.

| Path | Type | Purpose |
|---|---|---|
| `Input\L2_COMPS\{row}` | component ID | Key components of the second liquid: `insert_row`, then write the ID; the liquid richest in them leaves on `L2(OUT)` |
| `Input\L2_CUTOFF` | fraction | Threshold on the key components' fraction; enterable once a key is listed |

`L2_COMPS` `BENZENE` sends the organic liquid to `L2(OUT)`; `WATER` keeps the water-rich one there.

A feed that stays one liquid at the block's `TEMP` and `PRES` (benzene / toluene without water) ends with `BLKSTAT` 2: all of it leaves on `L1(OUT)`, `L2(OUT)` is empty and `LIQ_RATIO` is 1, with or without `L2_COMPS` / `L2_CUTOFF`. A Flash3 at the same conditions gives that split with `BLKSTAT` 0, so it shows beforehand whether a second liquid forms.

Heat streams:

1. Place a stream of type `HEAT`, connect it to `HS(IN)` and write its duty in `\Data\Streams\{heat}\Input\DUTY`; with `PRES` the block is then complete.

The heat stream's duty is used in place of `TEMP` or `DUTY`, while `SPEC_OPT` keeps its code: `TEMP` 25 C plus 10 kW on `HS(IN)` gives the same result as `DUTY` 10 kW.

A heat stream on `HS(OUT)` carries the block duty with the sign reversed.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty (`QNET2`: net duty, 0 when a duty is given) |
| `Output\LIQ_RATIO` | fraction | First liquid over total liquid (molar) |
| `Output\X1\{comp}` | mole fraction | First-liquid composition (`X2`: second liquid) |
| `Output\B_K\{comp}` | number | Ratio of the component's mole fractions in the two liquids |

`LIQ_RATIO` is L1 over L1 + L2 and `B_K` is x(L2) / x(L1), both molar; with `TEMP` given `QNET2` equals `QCALC`.

More: [flash options and free water](decanter-flash-options.md), [efficiencies](decanter-efficiencies.md), [KLL correlation and phase properties](decanter-phase-properties.md), [solid entrainment](decanter-entrainment.md), [heating curves](decanter-hcurves.md).

Not covered: Dynamics (Aspen Dynamics only); KLL subroutine (KLL_CORR SUBROUTINE) (user Fortran subroutine).
