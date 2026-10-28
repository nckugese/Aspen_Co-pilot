# Pipe methods and convergence

Paths are under `\Data\Blocks\{name}\` (Advanced | Methods and Convergence). Fluid flow only (`PIPE_METH=FLUID`).

## Methods

| Path | Type | Purpose |
|---|---|---|
| `Input\METHOD` | `INTEGRATE`, `CLOSED-FORM`, `CONST-DP-DL` | Integrate along the pipe, one closed-form equation (single-phase lines), or a constant gradient |
| `Input\CL_FORM_METH` | `AGA`, `WEYMOUTH`, `PANHANDLE-A`, `PANHANDLE-B`, `SMITH`, `OLIPHANT`, `HAZEN-WILL` | Closed-form equation (`CLOSED-FORM`): the gas equations, or `HAZEN-WILL` for water-like liquids |
| `Input\EFFICIENCY` | real | Pipeline efficiency factor, 1 = clean pipe (`CLOSED-FORM`) |
| `Input\H_W_COEFF` | real | Hazen-Williams C factor (default 100) |

`EFFICIENCY` below 1 raises the drop with `PANHANDLE-A` (0.9 gives about 20 % more).

Correlations by slope (`INTEGRATE`): `FRIC_*` set the friction drop, `HOLDUP_*` the liquid holdup, for horizontal (`HORIZ`), upward (`INCL`), vertical (`VERTICA` / `VERTI`) and downhill (`DOWNHIL` / `DOWNH`) pipes.

| Path | Type | Purpose |
|---|---|---|
| `Input\FRIC_HORIZ` | `BEGGS-BRILL`, `DUKLER`, `LOCK-MART`, `DARCY`, `HTFS` | Friction, horizontal |
| `Input\FRIC_INCL` | `BEGGS-BRILL`, `DUKLER`, `ORKI`, `AWR`, `H-BROWN`, `DARCY`, `HTFS` | Friction, upward |
| `Input\FRIC_VERTICA` | `BEGGS-BRILL`, `ORKI`, `AWR`, `H-BROWN`, `DARCY`, `HTFS` | Friction, vertical |
| `Input\FRIC_DOWNHIL` | `BEGGS-BRILL`, `SLACK`, `DARCY`, `HTFS` | Friction, downhill |
| `Input\HOLDUP_HORIZ` | `BEGGS-BRILL`, `EATON`, `LOCK-MART`, `HOOG`, `HUGH`, `HTFS` | Holdup, horizontal |
| `Input\HOLDUP_INCL` | `BEGGS-BRILL`, `FLANIGAN`, `ORKI`, `AWR`, `H-BROWN`, `HTFS` | Holdup, upward |
| `Input\HOLDUP_VERTI` | `BEGGS-BRILL`, `ORKI`, `AWR`, `H-BROWN`, `HTFS` | Holdup, vertical |
| `Input\HOLDUP_DOWNH` | `BEGGS-BRILL`, `SLACK`, `HTFS` | Holdup, downhill |
| `Input\PACKED_BED` | `NO`, `YES` | The pipe is filled with packing |
| `Input\VOIDAGE` | real | Bed void fraction (`PACKED_BED=YES`) |
| `Input\DIA_PART` | LENGTH | Particle diameter (`PACKED_BED=YES`) |
| `Input\SPHERICITY` | real | Particle sphericity, 1 = sphere (`PACKED_BED=YES`) |

## Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\CORR_METHOD` | `NEWTON`, `DIRECT` | How the corrector converges (`INTEGRATE`) |
| `Input\HINIT` | real | First step size, relative to the pipe length |
| `Input\INT_TOL` | real | Integration tolerance |
| `Input\CORR_TOL_RAT` | real | Corrector tolerance over `INT_TOL` |
| `Input\NPOINT` | int | Count of calculation points over the length |
| `Input\CDPDL_TOL` | real | Tolerance on the gradient (`CONST-DP-DL`) |
| `Input\BB1` | real | `BB1` to `BB10`: coefficients of the Beggs-Brill holdup correlation; blank = built-in |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\DPFRIC` | PRESSURE | Friction part of the drop |
| `Output\IN_LVFRAC` | fraction | No-slip liquid volume fraction at the inlet |
| `Output\IN_REGIME` | int | Flow-pattern code at the inlet (`OUT_REGIME` outlet) |
| `Output\DPTOTL` | PRESSURE | Total drop with the packing |
