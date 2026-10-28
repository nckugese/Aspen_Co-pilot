# Emulsion reaction set (EMULSION)

Free-radical polymerization in polymer particles dispersed in water: species, reaction rows that each run in the particles or the water, and particle data. Rules shared by all reaction sets: [reactions.md](reactions.md).

Root: `\Data\Reactions\Reactions\{id}`

Species and reactants are component IDs; the polymer is a component of `TYPE` `POLYMER`, each segment one of `TYPE` `SEGMENT`.

## Setup

1. `add_reaction_set` with `reaction_type='EMULSION'`.
2. Species: `insert_row` on a list (`Input\INITIATOR`, `Input\EMULSIFIER`, ...), then `set_value` on `Input\<list>\#0`; `DISPERSANT` and `POLYMER` take one ID each.
3. Segment of each monomer: `insert_row` on `Input\R_SEG`, `set_label` with the monomer ID, `set_value` with the segment.
4. Reactions: `insert_row` on `Input\EMRTYPE` once per reaction; `EMPHASE`, `CID1`, `EMPRE_EXP` and the other row keywords get the same rows.
5. Particle data keyed by component: `insert_row` + `set_label` with the emulsifier on `Input\AREA` and `Input\CMC_CONC`, with each monomer or agent on `Input\KLL`, then `set_value`.
6. Put the set's ID on the reactor's `RXN_ID` row.

## Species

| Path | Type | Purpose |
|---|---|---|
| `Input\INITIATOR\{row}` | ID | Initiator |
| `Input\MONOMER\{row}` | ID | Monomer |
| `Input\CHAINTAG\{row}` | ID | Chain-transfer agent |
| `Input\EMULSIFIER\{row}` | ID | Emulsifier (forms the micelles) |
| `Input\INHIBITOR\{row}` | ID | Inhibitor |
| `Input\CATALYST\{row}` | ID | Catalyst |
| `Input\ACTIVATOR\{row}` | ID | Activator |
| `Input\DISPERSANT` | ID | Continuous phase (water) |
| `Input\POLYMER` | ID | Polymer component |
| `Input\R_SEG\{monomer}` | ID | Segment a monomer becomes |

## Reactions (one row each)

| Path | Type | Purpose |
|---|---|---|
| `Input\EMRTYPE\{row}` | `INIT-DEC`, `INIT-CAT`, `INIT-ACT`, `PROPAGATION`, `CHAT-AGENT`, `CHAT-MON`, `CHAT-POL`, `TERM-DIS`, `TERM-COMB`, `INHIBITION`, `REDUCTION`, `OXIDATION` | Reaction type |
| `Input\EMPHASE\{row}` | `DISPERSANT` | Where the row runs: in the particles or in the water |
| `Input\CID1\{row}` | ID | First species (initiator, monomer of the radical end, ...) |
| `Input\CID2\{row}` | ID | Second species |
| `Input\EMPRE_EXP\{row}` | INVERSE-TIME | Pre-exponential factor |
| `Input\EMACT_ENERGY\{row}` | MOLE-ENTHALP | Activation energy |
| `Input\EMACT_VOL\{row}` | MOLE-VOLUME | Activation volume |
| `Input\EFFIC\{row}` | fraction | Initiator efficiency (initiation rows) |
| `Input\NRADS\{row}` | int | Radicals one initiator molecule gives |
| `Input\INCRX\{row}` | `YES`, `NO` | Use the row |

## Particles

| Path | Type | Purpose |
|---|---|---|
| `Input\AREA\{emulsifier}` | MOLE-AREA | Surface one kmol of emulsifier covers |
| `Input\CMC_CONC\{emulsifier}` | MOLE-CONC | Concentration above which the emulsifier forms micelles |
| `Input\AMPRE_EXP` | INVERSE-TIME | Radical capture by micelles: pre-exponential factor |
| `Input\AMACT_ENERGY` | MOLE-ENTHALP | Its activation energy |
| `Input\APPRE_EXP` | INVERSE-TIME | Radical capture by particles: pre-exponential factor |
| `Input\APACT_ENERGY` | MOLE-ENTHALP | Its activation energy |
| `Input\DPPRE_EXP` | INVERSE-TIME | Radical escape from particles: pre-exponential factor |

## Monomer split between phases

| Path | Type | Purpose |
|---|---|---|
| `Input\PHAPP` | `COEFF` | Split by fixed partition coefficients or by a phase calculation |
| `Input\KLL\{comp}` | real | Split ratio of a component between particles and water (`COEFF`) |
| `Input\KBASIS` | `MONOMER`, `AQUEOUS` | Phase the coefficients are taken against |

## Results (product stream, after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{prod}\Output\MASSFLOW\MIXED\{poly}` | MASS-FLOW | Polymer made |
| `\Data\Streams\{prod}\Output\COMP_ATTR\MWN\MWN\{poly}\MIXED` | real | Molar mass, number mean |

Not covered: Gel effect, Gel effect (second form) (gel-effect corrections, not checked); Options (moment, steady-state and flash options, not checked); Rigorous phase split (`PHAPP` `RIGOROUS`) (did not converge).
