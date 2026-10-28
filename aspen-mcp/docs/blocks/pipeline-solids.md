# Pipeline solids conveying

Paths are under `\Data\Blocks\{name}\` (Setup | Solids Conveying, `PIPE_METH=SOLIDS`): a gas carries a solid through the segments.

The solid must be in a solid substream: stream class `MIXCISLD`, solid component in `CISOLID`.

Segments are set as for fluid flow; the thermal and correlation settings are not used.

| Path | Type | Purpose |
|---|---|---|
| `Input\PIPE_METH` | `SOLIDS` | Switches the block to conveying |
| `Input\CONVEY_METH` | `DILUTE`, `DENSE` | Dilute phase (particles in suspension) or dense phase |
| `Input\DILUTE_METH` | `MUSCHELKNAUT`, `SIEGEL` | Correlation for the dilute-phase drop |
| `Input\DIA_PART` | LENGTH | Particle diameter |
| `Input\SPHERICITY` | real | Particle sphericity (1 = sphere) |
| `Input\VOIDAGE` | real | Bed voidage (`DENSE`) |
| `Input\SALTATION_V` | `MOLERUS`, `SEGLER`, `MUSCHELKNAUT`, `RIZK`, `WIRTH` | Saltation-velocity correlation |
| `Input\ACCELERATE` | `YES`, `NO` | Include the acceleration pressure drop |
| `Input\FLUID_METH` | `USER-SPEC`, `BLASIUS` | Gas wall-friction factor: given (`FLUID_FRIC`) or Blasius |
| `Input\LAMBS_METH` | `USER-SPEC`, `MUSCHELKNAUT` | Solids friction factor: given (`MUS_LAMBS`) or correlated |
| `Input\MUS_LAMBS` | real | Solids friction factor (Muschelknaut); `MUS_*` hold the other method constants |
| `Input\SIEG_LAMBS` | real | Solids friction factor (`SIEGEL`) |
| `Input\SOLIDS_MAXIT` | int | Iteration limit |
| `Input\DILUTE_PTOL` | real | Pressure tolerance, dilute phase (`DENSE_PTOL` dense) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\CNVY_TPRES` | PRESSURE | Total pressure drop |
| `Output\CNVY_TDUTY` | ENTHALPY-FLO | Heat duty |
| `Output\CNVY_TAPP` | VELOCITY | Gas velocity above the saltation velocity |
| `Output\SOLIDS_LOAD` | ratio | Solids loading, solid over gas mass flow |
