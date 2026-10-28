# Cyclone: own geometry

`TYPE` = `USER` (dimensions) or `USER-RATIO` (ratios to the diameter) in place of a standard family. Paths are under `\Data\Blocks\{name}\`; basics in [cyclone.md](cyclone.md).

`USER` needs the five lengths and diameters below plus the inlet height and width.

`USER-RATIO` needs the same seven as ratios.

`USER` is refused in `DESIGN`; `USER-RATIO` works in both modes.

`NTURN` and `RAT_NTURN` (gas turns of the `LAPPLE` method) are optional; blank, a default is used.

## Input | Dimensions (`TYPE` = `USER`)

| Path | Type | Purpose |
|---|---|---|
| `Input\LEN_CYLINDER` | LENGTH | Length of the cylindrical part |
| `Input\LEN_CONE` | LENGTH | Height of the conical part |
| `Input\LEN_OVER` | LENGTH | Vortex finder length; below cylinder plus cone |
| `Input\DIAM_OVER` | LENGTH | Gas outlet (vortex finder) diameter; below `DIAM` |
| `Input\DIAM_UNDER` | LENGTH | Solids outlet diameter; below `DIAM` |
| `Input\HT_INLET` | LENGTH | Inlet height |
| `Input\WIDTH_INLET` | LENGTH | Inlet width |
| `Input\NTURN` | real | `LAPPLE`: how many turns the gas makes |

Inlet shapes other than rectangular: [Muschelknautz](cyclone-muschelknautz.md).

## Input | Ratios (`TYPE` = `USER-RATIO`)

Each `RAT_*` is the matching dimension over the cyclone diameter.

| Path | Type | Purpose |
|---|---|---|
| `Input\RAT_LEN_CYLI` | ratio | Cylinder length |
| `Input\RAT_LEN_CONE` | ratio | Cone length |
| `Input\RAT_LEN_OVER` | ratio | Vortex finder length |
| `Input\RAT_DIAM_OVE` | ratio | Gas outlet diameter |
| `Input\RAT_DIAM_UND` | ratio | Solids outlet diameter |
| `Input\RAT_HT_INLET` | ratio | Inlet height |
| `Input\RAT_WIDTH_IN` | ratio | Inlet width |
| `Input\RAT_NTURN` | real | `LAPPLE`: gas turns |
| `Input\RAT_MAX_DIAM` | LENGTH | `DESIGN`: largest diameter allowed |

## Results (after a run; a standard `TYPE` reports its dimensions too)

| Path | Type | Purpose |
|---|---|---|
| `Output\LEN_CYL` | LENGTH | Cylinder length |
| `Output\LEN_CONE_OUT` | LENGTH | Cone length |
| `Output\DIAM_OUT` | LENGTH | Gas outlet diameter |
| `Output\DIAM_SOL` | LENGTH | Solids outlet diameter |
| `Output\HEIGHT` | LENGTH | Inlet height |
| `Output\WIDTH` | LENGTH | Inlet width |
| `Output\LEN_VORTEX` | LENGTH | Natural vortex length |
| `Output\NTURNS` | real | Gas turns used |
