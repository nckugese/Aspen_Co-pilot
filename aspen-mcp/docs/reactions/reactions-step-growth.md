# Step-growth reaction set (STEP-GROWTH)

Condensation polymerization: the model builds the reactions itself from functional groups and the species that carry them; you give the groups, the counts and the rate constants. Rules shared by all reaction sets: [reactions.md](reactions.md).

Root: `\Data\Reactions\Reactions\{id}`

Species are component IDs; the polymer is a component of `TYPE` `POLYMER`, the repeat and end units components of `TYPE` `SEGMENT`.

## Setup

1. `add_reaction_set` with `reaction_type='STEP-GROWTH'`, then `Input\POLYMER`.
2. Functional groups: `insert_row` + `set_label` with a group ID on `Input\TYPE`, then `set_value` with its type (no GUI form shows `TYPE`).
3. Group counts: `Input\NUMBER` has two dimensions; label species on dimension 0 and groups on dimension 1 (`insert_row` and `set_label` with `dimension=1`), then `set_value` on `NUMBER\{species}\{group}`.
4. Rate constants: `insert_row` + `set_label` `n` on `Input\SGPRE_EXP`; `SGACT_ENERGY` gets the same label. Reaction sets: label `n` on `Input\NUCLEOPHILE`; it makes `RC_SETS\{n}`, which takes one `insert_row` per rate-constant set used.
5. Put the set's ID on the reactor's `RXN_ID` row.

## Groups and species

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE\{group}` | `E-GRP`, `N-GRP`, `EE-GRP`, `NN-GRP`, `EN-GRP`, `EX-GRP`, `NX-GRP`, `BOND` | Group type: E electrophilic, N nucleophilic; a doubled code is a repeat unit holding two |
| `Input\NUMBER\{species}\{group}` | int | How many of the group one species carries |
| `Input\POLYMER` | ID | Polymer component |

## Rate constants and reaction sets

| Path | Type | Purpose |
|---|---|---|
| `Input\SGPRE_EXP\{n}` | INVERSE-TIME | Rate constant `{n}` (its factor before the exponential) |
| `Input\SGACT_ENERGY\{n}` | MOLE-ENTHALP | Its activation energy |
| `Input\NUCLEOPHILE\{n}` | ID | Nucleophile species of reaction set `{n}` |
| `Input\RC_SETS\{n}\{row}` | string | Rate-constant set number the reaction set uses |

## Options

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASE` | `L`, `V`, `L1`, `L2` | Phase the reactions run in |
| `Input\CONC_BASIS` | `MOL/L`, `MMOL/L`, `MOL/KG`, `MMOL/KG` | Concentration basis of the rate laws |

## Results (product stream, after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{prod}\Output\MASSFLOW\MIXED\{poly}` | MASS-FLOW | Polymer made |
| `\Data\Streams\{prod}\Output\MASSFLOW\MIXED\H2O` | MASS-FLOW | Water released |
| `\Data\Streams\{prod}\Output\COMP_ATTR\MWN\MWN\{poly}\MIXED` | real | Molar mass, number mean |
| `\Data\Streams\{prod}\Output\COMP_ATTR\DPN\DPN\{poly}\MIXED` | real | Number-average chain length |

Not covered: User reaction entry, User reaction list, User rate-constant assignment, User reaction stoichiometry, User rate constants (user reactions, not checked); Subroutines (user Fortran subroutines).
