# GENERAL reactions

A GENERAL set picks the rate form per reaction (`REAC_CLASS`) and can make a reaction reversible.

Root: `\Data\Reactions\Reactions\{id}`

Each reaction needs a name in `REACNAME`: without one the run does not start.

`add_reaction` builds class `POWERLAW`; its rows are those of [reactions.md](reactions.md) and it gave the POWERLAW set's conversion.

Class `LHHW` uses the adsorption rows of [reactions-lhhw.md](reactions-lhhw.md) at the same paths, with the `EXPONENT` power law as driving force: the same terms gave the LHHW set's conversion.

`REVERSIBLE` `YES` with `AUTOMATIC` adds the reverse rate from the equilibrium constant: conversion fell below the forward-only run and stayed below equilibrium.

`STATUS` `OFF` leaves the reaction out.

Class `EQUILIBRIUM`: [reactions-equilibrium.md](reactions-equilibrium.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\REACNAME\{rxn}` | string | Reaction name (required) |
| `Input\REAC_CLASS\{rxn}` | `POWERLAW`, `LHHW`, `EQUILIBRIUM` | Rate form |
| `Input\STATUS\{rxn}` | `ON`, `OFF` | Reaction used or left out |
| `Input\REVERSIBLE\{rxn}` | `NO`, `YES` | Add a reverse rate |
| `Input\REV_METH\{rxn}` | `AUTOMATIC` | Reverse rate from the equilibrium constant |
| `Input\RATE_UNITV\{rxn}` | `KMOL/CUM-S`, `KMOL/CUM-HR`, `MOL/CC-S`, `LBMOL/CUFT-HR` | Rate unit, volume basis |
| `Input\RATE_UNITC\{rxn}` | `KMOL/KG-S`, `KMOL/KG-HR`, `MOL/GM-S`, `LBMOL/LB-HR` | Rate unit, catalyst-mass basis |
