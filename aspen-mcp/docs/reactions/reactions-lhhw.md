# LHHW reactions

Rate = kinetic factor x driving force / adsorption^m. The kinetic factor is the power-law k of [reactions-powerlaw.md](reactions-powerlaw.md); the driving force is K1 times the product of C^`EXPON` minus K2 times the product of C^`EXPON1`; the adsorption is a sum of terms K times a product of C^exponent.

Root: `\Data\Reactions\Reactions\{id}`

Stoichiometry and `PRE_EXP` / `ACT_ENERGY`: [reactions.md](reactions.md); equilibrium reactions: [reactions-equilibrium.md](reactions-equilibrium.md).

With K1 = 1, K2 near 0 and one adsorption term K = 1 the rate is the power-law rate.

An adsorption term 5 C_ETOH next to the constant term cut the conversion by more than half.

K2 on the products adds a reverse term.

## Driving force

1. After `add_reaction`, `EXPON\{rxn}` holds a row per reactant and `EXPON1\{rxn}` a row per product: write their values; `DF1_*` / `DF2_*` take a value at once.

| Path | Type | Purpose |
|---|---|---|
| `Input\EXPON\{rxn}\{comp}\MIXED` | real | First-term exponent |
| `Input\EXPON1\{rxn}\{prod}\MIXED` | real | Second-term exponent |
| `Input\DF1_A\{rxn}` | real | ln K1, constant part (`DF1_B` over T, `DF1_C` times ln T, `DF1_D` times T) |
| `Input\DF2_A\{rxn}` | real | ln K2, built the same way from `DF2_A` ... `DF2_D` |

## Adsorption

1. `insert_row` + `set_label` `1`, `2`, ... (one per term) on `Input\ADS_A\{rxn}`; `ADS_B`, `ADS_C`, `ADS_D` get the same rows.
2. `insert_row` on `Input\ADS_EXPONENT\{rxn}`, `set_label` the component (dimension 0) and `MIXED` (dimension 1); then `insert_row` on `ADS_EXPONENT\{rxn}\{comp}\MIXED` once per term: `#0` is term 1.

| Path | Type | Purpose |
|---|---|---|
| `Input\ADS_A\{rxn}\{term}` | real | ln K of a term, constant part (`ADS_B` over T, `ADS_C` times ln T, `ADS_D` times T) |
| `Input\ADS_EXPONENT\{rxn}\{comp}\MIXED\#0` | real | Exponent of the component in term 1 (`#1` term 2, ...) |
| `Input\ADS_PW_EXP\{rxn}` | real | Power m of the adsorption expression |
