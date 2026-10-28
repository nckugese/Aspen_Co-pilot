# Equilibrium reactions

A reaction of a POWERLAW, LHHW or REAC-DIST set with `REACTYPE` `EQUIL`, or of class `EQUILIBRIUM` in a GENERAL set, is held at chemical equilibrium instead of following a rate.

Root: `\Data\Reactions\Reactions\{id}`

1. `add_reaction` as in [reactions.md](reactions.md).
2. Clear each reactant's exponent (`set_value` `""` on `EXPONENT\{rxn}\{comp}\MIXED`): `EQUIL` is refused while one holds a value.
3. Set `REACTYPE` = `EQUIL`.

`GIBBS` needs no constants; it gave the same conversion in a POWERLAW, an LHHW and a GENERAL set.

`BUILT`: ln K is A, plus B over T, plus C times ln T, plus D times T (T in K), with K on the basis `R_D_KBASIS`. K = 4 on mole fractions took the 50 + 50 kmol/hr feed to the exact 33.33 kmol/hr of ester, from A alone and from all four terms.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_KEQ\{rxn}` | `GIBBS`, `BUILT` | K from Gibbs energies, or from A-D |
| `Input\A\{rxn}` | real | ln K: constant |
| `Input\B\{rxn}` | real | ln K: coefficient of 1/T |
| `Input\C\{rxn}` | real | ln K: coefficient of ln T |
| `Input\D\{rxn}` | real | ln K: coefficient of T |
| `Input\R_D_KBASIS\{rxn}` | `MOLE-GAMMA`, `MOLAL-GAMMA`, `MOLEFRAC`, `MASSFRAC`, `MOLARITY`, `MOLALITY`, `FUGACITY` | Basis K is written on |
| `Input\DELT\{rxn}` | DELTA-T | Temperature approach: K taken at the temperature plus this (`EQUIL` only) |
