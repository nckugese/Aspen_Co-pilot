# POWERLAW reactions

Rate of a kinetic reaction: r = k (T/T0)^n exp(-E/R (1/T - 1/T0)) times the product of each reactant's concentration raised to its `EXPONENT`; with no `T_REF` the T0 terms drop out.

Root: `\Data\Reactions\Reactions\{id}`

Stoichiometry, `PRE_EXP` and `ACT_ENERGY`: [reactions.md](reactions.md).

`PRE_EXP` is in SI units whatever the unit set: on `MOLARITY` with two first-order reactants it is m3/(kmol s).

With `T_REF`, `PRE_EXP` is the rate constant at T0.

With `CAT-WT` the rate is per kg of catalyst, and the reactor needs a catalyst mass ([rcstr-catalyst.md](../blocks/rcstr-catalyst.md)).

`PARTIALPRES` (here and in `R_D_KBASIS`) is accepted only for a vapor reaction (`PHASE` `V`).

| Path | Type | Purpose |
|---|---|---|
| `Input\T_EXP\{rxn}` | real | Temperature exponent n |
| `Input\T_REF\{rxn}` | TEMPERATURE | Reference temperature T0 |
| `Input\R_D_CBASIS\{rxn}` | `MOLARITY`, `MOLALITY`, `MOLEFRAC`, `MASSFRAC`, `MASSCONC`, `MOLE-GAMMA`, `FUGACITY` | Concentration basis of the rate |
| `Input\R_D_RBASIS\{rxn}` | `REAC-VOL`, `CAT-WT` | Rate per reactor volume or per catalyst mass |
