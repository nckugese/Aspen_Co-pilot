# Dryer: spray

`DRYER_TYPE` = `SPRAY`: a liquid feed is atomized into a tower of hot gas. Paths are under `\Data\Blocks\{name}\`; basics in [dryer.md](dryer.md).

The feed is a liquid: water in `MIXED` with the solids, at a pressure above the dryer's. Fed at the gas pressure the nozzle model stops (spray inlet pressure too low).

Set `NUM_DROP_INT`: without it the run ended with no results at all.

`TWO-FLUID` needs an atomizing gas stream on `G2(IN)`.

`ROTARY`: keep the wheel rim speed within 180-300 m/s; 24000 rpm on a 0.2 m wheel ran clean, 10000 rpm warned.

`USER-SPEC` also needs `DROP_VEL_INI`: without it the droplet equations failed to solve.

`INSOL_MO_CON` is the feed liquid per kg of solids (720 kg water on 180 kg calcite: 4.0).

## Input | Specifications and Atomization

| Path | Type | Purpose |
|---|---|---|
| `Input\DIAM` | LENGTH | Tower diameter |
| `Input\HEIGHT` | LENGTH | Tower height |
| `Input\ATOMIZER` | `HOLLOW-CONE`, `TWO-FLUID`, `ROTARY` | Pressure nozzle (default), nozzle with atomizing gas, or spinning wheel |
| `Input\NUM_ATOMIZER` | int | Number of atomizers |
| `Input\NOZZLE_DIAM` | LENGTH | Nozzles: orifice diameter |
| `Input\SPRAY_ANGLE` | real | `HOLLOW-CONE`: full cone angle, degrees |
| `Input\FLUID_MIXING` | `INTERNAL`, `EXTERNAL` | `TWO-FLUID`: gas and liquid mixed inside or outside the nozzle |
| `Input\WHEEL_DIAM` | LENGTH | `ROTARY`: wheel diameter |
| `Input\WHEEL_SPEED` | FREQUENCY | `ROTARY`: wheel speed |
| `Input\NUM_VANE` | int | `ROTARY`: number of vanes |
| `Input\VANE_HEIGHT` | LENGTH | `ROTARY`: vane height |
| `Input\NUM_DROP_INT` | int | Droplet size classes |
| `Input\DSD_CALC_MET` | `GEOMETRY`, `USER-SPEC` | Droplet sizes from the atomizer model (default) or given |
| `Input\D63` | LENGTH | `USER-SPEC`: characteristic droplet size |
| `Input\CUM_FREQ` | fraction | `USER-SPEC`: cumulative mass fraction below `D63` |
| `Input\RRSB_N` | real | `USER-SPEC`: RRSB spread exponent (default 1) |
| `Input\DROP_VEL_INI` | VELOCITY | `USER-SPEC`: droplet start velocity |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EVAP_RATE2` | MASS-FLOW | Moisture evaporated |
| `Output\OUSOL_MO_CON` | ratio | Product moisture, kg per kg dry solids |
| `Output\EXGT` | TEMPERATURE | Exhaust temperature |
