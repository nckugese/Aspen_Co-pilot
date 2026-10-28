# FluidBed: geometry

Vessel shape and the secondary gas inlet. Paths are under `\Data\Blocks\{name}\`; basics in [fluidbed.md](fluidbed.md).

## Rectangular vessel

`RECTANGULAR` needs `WIDTH` and `DEPTH` in place of `DIAM`.

| Path | Type | Purpose |
|---|---|---|
| `Input\WIDTH` | LENGTH | Vessel width |
| `Input\DEPTH` | LENGTH | Vessel depth |

## Diameter that changes with height

| Path | Type | Purpose |
|---|---|---|
| `Input\DIAM_OPT` | `CONSTANT`, `PROFILE` | One diameter, or a table over the height (circular only) |

1. Set `DIAM_OPT` to `PROFILE` and insert a row into `Input\DIA` (`insert_row`) per point, at least two; `DIA_LOC` gets the same rows `#0`, `#1`...
2. Write each row's diameter and its location, locations rising from 0 to 1.

| Path | Type | Purpose |
|---|---|---|
| `Input\DIA\{row}` | LENGTH | Diameter at that point |
| `Input\DIA_LOC\{row}` | fraction | Its location, fraction of `HEIGHT` |

## Secondary gas

A stream on `G2(IN)` gets an entry `FEED_LOC\<stream>` for where it enters.

| Path | Type | Purpose |
|---|---|---|
| `Input\FEED_LOC\{stream}` | fraction | Inlet height of that secondary gas stream, fraction of `HEIGHT` |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\H_BOTTOMZONE` | LENGTH | Height of the dense bottom zone |
| `Output\BED_DPCALC` | PDROP | Pressure drop over the bed |
