# Extract

Rigorous countercurrent liquid-liquid extractor: a feed liquid meets a solvent over a set of stages, with no vapor phase. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `TF(IN)` feed to the top stage, `BF(IN)` feed to the bottom stage, `SF(IN)` side feeds, `TP(OUT)` top product, `BP(OUT)` bottom product, `SP(OUT)` side products, `HS(IN)` / `HS(OUT)` heat streams ([extract-heat-streams.md](extract-heat-streams.md)), `PS(OUT)` pseudo streams.

The 1st liquid runs down from stage 1 and the 2nd liquid up from the last stage: `TP(OUT)` leaves stage 1 as 2nd liquid and `BP(OUT)` leaves stage `NSTAGE` as 1st liquid. Stages and phases of `TF`, `BF`, `TP` and `BP` fill in by themselves.

To run it needs `NSTAGE`, a stage pressure and a key component for each liquid; `ADIABATIC` (the default) and `DUTY` also need a `TEMP_EST` row (one stage is enough), `TEMP` does not. Anything missing stops the run before it starts: no `BLKSTAT` and no Run-Status are written.

## Setup | Specs

| Path | Type | Purpose |
|---|---|---|
| `Input\NSTAGE` | int | Stage count; stage 1 is the top |
| `Input\OPT_THERMAL` | `ADIABATIC`, `TEMP`, `DUTY` | Thermal spec of the stages |

Switching to `TEMP` is refused while `TEMP_EST` rows exist: `remove_row` them first.

| Path | Type | Purpose |
|---|---|---|
| `Input\TSPEC_TEMP\{stage}` | TEMPERATURE | Stage temperature (`TEMP`) |
| `Input\HEATER_DUTY\{stage}` | ENTHALPY-FLO | Heat added on a stage, negative removes (`DUTY`) |
| `Input\TEMP_EST\{stage}` | TEMPERATURE | Temperature estimate (`ADIABATIC`, `DUTY`) |

## Setup | Key Components (unlabelled rows `#0`, `#1`, ...)

| Path | Type | Purpose |
|---|---|---|
| `Input\COMP1_LIST\{row}` | component | Component that marks the 1st liquid |
| `Input\COMP2_LIST\{row}` | component | Component that marks the 2nd liquid |

## Setup | Streams

| Path | Type | Purpose |
|---|---|---|
| `Input\FEED_STAGE\{stream}` | int | Stage a feed enters (a side feed on `SF(IN)` needs one) |
| `Input\PROD_STAGE\{stream}` | int | Stage a side product leaves |
| `Input\PROD_PHASE\{stream}` | `L1`, `L2` | Liquid a side product draws |
| `Input\PROD_FLOW\{stream}` | MOLE-FLOW | Side product flow |

A flow on the top or bottom product is refused; only side products take one.

## Setup | Pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\STAGE_PRES\{stage}` | PRESSURE | Stage pressure |

A single row on stage 1 sets the pressure of every stage.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TOP_TEMP` | TEMPERATURE | Top stage temperature |
| `Output\BOTTOM_TEMP` | TEMPERATURE | Bottom stage temperature |
| `Output\TOP_L2FLOW` | MOLE-FLOW | 2nd liquid leaving the top stage |
| `Output\BOT_L1FLOW` | MOLE-FLOW | 1st liquid leaving the bottom stage |
| `Output\B_TEMP\{stage}` | TEMPERATURE | Stage temperature |
| `Output\L1_FLOW\{stage}` | MOLE-FLOW | 1st liquid flow leaving a stage |
| `Output\X1\{stage}\{comp}` | fraction | Mole fraction in the 1st liquid on a stage |
| `Output\X2\{stage}\{comp}` | fraction | Mole fraction in the 2nd liquid on a stage |
| `Output\DUTY\{stage}` | ENTHALPY-FLO | Stage duty |

More: [K-values](extract-kll.md), [efficiencies](extract-efficiencies.md), [heat streams](extract-heat-streams.md), [convergence and estimates](extract-convergence.md), [report and pseudo streams](extract-report.md).

Not covered: Dynamics (Aspen Dynamics only); K-value subroutine (OPT_KLL=SUBROUTINE) (user Fortran subroutine).
