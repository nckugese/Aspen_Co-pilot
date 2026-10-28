# BatchSep

Batch distillation: a heated pot under a column with a condenser and distillate receivers, run as a sequence of operating steps over time. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `In_Charge(IN)` the batch charge, `In_F(IN)` feeds during the batch, `Out_D(OUT)` distillate receivers, `Out_SD(OUT)` side-draw receivers, `Out_B(OUT)` the pot.

A run needs the pot size (`D` and `L`); without them the block fails.

The charge is the `In_Charge(IN)` flow taken over one hour: 100 kmol/hr charges 100 kmol, 200 kmol/hr charges 200 kmol.

At the end `Out_D(OUT)` carries what distillate receiver 1 holds and `Out_B(OUT)` what is left in the pot; their flows add up to the charge.

Without an operating step only the initial state is computed and nothing is distilled.

## Setup (Configuration, Reflux, Pot geometry, Pressure and Streams sheets)

| Path | Type | Purpose |
|---|---|---|
| `Input\NSTAGE` | int | Stages, condenser = 1 and pot = last |
| `Input\CONDENSER` | `TOTAL`, `PARTIAL`, `PARTIAL2` | Total, partial, or partial plus a second condenser ([batchsep-condenser.md](batchsep-condenser.md)) |
| `Input\SPECTYPE` | `RR`, `MOLE-D`, `MASS-D`, `MOLE-L`, `MASS-L` | Second column spec: reflux ratio, distillate or reflux rate (mass codes take `FMRDIST1`, `FMRREFLUX1`) |
| `Input\REFLUXRATIO1` | ratio | Reflux ratio (`RR`) |
| `Input\FRDIST1` | MOLE-FLOW | Distillate rate (`MOLE-D`) |
| `Input\FRREFLUX1` | MOLE-FLOW | Reflux rate (`MOLE-L`) |
| `Input\GEOMETRYSPEC` | `DL`, `DV`, `LV` | Pot size from two of diameter `D`, length `L`, volume `V` |
| `Input\D` | LENGTH | Pot diameter |
| `Input\L` | LENGTH | Pot length |
| `Input\COND_PRES` | PRESSURE | Condenser pressure |
| `Input\PDROPSPEC` | `COLPDROP`, `STGPDROP`, `POTPRES` | Column pressure from a column drop, a drop per stage (`DPSTAGE`) or the pot pressure (`POTPRESSURE`) |
| `Input\DPCOL` | PDROP | Pressure drop over the column (`COLPDROP`) |
| `Input\FEED_STAGE\{stream}` | int | Stage of a stream on `In_F(IN)` |

## Initial conditions and heating

| Path | Type | Purpose |
|---|---|---|
| `Input\INITIALCOND` | `TOTAL`, `CHARGE`, `EMPTY` | Start at total reflux, with the charge in the pot under an inert, or empty ([batchsep-initial-final.md](batchsep-initial-final.md)) |
| `Input\P_MINITIAL` | MOLES | Pot holdup at the start (`TOTAL`); left empty it acts as 10 kmol |
| `Input\JH_OPT` | `DUTY`, `TEMP`, `LMTD` | Pot heating given as a duty, a medium temperature, or a medium inlet temperature and flow ([batchsep-heat-transfer.md](batchsep-heat-transfer.md)) |
| `Input\JH_DUTY` | ENTHALPY-FLO | Jacket duty (`DUTY`) |

## Operating Steps

1. `add_element` on `Subobjects\Operating Steps` with a name, e.g. `DISTIL`; its fields are keyed by that name.
2. Set `OPS_DURATION\{step}`; changes and triggers per step: [batchsep-operating-steps.md](batchsep-operating-steps.md).

Heat reaches the pot only through a step: give each step a changed variable for the heating (location `JKHEATING`, parameter `DUTY`, value `OPS_DUTYVAL`). With `JH_DUTY` alone nothing boils.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\MOLEFLMX\MIXED` | MOLE-FLOW | Distillate collected (the stream on `Out_D(OUT)`) |
| `\Data\Streams\{stream}\Output\MOLEFRAC\MIXED\{comp}` | fraction | Its composition |
| `\Data\Streams\B1\Output\MOLEFLMX\MIXED` | MOLE-FLOW | Pot contents at the end (stream on `Out_B(OUT)`) |

More: [condenser and reflux drum](batchsep-condenser.md), [holdups](batchsep-holdups.md), [initial and final conditions](batchsep-initial-final.md), [operating steps](batchsep-operating-steps.md), [heat transfer](batchsep-heat-transfer.md), [controllers](batchsep-controllers.md), [internals](batchsep-internals.md), [efficiencies](batchsep-efficiencies.md), [convergence](batchsep-convergence.md).

Not covered: Flowsheet options (flowsheet-level flags such as free water and pause, not checked); Pot only (CONFIG POT) (BLKSTAT 0 but nothing leaves the pot); Steam heating (JH_OPT STEAM) (BLKSTAT 0 but the pot is not heated); Shortcut heat transfer (H_TRANS_MODE SHORTCUT) (did not converge: under-specified); Charge over a time (CHARGESPEC CHARGE) (did not converge); Controller mode changed in a step (CONTROLLER / MODE) (the batch never enters its step); Reactions, Three phases (VALIDPHASES), Cooling by jacket, coils or exchanger (JC_, CC_, XC_), Process-side film coefficients, Initial receiver contents, Side draws and their receivers, Time-profile plots (not checked).
