# VScrub: design

`MODE` `DESIGN`: the block sizes the unit to catch the share `EFF` of the dust. Paths are under `\Data\Blocks\{name}\`; basics in [vscrub.md](vscrub.md).

## Venturi

`YUNG` design keeps the throat velocity within `MIN_VEL`-`MAX_VEL` and the diameter within `MIN_DIAM`-`MAX_DIAM`; with the default `MIN_DIAM` (0.15 m) this 2300 m3/h gas could not reach `MIN_VEL` and the block was bypassed with a warning. Lower `MIN_DIAM` for small gas flows.

Here `YUNG` picked the middle of the velocity range: 85 m/s with the defaults, 70 m/s with 40-100 m/s.

| Path | Type | Purpose |
|---|---|---|
| `Input\EFF` | fraction | Target share of the dust caught (required) |
| `Input\VEL_RATIO` | ratio | `YUNG`: droplet over gas velocity at the throat exit (default 0.8) |
| `Input\THROAT_SHAPE` | `ROUND`, `ANNULAR`, `RECTANGULAR` | Shape of the sized throat |
| `Input\OD:ID` | ratio | `ANNULAR`: outer over inner diameter (default 2) |
| `Input\W:H` | ratio | `RECTANGULAR`: width over height (default 2) |

Throat limits, on the Operating Options sheet (`YUNG`):

| Path | Type | Purpose |
|---|---|---|
| `Input\MIN_VEL` | VELOCITY | Lowest throat gas velocity (default 50 m/s) |
| `Input\MAX_VEL` | VELOCITY | Highest throat gas velocity, 80 to 200 m/s (default 120) |
| `Input\MIN_DIAM` | LENGTH | Smallest throat diameter (default 0.15 m) |
| `Input\MAX_DIAM` | LENGTH | Largest throat diameter (default 1.15 m) |
| `Input\MIN_RATIO` | ratio | Lowest liquid over gas volume ratio (`MAX_RATIO` the highest) |
| `Input\LIQ_VEL` | VELOCITY | Speed at which the liquid is injected into the throat (default 0) |
| `Input\VOL_RATIO` | ratio | Starting guess of the liquid over gas volume ratio (default 0.001) |

## Spray tower

With `SPEREGAVE` the target must be reachable at the given `REL_GAS_VEL`: 0.5 at 3 m/s ended with a warning and the best efficiency found (0.15).

`CALC_NOZZLES` `YES` finds the nozzle count for the `DROP_DIA` given; it needs `DIAM_ORIFICE` and `SPRAY_ANGLE`, and a droplet larger than one nozzle makes (the limit depends on the nozzle) ends with a warning.

| Path | Type | Purpose |
|---|---|---|
| `Input\CALC_NOZZLES` | `NO`, `YES` | Let the block size the nozzle count (`SPESAUDIAM`, `SPEREGAVE`) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\DIAM` | LENGTH | Sized round throat diameter |
| `Output\LENGTH` | LENGTH | `YUNG`: sized throat length |
| `Output\VELOCITY` | VELOCITY | Throat gas velocity chosen |
| `Output\OUTSIDE_DIAM` | LENGTH | `ANNULAR`: sized outer diameter (`INSIDE_DIAM` the inner) |
| `Output\EFF_OUT` | fraction | Efficiency reached |
| `Output\GAS_VEL` | VELOCITY | Spray tower: gas velocity found |
| `Output\NUMBER` | int | Spray tower: nozzle count found |
