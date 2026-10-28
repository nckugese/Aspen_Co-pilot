# RGibbs restricted equilibrium

Paths are under `\Data\Blocks\{name}\`. Set `OPT_CHEMEQ` `RESTRICT`, then choose how with `RESTR_TYPE`.

| Path | Type | Purpose |
|---|---|---|
| `Input\RESTR_TYPE` | `SYSTEM`, `INDIVIDUAL` | One temperature approach for the whole system, or a spec per reaction |

## Whole system

| Path | Type | Purpose |
|---|---|---|
| `Input\TAPP` | DELTA-T | Temperature approach: equilibrium taken at `TEMP` + `TAPP` |

Only the composition moves: `TAPP` -100 C at 800 C gives the 700 C equilibrium outlet while the outlet stays at 800 C.

## Individual reactions

1. `insert_row` on `Input\COEF` labelled with the reaction number (1, 2, ...); rows of `COEF1`, `OPT_EXT_DELT`, `DELT` and `EXT_SPEC` with that number appear with it.
2. For each reactant `insert_row` on `Input\COEF\{n}` labelled with the component and write its coefficient; for each product the same on `Input\COEF1\{n}`.
3. Set `OPT_EXT_DELT\{n}`, then `DELT\{n}` or `EXT_SPEC\{n}`.

| Path | Type | Purpose |
|---|---|---|
| `Input\COEF\{n}\{comp}` | real | Reactant coefficient, stored negative |

A positive number written to `COEF` is stored with a minus sign.

| Path | Type | Purpose |
|---|---|---|
| `Input\COEF1\{n}\{comp}` | real | Product coefficient, positive |
| `Input\OPT_EXT_DELT\{n}` | `DELT`, `EXTENT` | Reaction n held by a temperature approach, or by a fixed extent |
| `Input\DELT\{n}` | DELTA-T | Temperature approach of reaction n |
| `Input\EXT_SPEC\{n}` | MOLE-FLOW | Reaction n held at this many kmol/hr of turnover |

Only the listed reactions run: with reforming fixed at 3 kmol/hr, a feed of 10 kmol/hr methane keeps 7.

With a fixed extent, list a full independent set (species minus elements, e.g. 5 - 3 = 2 for steam reforming with water-gas shift); one reaction short of that set ends in a severe error.

## Calculated approach (`CALC-TAPP`)

`OPT_CHEMEQ` `CALC-TAPP` needs `TEMP` and `DUTY`; RGibbs finds the approach itself.

| Path | Type | Purpose |
|---|---|---|
| `Input\TAPP_EST` | DELTA-T | Starting guess for that approach |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\K\{n}` | real | Equilibrium constant of reaction n at the outlet |
