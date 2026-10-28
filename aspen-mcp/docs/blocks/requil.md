# REquil

Equilibrium reactor for reactions you list: each reaches chemical equilibrium (or a set approach to it) together with phase equilibrium, the constants coming from the components' Gibbs energies. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `V(OUT)` vapor, `L(OUT)` liquid, `HS(IN)` heat stream in, `HS(OUT)` heat stream out.

To run it needs the two values `SPEC_OPT` names (`TEMP` and `PRES` by default) and at least one reaction; at 70 C and 1 atm the equimolar feed ends 78 % converted, all liquid.

With no reaction row the input stays incomplete and the run does not start.

`PRES` of zero or less is a drop from the feed pressure: -0.1 bar on a 1 atm feed gives 0.913 bar.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_OPT` | `TP`, `TV`, `PV`, `TD`, `PD`, `TQ`, `PQ` | Which pair is given: T, P, vapor fraction (V), duty (D), or the duty of a heat stream fed in (Q) |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\PRES` | PRESSURE | Outlet pressure; zero or less is a drop |
| `Input\VFRAC` | fraction | Outlet vapor fraction (`TV`, `PV`) |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty (`TD`, `PD`) |
| `Input\NPHASE` | `1`, `2` | Phases in the flash: one, or vapor and liquid (default 2) |
| `Input\PHASE` | `V`, `L` | The single phase when `NPHASE` is 1 |

`TD` solves the pressure, and it may converge only with the reaction on a fixed extent (`OPT_EXT_DELT` `EXTENT`, [requil-reactions.md](requil-reactions.md)); with the reaction at equilibrium the pressure search can run down to 0.1 bar and fail (`EQULK2.14`).

`TQ` and `PQ` take the duty from a heat stream on `HS(IN)`: a 3.9 kW stream gives `QCALC` 3.9 kW.

Under `TQ` the `TEMP` written is not kept: the run holds the feed pressure (or `PRES` when set) and solves the temperature from the heat stream, the same result as `PQ`.

## Input | Reactions

1. `insert_row` on `Input\COEF` labelled with the reaction number (1, 2, ...); rows of `COEF1`, `OPT_EXT_DELT`, `DELT`, `EXT_SPEC`, `EXT_EST` and `TAPP_CHK` with that number come with it.
2. For each reactant `insert_row` on `Input\COEF\{n}` labelled with the component and write its coefficient; for each product the same on `Input\COEF1\{n}`. There is no substream level in these paths.

| Path | Type | Purpose |
|---|---|---|
| `Input\COEF\{n}\{comp}` | real | Reactant coefficient, stored negative |

A positive number written to `COEF` is stored with a minus sign.

| Path | Type | Purpose |
|---|---|---|
| `Input\COEF1\{n}\{comp}` | real | Product coefficient; a negative one is refused |

A new reaction starts as `OPT_EXT_DELT` `DELT` with `DELT` 0: full equilibrium at the outlet temperature ([requil-reactions.md](requil-reactions.md) for approaches and fixed extents).

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
| `Output\B_VFRAC` | fraction | Outlet vapor fraction |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\QNET` | ENTHALPY-FLO | Net duty, after any heat stream |
| `Output\K\{n}` | real | Equilibrium constant of reaction n |
| `Output\TKEQ\{n}` | TEMPERATURE | Temperature at which that constant was taken |

More: [reaction extents and approach checks](requil-reactions.md), [convergence and entrainment](requil-convergence.md).

Not covered: Solid entrainment (VAPOR), Outlet particle size distribution (OPT_PSD) (needs a solid substream, not checked); Phase S (pure salts) (electrolyte systems only, not checked).
