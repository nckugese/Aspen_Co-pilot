# Crystallizer: solubility

How the saturation concentration is given (`SOL_METHOD`). Paths are under `\Data\Blocks\{name}\`; basics in [crystallizer.md](crystallizer.md).

## Table (`SOLUBILITY`)

| Path | Type | Purpose |
|---|---|---|
| `Input\SOL_TYPE` | `CONCEN`, `RATIO` | Table of concentrations (`SOLUB_CONCEN`) or of mass ratios (`SOLUB_RATIO`) |
| `Input\SOL_BASIS` | `SOLUTION`, `SOLVENT` | Amount of solute per solution (default) or per solvent |
| `Input\SOLVENT_CID` | component | The solvent, for `SOL_BASIS` `SOLVENT` |
| `Input\SOLUB_RATIO\{row}` | mass ratio | kg solute per kg solvent (or solution) at that row's `SOLUB_TEMP` |

0.01 and 0.2 kg/kg at 10 and 60 C on solvent basis left 0.067 kg acid per kg water at 25 C.

## Function (`SOLUB-FUN`)

ln S = `SOLUB_A` + `SOLUB_B`/T + `SOLUB_C` ln T + `SOLUB_D` T, with T in `TEMP_UNIT` and S in `CONC_UNITS` (or a mass ratio); `SOLUB_A` 3.4 with T in K gave e^3.4 = 30 g/l.

Set `TEMP_UNIT` and `CONC_UNITS`: without them the block stays incomplete.

| Path | Type | Purpose |
|---|---|---|
| `Input\SOLUB` | `CONC`, `RATIO` | S is a concentration or a mass ratio |
| `Input\SOLUB_A` | real | Constant term |
| `Input\SOLUB_B` | real | Coefficient of 1/T |
| `Input\SOLUB_C` | real | Coefficient of ln T |
| `Input\SOLUB_D` | real | Coefficient of T |
| `Input\TEMP_UNIT` | `K`, `C`, `F`, `R` | Unit of T |
| `Input\CONC_UNITS` | `kg/cum`, `lb/cuft`, `gm/l`, `gm/cc`, `mg/l`, `mg/cc`, `mg/cum`, `lb/gal` | Unit of S for `CONC` |

## Electrolyte chemistry (`CHEMISTRY`)

The salt equilibrium comes from a Chemistry object (here the global one, `GCHEMISTRY`) whose salt is a component of type `SOLID`; it needs `SALT` but no stoichiometry row.

| Path | Type | Purpose |
|---|---|---|
| `Input\SALT` | component | The salt that crystallizes (a component ID) |
| `Input\SALT_OUT` | `YES`, `NO` | Crystals go to `CISOLID` (default) or stay in `MIXED` as a solid |

With `SALT_OUT` `NO` the run put all crystals in `MIXED`.

| Path | Type | Purpose |
|---|---|---|
| `Input\SALT_IN` | `YES`, `NO` | Salt arriving in `CISOLID` takes part in the equilibrium (default) or passes through |

A slurry diluted with water kept more crystals with `SALT_IN` `NO`.

| Path | Type | Purpose |
|---|---|---|
| `Output\B_MASSFLOW` | MASS-FLOW | Crystal product rate (it matched the CISOLID salt flow) |

`B_MASSFLOW` equalled the crystals in `P(OUT)` in the chemistry run.
