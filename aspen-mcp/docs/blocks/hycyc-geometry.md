# HyCyc: geometry

How `TYPE` fixes the cyclone proportions. Paths are under `\Data\Blocks\{name}\`; basics in [hycyc.md](hycyc.md).

The four built-in types scale every dimension from `DIAM`. `USER` takes lengths from the Dimensions sheet (`SIMULATION` only); `USER-RATIO` takes ratios to `DIAM` from the Ratios sheet.

`USER` needs `LEN_CYLINDER`, `DIAM_OVER`, `DIAM_UNDER` and the inlet size: `HT_INLET` + `WIDTH_INLET` (rectangular) or `DIAM_INLET` (round).

`USER-RATIO` with a rectangular inlet needs `RAT_HT_INLET` and `RAT_WIDTH_IN`; the other ratios have defaults.

With `METHOD` `PLITT`, `NAGESWARARAO` or `MOD-BRAUN` the vortex finder length is needed too: `LEN_OVER` (`USER`) or `RAT_LEN_OVER` (`USER-RATIO`).

## Dimensions (`TYPE` `USER`)

| Path | Type | Purpose |
|---|---|---|
| `Input\CONFIG_INLET` | `RECTANGULAR`, `ROUND` | Inlet shape (default rectangular) |
| `Input\LEN_CYLINDER` | LENGTH | Length of the cylindrical part |
| `Input\DIAM_OVER` | LENGTH | Overflow outlet diameter, smaller than `DIAM` |
| `Input\DIAM_UNDER` | LENGTH | Underflow outlet diameter, smaller than `DIAM` |
| `Input\HT_INLET` | LENGTH | Rectangular inlet: height |
| `Input\WIDTH_INLET` | LENGTH | Rectangular inlet: width, under half of `DIAM` |
| `Input\DIAM_INLET` | LENGTH | Round inlet: diameter |
| `Input\LEN_OVER` | LENGTH | Vortex finder length (`PLITT`, `NAGESWARARAO`, `MOD-BRAUN`) |
| `Input\CONE_ANGLE` | ANGLE | Cone angle (`USER` and `USER-RATIO`; default 20 deg) |

## Ratios (`TYPE` `USER-RATIO`, each over `DIAM`)

| Path | Type | Purpose |
|---|---|---|
| `Input\INLET` | ratio | Round inlet diameter (default 0.1429) |
| `Input\RAT_HT_INLET` | ratio | Rectangular inlet height |
| `Input\RAT_WIDTH_IN` | ratio | Rectangular inlet width (below 0.5) |
| `Input\LENGTH` | ratio | Total length (default 5) |
| `Input\OVER` | ratio | Overflow diameter (default 0.2) |
| `Input\UNDER` | ratio | Underflow diameter (default 0.15) |
| `Input\RAT_LEN_OVER` | ratio | Vortex finder length (`PLITT`, `NAGESWARARAO`, `MOD-BRAUN`) |

## Results (after a run)

The results give the dimensions used; with `USER` they repeat the inputs.

| Path | Type | Purpose |
|---|---|---|
| `Output\DIAM_OUT2` | LENGTH | Overflow diameter |
| `Output\DIAMETER` | LENGTH | Underflow diameter |
| `Output\LEN_CYL` | LENGTH | Cylinder length |
| `Output\HEIGHT` | LENGTH | Inlet height (rectangular inlet) |
| `Output\WIDTH` | LENGTH | Inlet width (rectangular inlet) |
