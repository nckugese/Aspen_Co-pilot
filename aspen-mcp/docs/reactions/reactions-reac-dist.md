# REAC-DIST reactions

Reactions on the stages of a RadFrac: kinetic, at equilibrium, or a fixed conversion of a key component.

Root: `\Data\Reactions\Reactions\{id}`

A RadFrac takes only this type in `REACID`: a POWERLAW set is refused. Stages, holdups and the row steps: [radfrac-reactions.md](../blocks/radfrac-reactions.md).

Its tables have no substream level: `COEF\{rxn}\{comp}`; `add_reaction` writes them that way.

Exponents belong to `KINETIC` only: clear them (`""`) before setting `EQUIL` or `CONV`.

The test column needed `MAXOL` 200 for the kinetic set and `CONV_METH` `NONIDEAL` for the equilibrium set ([radfrac-convergence.md](../blocks/radfrac-convergence.md)); without them it ended with errors.

A kinetic set uses the stage holdup given in the RadFrac.

| Path | Type | Purpose |
|---|---|---|
| `Input\REACTYPE\{rxn}` | `KINETIC`, `EQUIL`, `CONV` | Rate law, equilibrium, or conversion |
| `Input\COEF\{rxn}\{comp}` | real | Reactant coefficient (kept negative) |
| `Input\COEF1\{rxn}\{prod}` | real | Product coefficient |
| `Input\EXPONENT\{rxn}\{comp}` | real | Reactant exponent (kinetic) |
| `Input\PRE_EXP\{rxn}` | real | Factor k in front of the exponential (SI units) |
| `Input\ACT_ENERGY\{rxn}` | MOLE-ENTHALP | Activation energy E |
| `Input\R_D_CBASIS\{rxn}` | `MOLARITY`, `MOLALITY`, `MOLEFRAC`, `MASSFRAC`, `MASSCONC`, `MOLE-GAMMA`, `MOLAL-GAMMA` | Concentration basis of the rate |

Equilibrium constants: [reactions-equilibrium.md](reactions-equilibrium.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\KEY_CID\{rxn}` | component | Key component of a `CONV` reaction |
| `Input\CONV_A\{rxn}` | fraction | Share of the key component converted |
| `Input\R_D_CTYPE\{rxn}` | `SIMULT`, `SERIES` | Conversion reactions together or one after another |
