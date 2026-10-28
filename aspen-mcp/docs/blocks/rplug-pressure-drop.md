# RPlug pressure drop and holdup

Paths are under `\Data\Blocks\{name}\`. `OPT_PDROP` = `CORRELATION` computes the drop from the flow, the wall roughness and the change in height instead of a fixed `PDROP`.

A rise adds the static head to the drop: `ELEVATION` gives it directly, `OPT_ELEV` = `ANGLE` from the slope.

## Setup | Pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_PDROP` | `SPECIFIED`, `CORRELATION` | Fixed drop (`PDROP`) or a correlation |
| `Input\DP_FCOR` | `BEGGS-BRILL`, `DUKLER`, `SLACK`, `ORKI`, `AWR`, `LOCK-MART`, `H-BROWN`, `DARCY`, `ERGUN`, `HTFS` | Friction method |
| `Input\ROUGHNESS` | LENGTH | Wall roughness |
| `Input\DP_MULT` | real | Factor on the friction drop |

## Setup | Configuration (height)

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_ELEV` | `RISE`, `ANGLE` | Height change given as a rise or a slope |
| `Input\ELEVATION` | LENGTH | Outlet height above the inlet (`RISE`) |
| `Input\ANGLE` | ANGLE | Slope from the horizontal (`ANGLE`) |

## Setup | Holdup (two phases)

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_HOLDUP` | `NO-SLIP`, `CALCULATED`, `SPECIFIED` | Liquid holdup equal to the liquid volume share, from a correlation, or given |
| `Input\DP_HCOR` | `BEGGS-BRILL`, `FLANIGAN`, `EATON`, `HOOG`, `HUGH`, `SLACK`, `ORKI`, `AWR` | Holdup correlation (`CALCULATED`) |
| `Input\HOLDUP\{row}` | fraction | Liquid holdup at a point (`SPECIFIED`; location row in `HLOC`, as in [rplug-profiles.md](rplug-profiles.md)) |
| `Input\HLOC\{row}` | fraction | Its location |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\B_PRES\MIXED\{id}` | PRESSURE | Pressure profile |
| `Output\B_VFRAC\MIXED\{id}` | fraction | Vapor fraction profile |
