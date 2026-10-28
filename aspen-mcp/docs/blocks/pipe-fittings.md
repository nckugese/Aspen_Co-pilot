# Pipe fittings

Paths are under `\Data\Blocks\{name}\` (Setup | Fittings 1 and Fittings 2). Fittings are turned into extra length; their drop is part of `DPFRIC`.

## Fittings 1 (counts)

| Path | Type | Purpose |
|---|---|---|
| `Input\CONNECTIONS` | `FLANGED-WELD`, `SCREWED` | Joint type; it sets the loss per fitting |
| `Input\ELBOWS` | int | Number of elbows |
| `Input\GATE_VALVES` | int | Gate valves (`GLOBE_VALVES`, `BUTTERFLY_VA` the other valves) |
| `Input\STRAIGHT_TEE` | int | Tees with flow straight through (`BRANCHED_TEE` through the branch) |
| `Input\MISC_K` | real | Extra loss as a velocity-head coefficient K; `K_LABEL` a name for it |
| `Input\MISC_L_D` | real | Extra loss as equivalent length over diameter; `MISC_L_D_LAB` a name |

## Fittings 2 (changes of section)

| Path | Type | Purpose |
|---|---|---|
| `Input\ENLARGEMENT` | `NO`, `YES` | A sudden or tapered widening |
| `Input\E_DIAM` | LENGTH | Diameter after the widening (`ENLARGEMENT=YES`) |
| `Input\E_ANGLE` | ANGLE | Taper angle of the widening |
| `Input\CONTRACTION` | `NO`, `YES` | A narrowing; `C_DIAM`, `C_ANGLE` as for the widening |
| `Input\C_DIAM` | LENGTH | Diameter after the narrowing (`CONTRACTION=YES`) |
| `Input\ORIFICE` | `NO`, `YES` | A restriction plate |
| `Input\ORIFICE_DIAM` | LENGTH | Orifice bore (`ORIFICE=YES`; `ORIFICE_THIC` plate thickness) |
| `Input\PIPE_ENTRANC` | `NONE`, `INWARD`, `FLUSH` | Entrance loss from a vessel: none, pipe projecting inward, or flush |
| `Input\ENTRANCE_RD` | `0`, `.02`, `.04`, `.06`, `.1`, `.15_AND_UP` | Rounding radius over diameter of a flush entrance |
| `Input\PIPE_EXIT` | `NO`, `YES` | Add an exit loss into a vessel |

The fittings show up as equivalent length: 100 m of pipe counts as about 171 m with the Fittings 1 set above and about 241 m with the Fittings 2 set.

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\EQUIV-LEN` | LENGTH | Pipe plus fittings equivalent length |
| `Output\DPFRIC` | PRESSURE | Friction drop including the fittings |
