# Pipe solids conveying

Paths are under `\Data\Blocks\{name}\` (Setup | Solids Conveying, `PIPE_METH=SOLIDS`): a gas carries a solid through the pipe.

The solid must be in a solid substream: stream class `MIXCISLD`, solid component in `CISOLID`.

Give the length and inner diameter as for fluid flow; `OSCHED` is refused with `SOLIDS`.

| Path | Type | Purpose |
|---|---|---|
| `Input\CONVEY_METH` | `DILUTE`, `DENSE` | Dilute phase (particles carried in suspension) or dense phase |
| `Input\DILUTE_METH` | `MUSCHELKNAUT`, `SIEGEL` | Dilute-phase drop correlation |
| `Input\DIA_PART` | LENGTH | Particle diameter |
| `Input\SPHERICITY` | real | Particle sphericity (1 = sphere) |
| `Input\SALTATION_V` | `MOLERUS`, `SEGLER`, `MUSCHELKNAUT`, `RIZK`, `WIRTH` | Saltation-velocity correlation |
| `Input\ACCELERATE` | `YES`, `NO` | Count the acceleration drop |
| `Input\FLUID_METH` | `USER-SPEC`, `BLASIUS` | Gas wall friction: given (`FLUID_FRIC`) or Blasius |
| `Input\LAMBS_METH` | `USER-SPEC`, `MUSCHELKNAUT` | Solids friction: given (`MUS_LAMBS`) or correlated |
| `Input\BETA_METH` | `USER-SPEC`, `BARTH`, `MUSCHELKNAUT` | Gas-solid velocity ratio: given (`MUS_BETA`) or correlated |
| `Input\MUS_LAMBS` | real | Solids friction factor; `MUS_*` hold the other Muschelknaut constants |
| `Input\SIEG_LAMBS` | real | Solids friction factor with `SIEGEL` |
| `Input\CNVY_ELBOWS` | int | Bends in the line |
| `Input\FICT_LENG` | LENGTH | Extra length for other losses |
| `Input\SOLIDS_MAXIT` | int | Iteration limit |
| `Input\DILUTE_PTOL` | real | Pressure tolerance, dilute phase (`DENSE_PTOL` dense) |

## Dense phase (`CONVEY_METH=DENSE`)

| Path | Type | Purpose |
|---|---|---|
| `Input\VOIDAGE` | real | Void fraction of the moving plug |
| `Input\PTOW_FRIC` | real | Particle-wall friction coefficient (`PTOP_FRIC` particle-particle) |
| `Input\STRESS_COEFF` | real | How much of the plug stress reaches the wall |
| `Input\CHAR_VISC` | VELOCITY | Characteristic velocity of the plug |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\S_DPTOT` | PRESSURE | Total pressure drop |
| `Output\S_DUTY` | ENTHALPY-FLO | Heat duty |
| `Output\S_LOADING` | ratio | Solids loading, solid over gas mass flow |
| `Output\S_APPSV` | VELOCITY | Gas velocity above the saltation velocity (dilute) |
| `Output\S_SVEL` | VELOCITY | Slug velocity (dense) |
| `Output\S_SLEN` | LENGTH | Slug length (dense) |
