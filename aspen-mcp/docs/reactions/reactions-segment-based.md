# Segment-based reaction set (SEGMENT-BAS)

Power-law reactions written on the segments of a polymer, which change its units without chain-growth kinetics. Rules shared by all reaction sets: [reactions.md](reactions.md).

Root: `\Data\Reactions\Reactions\{id}`

Species are component IDs; the polymer is a component of `TYPE` `POLYMER`, each segment one of `TYPE` `SEGMENT`.

## Setup

1. `add_reaction_set` with `reaction_type='SEGMENT-BAS'`, then `Input\POLYMER`.
2. Reactants of reaction `n`: `insert_row` + `set_label` `n` on `Input\COEF`, then one labelled row per reactant (label = component ID) on `Input\COEF\{n}`; `EXPONENT\{n}` and `PRE_EXP\{n}` appear with them.
3. Products: the same on `Input\COEF1` and `Input\COEF1\{n}`.
4. Put the set's ID on the reactor's `RXN_ID` row.

A reactant coefficient is stored negative: `1` written on `COEF\{n}\{comp}` reads back `-1`.

## Reactions

| Path | Type | Purpose |
|---|---|---|
| `Input\COEF\{n}\{comp}` | real | Reactant coefficient (kept negative) |
| `Input\COEF1\{n}\{product}` | real | Product coefficient |
| `Input\EXPONENT\{n}\{comp}` | real | Order in that reactant |
| `Input\PRE_EXP\{n}` | INVERSE-TIME | Pre-exponential factor |
| `Input\ACT_ENERGY\{n}` | MOLE-ENTHALP | Activation energy |
| `Input\REF_TEMP\{n}` | TEMPERATURE | Reference temperature of the rate constant |

## Options

| Path | Type | Purpose |
|---|---|---|
| `Input\POLYMER` | ID | Polymer whose segments react |
| `Input\PHASE` | `L`, `L1`, `L2`, `LS`, `V` | Phase the reactions run in |
| `Input\CBASIS` | `MOLARITY`, `MOLALITY`, `MOLEFRAC`, `MASSFRAC`, `MASSCONC` | Concentration basis of the rate law |

## Results (product stream, after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{prod}\Output\MASSFLOW\MIXED\{poly}` | MASS-FLOW | Polymer made |
| `\Data\Streams\{prod}\Output\MASSFLOW\MIXED\{comp}` | MASS-FLOW | Monomer left |

Not covered: Site assignment (site activities (`OPT_ASSIGN` `ASSIGN`), not checked); Reaction flags (per-component include flags, not checked); Subroutines (user Fortran subroutines).
