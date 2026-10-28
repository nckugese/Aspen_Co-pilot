# Reactions

A reaction set is a named group of numbered reactions, each with its stoichiometry and its kinetics or equilibrium, that a reactor or a column uses by the set's ID.

Root: `\Data\Reactions\Reactions\{id}`

In the paths `{rxn}` is the reaction number, `{comp}` a reactant and `{prod}` a product ID.

Set types (the type passed to `add_reaction_set`): `POWERLAW`, `LHHW`, `GENERAL`, `REAC-DIST` (RadFrac only), `USER`, `USERACM`, `IONIC`, and the polymer types `EMULSION`, `FREE-RAD`, `SEGMENT-BAS`, `STEP-GROWTH`, `ZIEGLER-NAT`.

There is no `EQUILIBRIUM` set type; an equilibrium reaction is one reaction of a set ([reactions-equilibrium.md](reactions-equilibrium.md)).

## Build a set

1. `add_reaction_set(name, type)` creates `\Data\Reactions\Reactions\{id}`.
2. `add_reaction(set, n, reactants, products, phase, exponents)` creates reaction `n` as `KINETIC`, with its phase, `COEF` / `COEF1` rows and `EXPONENT` rows (by default the reactant coefficients).
3. Give the kinetics: `PRE_EXP` and `ACT_ENERGY` (below), or the type's own fields.
4. Point the reactor at the set: `insert_row` on the block's `Input\RXN_ID`, then `set_value` `Input\RXN_ID\#0` = the set's ID (RCSTR, RPlug). A RadFrac takes a `REAC-DIST` set ([reactions-reac-dist.md](reactions-reac-dist.md)).

Coefficients go in positive on both sides; a reactant coefficient is kept negative (2 reads back -2), and a negative product coefficient is refused.

Reactions are numbered 1, 2, ... inside a set. A reverse reaction is a second reaction with the sides swapped.

A kinetic reaction whose `ACT_ENERGY` is blank does not react, and the run gives no message; enter 0 for a rate with no temperature dependence.

`remove_reaction(set, n)` deletes reaction `n` with its rows; `remove_reaction_set(set)` deletes the set.

## Stoichiometry

| Path | Type | Purpose |
|---|---|---|
| `Input\REACTYPE\{rxn}` | `KINETIC`, `EQUIL` | Rate law, or at equilibrium |
| `Input\PHASE\{rxn}` | `L`, `V` | Phase the reaction runs in |
| `Input\COEF\{rxn}\{comp}\MIXED` | real | Reactant coefficient (kept negative) |
| `Input\COEF1\{rxn}\{prod}\MIXED` | real | Product coefficient |
| `Input\EXPONENT\{rxn}\{comp}\MIXED` | real | Reactant exponent in the rate (kinetic only) |

## Kinetics

| Path | Type | Purpose |
|---|---|---|
| `Input\PRE_EXP\{rxn}` | real | Factor k in front of the exponential, in SI units ([reactions-powerlaw.md](reactions-powerlaw.md)) |
| `Input\ACT_ENERGY\{rxn}` | MOLE-ENTHALP | Activation energy E (give `unit=`, e.g. kJ/mol) |

More: [POWERLAW](reactions-powerlaw.md), [equilibrium reactions](reactions-equilibrium.md), [LHHW](reactions-lhhw.md), [GENERAL](reactions-general.md), [REAC-DIST](reactions-reac-dist.md); polymer types: [EMULSION](reactions-emulsion.md), [FREE-RAD](reactions-free-rad.md), [SEGMENT-BAS](reactions-segment-based.md), [STEP-GROWTH](reactions-step-growth.md), [ZIEGLER-NAT](reactions-ziegler-natta.md). Reactors: [RCSTR](../blocks/rcstr.md), [RPlug](../blocks/rplug.md), [RBatch](../blocks/rbatch.md), [BatchOp](../blocks/batchop-reactions.md), [RadFrac](../blocks/radfrac-reactions.md).

Not covered: LHHW catalyst activity, GENERAL catalyst activity, GENERAL class CUSTOM (own rate expression), GENERAL class GLHHW, REAC-DIST new-reaction sheet, REAC-DIST reaction list (RXNID) (not checked); LHHW solids basis (needs a solids reactor, not checked); REAC-DIST salt stoichiometry, REAC-DIST salt precipitation (electrolytes, not checked); REAC-DIST kinetics subroutine, USER sets (user Fortran); USERACM sets (needs Aspen Custom Modeler, not checked); IONIC sets (needs polymer components, not checked).
