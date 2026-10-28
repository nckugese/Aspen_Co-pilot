# HeatX U methods and film coefficients

Paths are under `\Data\Blocks\{name}\`. How the overall coefficient U is found.

`FILM-COEF` and `GEOMETRY` are refused unless `MODE=DETAILED`.

## Setup | U Methods

| Path | Type | Purpose |
|---|---|---|
| `Input\U_OPTION` | `CONSTANT`, `PHASE`, `POWER-LAW`, `FILM-COEF`, `GEOMETRY` | How U is found (default `PHASE`) |
| `Input\U` | HEAT-TRANS-C | Constant U |
| `Input\L_L` | HEAT-TRANS-C | U for one phase pair (`PHASE`) |

Phase-pair fields are `<hot>_<cold>`, each letter `L` liquid, `V` vapor or `B` boiling/condensing: `L_L`, `L_V`, `L_B`, `V_L`, `V_V`, `V_B`, `B_L`, `B_V`, `B_B`.

| Path | Type | Purpose |
|---|---|---|
| `Input\U_REF_VALUE` | HEAT-TRANS-C | U at the reference flow (`POWER-LAW`) |
| `Input\U_REF_SIDE` | `HOT`, `COLD`, `HOT-COLD` | Side whose flow scales U |
| `Input\BASIS_UFLOW` | MOLE-FLOW | Reference flow |
| `Input\U_EXPONENT` | real | Flow exponent |
| `Input\U_SCALE` | real | Factor applied to the U found |

## Setup | Film Coefficients (`U_OPTION=FILM-COEF`)

Hot-side fields start with `HH`, cold-side fields with `CH`; the two sides take the same options.

| Path | Type | Purpose |
|---|---|---|
| `Input\HH_OPTION` | `CONSTANT`, `PHASE`, `POWER-LAW`, `GEOMETRY` | How the hot film coefficient is found |
| `Input\HH` | HEAT-TRANS-C | Constant hot film coefficient |
| `Input\HH_L` | HEAT-TRANS-C | Hot film coefficient when liquid (`_V` vapor, `_B` condensing) |
| `Input\HH_REF_VALUE` | HEAT-TRANS-C | Hot film coefficient at the reference flow (`POWER-LAW`) |
| `Input\BASIS_HHFLOW` | MOLE-FLOW | Its reference flow |
| `Input\HH_EXPONENT` | real | Its flow exponent |
| `Input\CH` | HEAT-TRANS-C | Constant cold film coefficient |
| `Input\HFOUL_FACTOR` | INVERSE-HT-C | Hot-side fouling resistance (`CFOUL_FACTOR` cold side) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\HX_UAVD` | HEAT-TRANS-C | Average U used |
| `Output\HX_UAVC` | HEAT-TRANS-C | Clean U from the film coefficients |
