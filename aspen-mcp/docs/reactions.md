# Reactions

## Reaction Set Types

| Type | Description | Use With |
|------|------------|----------|
| POWERLAW | Rate law: r = k0 * T^n * exp(-E/RT) * Prod(Ci^ai) | RCSTR, RPlug |
| LHHW | Langmuir-Hinshelwood-Hougen-Watson kinetics | RCSTR, RPlug |
| EQUILIBRIUM | Chemical equilibrium constant based | RCSTR, RPlug |
| GENERAL | User-defined rate expression | RCSTR, RPlug |

## Creating a Reaction Set

```
add_reaction_set(session, 'RXN1', 'POWERLAW')
```

## Adding a Reaction

```
add_reaction(session, 'RXN1', reaction_no=1,
    reactants={"ETHANE": 1},
    products={"ETHYLENE": 1, "HYDROGEN": 1},
    phase='V',
    exponents={"ETHANE": 1})
```

## Key Reaction Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Reactions\Reactions\{set}\Input\REACTYPE\{rxn}` | string | `KINETIC` or `EQUILIBRIUM` |
| `\Data\Reactions\Reactions\{set}\Input\PHASE\{rxn}` | string | `V`, `L`, `V-L` |
| `\Data\Reactions\Reactions\{set}\Input\COEF\{rxn}\{comp}\MIXED` | float | Reactant coefficient |
| `\Data\Reactions\Reactions\{set}\Input\COEF1\{rxn}\{comp}\MIXED` | float | Product coefficient |
| `\Data\Reactions\Reactions\{set}\Input\EXPONENT\{rxn}\{comp}\MIXED` | float | Concentration exponent |
| `\Data\Reactions\Reactions\{set}\Input\PRE_EXP\{rxn}` | float | Pre-exponential factor k0 |
| `\Data\Reactions\Reactions\{set}\Input\ACT_ENERGY\{rxn}` | float | Activation energy E (default unit: cal/mol) |
| `\Data\Reactions\Reactions\{set}\Input\T_EXP\{rxn}` | float | Temperature exponent n |

## Assigning Reaction Set to a Reactor Block

The RXN_ID node in reactor blocks (RCSTR, RPlug) has a pre-existing empty element:

```
list_elements(session, '\Data\Blocks\{name}\Input\RXN_ID')
→ [0] #0 = None

set_value(session, aspen_path='\Data\Blocks\{name}\Input\RXN_ID\#0', value='RXN1')
```

## Gotchas

- RStoic and RYield do NOT use external reaction sets — they have their own stoichiometry/yield inputs.
- COEF = reactant coefficients (positive values, Aspen auto-negates).
- COEF1 = product coefficients (positive values).
- Kinetic parameters (PRE_EXP, ACT_ENERGY) are scalar per reaction, not per component.
- Always set PRE_EXP and ACT_ENERGY for POWERLAW reactions, or the block will fail.
