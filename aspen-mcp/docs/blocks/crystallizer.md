# Crystallizer

Steady crystallizer, one well-stirred vessel with the product drawn from the mix: crystallizes one solute by cooling or by boiling off solvent, optionally with a crystal size distribution. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `P(OUT)` product slurry (mother liquor plus crystals), `V(OUT)` vapor, `HS(IN)` and `HS(OUT)` heat streams.

The solute is an ordinary conventional component; the block moves the crystallized part from `MIXED` into the stream class's solid substream, `CISOLID` (`MIXCISLD`) or `CIPSD` (`MIXCIPSD`, for a size distribution).

With `SOL_METHOD` `SOLUBILITY` (default) it needs the stoichiometry row, at least one solubility point, and two of `TEMP`, `PRES`, `DUTY`, `BASIS_FLOWV`, `PROD_RATE`.

`PROD_RATE` is reached by boiling off solvent: pair it with `TEMP`, or with a `PRES` low enough to boil (for example 0.1 atm); at 1 atm with cooling alone the rate can be missed.

While two of them are set the other three refuse input: clear one (write `""`) before setting another.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\MODE` | `CRYSTALLIZE`, `EITHER` | Crystallize only (default), or crystallize or dissolve as the solubility requires |
| `Input\SOL_METHOD` | `SOLUBILITY`, `SOLUB-FUN`, `CHEMISTRY` | Saturation from a table, a function, or electrolyte chemistry ([solubility](crystallizer-solubility.md)) |
| `Input\TEMP` | TEMPERATURE | Crystallizer temperature |
| `Input\PRES` | PRESSURE | Crystallizer pressure |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty |
| `Input\BASIS_FLOWV` | MOLE-FLOW | Vapor rate to `V(OUT)` |
| `Input\PROD_RATE` | MASS-FLOW | Crystal product rate |
| `Input\NPHASE` | `1`, `2` | Phases in the flash: one, or vapor-liquid (default) |
| `Input\PHASE` | `L` | The phase when `NPHASE` is 1 |

## Setup | Stoichiometry (row `1` exists on a new block)

| Path | Type | Purpose |
|---|---|---|
| `Input\STOIC_CID1\1` | component | Crystal product: the solute |
| `Input\STOIC_SSID1\1` | substream | Its substream: `CISOLID` or `CIPSD` |
| `Input\COEF1\1` | real | Its coefficient, 1 |

1. Insert one row on `COEF\1` labeled with the solute (`insert_row`, then `set_label`); its substream is `MIXED`.

| Path | Type | Purpose |
|---|---|---|
| `Input\COEF\1\{comp}\MIXED` | real | Coefficient of the dissolved solute, -1 |

## Setup | Solubility (table)

| Path | Type | Purpose |
|---|---|---|
| `Input\SOLUB_TEMP\{row}` | TEMPERATURE | Temperature of a point; insert one row per point (`#0`, `#1`, ...), which also adds the `SOLUB_CONCEN` row |
| `Input\SOLUB_CONCEN\{row}` | MASS-CONC | Saturation concentration at that temperature, per volume of solution by default |

Between points the saturation is linear in temperature: 18 and 50 g/l at 20 and 40 C gave 26 g/l at 25 C.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Crystallizer temperature |
| `Output\B_PRES` | PRESSURE | Crystallizer pressure |
| `Output\QCALC` | ENTHALPY-FLO | Heater duty |
| `Output\QNET` | ENTHALPY-FLO | Net duty |
| `Output\VFLOW` | MASS-FLOW | Vapor flow to `V(OUT)` |
| `Output\SLURRY_DEN` | MASS-CONC | Magma density: crystal mass per slurry volume |

The crystals are in the product stream's solid substream, e.g. `\Data\Streams\{stream}\Output\MASSFLOW\CISOLID\{comp}`.

More: [solubility](crystallizer-solubility.md), [size distribution](crystallizer-psd.md), [growth kinetics](crystallizer-growth.md), [recirculation](crystallizer-recirculation.md), [convergence](crystallizer-convergence.md).

Not covered: MODE DISSOLVE (dissolving with it still ends in a crystals-formed warning; `EITHER` dissolves cleanly); SOL_METHOD USER-SUBR, Advanced|User Subroutine (user Fortran); Advanced|Component Attributes (its element list is not in this block's tree); Per-substream PSD (OPT_SUBPSD SUBSID) (its fields are not in this block's tree).
