# HeatX shell and tube geometry

Paths are under `\Data\Blocks\{name}\`. Used with `MODE=DETAILED`.

A detailed block needs at least `SHELL_DIAM`, `TOTAL_NUMBER`, `LENGTH`, `OUTSIDE_DIAM`, `PITCH`, `TUBE_NPASS`, `BAFFLE_CUT` and `NSEG_BAFFLE`; in `SIMULATION` it needs no `SPEC`.

## Geometry | Shell

| Path | Type | Purpose |
|---|---|---|
| `Input\HSHELL_TUBE` | `SHELL`, `TUBE` | Side the hot stream flows in |
| `Input\TEMA_TYPE` | `E`, `F`, `G`, `H`, `J`, `X` | TEMA shell type |
| `Input\SHELL_DIAM` | LENGTH | Shell inside diameter |
| `Input\TUBE_NPASS` | `1`, `2`, `4`, `6`, `8`, `10`, `12` | Tube passes per shell |
| `Input\ORIENTATION` | `HORIZONTAL`, `VERTICAL` | Exchanger orientation |
| `Input\SHELL_NSER` | int | Shells in series |
| `Input\SHELL_NPAR` | int | Shells in parallel |

## Geometry | Tubes

| Path | Type | Purpose |
|---|---|---|
| `Input\TOTAL_NUMBER` | int | Number of tubes |
| `Input\LENGTH` | LENGTH | Tube length |
| `Input\OUTSIDE_DIAM` | LENGTH | Tube outside diameter |
| `Input\WALL_THICK` | LENGTH | Tube wall thickness (or `INSIDE_DIAM`) |
| `Input\PITCH` | LENGTH | Tube pitch, center to center |
| `Input\PATTERN` | `TRIANGLE`, `SQUARE`, `ROT-TRIANGLE`, `ROT-SQUARE` | Tube layout |
| `Input\MATERIAL` | material code (e.g. `CARBON-STEEL`) | Tube material |
| `Input\OPT_TUSIZE` | `ACTUAL`, `NOMINAL` | Tube size by diameters, or by `NOMINAL_SIZE` and `BWG` |
| `Input\TUBE_TYPE` | `BARE`, `FINNED` | Bare or finned tubes |

## Geometry | Tube Fins (`TUBE_TYPE=FINNED`)

The fin root diameter (tube OD minus twice `HEIGHT`) must lie between the tube's inside and outside diameters.

| Path | Type | Purpose |
|---|---|---|
| `Input\HEIGHT` | LENGTH | Fin height |
| `Input\NPER_LENGTH` | INVERSE-LENG | Fin count per metre of tube |
| `Input\THICKNESS` | LENGTH | Fin thickness |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\HX_AREAP` | AREA | Surface the entered geometry provides |
| `Output\HX_TMV` | VELOCITY | Tube-side velocity |
| `Output\HX_SMCV` | VELOCITY | Shell-side crossflow velocity |
| `Output\HX_UAVC` | HEAT-TRANS-C | Clean U |
| `Output\HX_XIC` | fraction | Thermal effectiveness |
| `Output\HX_OVERD` | percent | Over-design of the geometry (`RATING`) |
