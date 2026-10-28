# FabFl: design mode

`MODE` `DESIGN` finds the filtering area for the gas, and from the bag data the number of cells; `AREA_OPT` picks the method. Paths are under `\Data\Blocks\{name}\`; basics in [fabfl.md](fabfl.md).

`FROM-BAGHOUS` and `FROM-VGAS` need `INIT_VEL`, `FROM-PDROP` `AVG_PDROP` and `FILT_TIME`, `FROM-ACRATIO` the [coefficient model](fabfl-coefficient-model.md).

`FROM-BAGHOUS` keeps the bag data and returns `NCELLS_OUT`: 10 cells for 1000 kmol/hr nitrogen at `INIT_VEL` 0.01 m/s; 0.005 m/s gave 12 and 0.02 m/s gave 10 again.

`FROM-VGAS` sizes the area so the gas crosses the cloth at `INIT_VEL`.

Use `FROM-PDROP` with `CALCULATE` `PRESSURE`: with `TIME` the area came out below 1 m2 and the run warned.

Aspen refuses an `INIT_VEL` above `MAX_VEL`, an `AVG_PDROP` outside 0.005 to 0.05 bar, and `PDROP_OPT` `CONSTANT` together with `FROM-PDROP`.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\AREA_OPT` | `FROM-BAGHOUS`, `FROM-VGAS`, `FROM-ACRATIO`, `FROM-PDROP` | How the area is found: bag data and a velocity guess (default), a set velocity, the air-to-cloth model, or a mean drop |
| `Input\INIT_VEL` | VELOCITY | Gas velocity through the cloth (for `FROM-BAGHOUS` a guess) |
| `Input\AVG_PDROP` | PDROP | `FROM-PDROP`: mean drop over a cycle |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\NCELLS_OUT` | int | `FROM-BAGHOUS`: cells needed |
| `Output\TOT_AREA` | AREA | Filtering area found |
| `Output\VELOCITY` | VELOCITY | Gas velocity through the cloth |
| `Output\THICKNESS` | LENGTH | Cake thickness before cleaning |
| `Output\TIME` | TIME | Filtering time (`CALCULATE` `TIME`) |
