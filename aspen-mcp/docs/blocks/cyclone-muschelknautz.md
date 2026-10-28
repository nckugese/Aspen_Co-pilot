# Cyclone: Muschelknautz method

`METHOD` = `MUSCHELKNAUT`: wall friction model, with more inlet shapes. Paths are under `\Data\Blocks\{name}\`; basics in [cyclone.md](cyclone.md), dimensions in [geometry](cyclone-geometry.md).

`AXIAL` and `SPIRAL` inlets are refused unless the method is `MUSCHELKNAUT`.

`ROUND` takes `DIAM_INLET` in place of the inlet height and width; `AXIAL` also needs `ANGLE_BLADE`, `SPIRAL` `ANGLE_INLET`.

Give the geometry as a standard `TYPE` or as `USER`: with `USER-RATIO` this method stays incomplete.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\WALL_FRIC` | real | Wall friction coefficient (default 0.0075) |
| `Input\D_CONST` | real | Model constant D (default 3) |
| `Input\KG_CONST` | real | Model constant Kg (default 0.025) |

## Input | Dimensions (`TYPE` = `USER`)

| Path | Type | Purpose |
|---|---|---|
| `Input\CONFIG_INLET` | `RECTANGULAR`, `ROUND`, `AXIAL`, `SPIRAL` | Inlet shape (default `RECTANGULAR`) |
| `Input\DIAM_INLET` | LENGTH | `ROUND`: inlet diameter, below half of `DIAM` |
| `Input\ANGLE_BLADE` | deg | `AXIAL`: blade angle |
| `Input\BLADE_TYPE` | `STRAIGHT`, `CURVED`, `SNAIL` | `AXIAL`: blade shape |
| `Input\ANGLE_INLET` | deg | `SPIRAL`: wrap angle of the inlet |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\OUT_VELOC` | VELOCITY | Gas velocity in the vortex finder |
| `Output\PDROP` | PDROP | Gas pressure drop |
