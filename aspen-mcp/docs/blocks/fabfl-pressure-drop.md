# FabFl: pressure drop

How the drop across cloth and cake is found, and the pressure of the dust outlet. Paths are under `\Data\Blocks\{name}\`; basics in [fabfl.md](fabfl.md).

`FROM-RES` (default): the drop rises as the cake grows, from the clean-cloth `MINIMUM` to `MAXIMUM`; `PDROP` is the mean of the two.

Doubling `RESISTANCE` halved the filtering time to the same `MAX_PDROP` (36.8 to 18.4 h).

With the default `DPMED_OPT` the clean-cloth drop stayed 0.0025 bar whatever `PDROP` or `MEDIUM_RES` said; `MEDIUM-RES` takes it from `PDROP` (0.004 bar gave `MINIMUM` 0.004).

`CAKE-RES` changed the result only in `DESIGN` with `FROM-PDROP`; a `SIMULATION` run gave the `DUST-RES` numbers.

`CONSTANT`: `PDROP` equals `AVG_PDROP`.

`VEL-FUNCTION`: drop = a + b v + c v^2 with v in `VEL_UNITS`. In `SIMULATION`, a, b and c are read as N/sqm whatever `PDROP_UNITS` says (`bar` gave a drop 1e5 times too small): enter them in N/sqm.

In `DESIGN` with `FROM-PDROP` the function sets the velocity that gives `AVG_PDROP`.

## Cloth and cake

| Path | Type | Purpose |
|---|---|---|
| `Input\PDROP_OPT` | `FROM-RES`, `CONSTANT`, `VEL-FUNCTION` | How the drop is found: from the cloth and cake resistances (default), a fixed value, or a velocity polynomial |
| `Input\RES_OPT` | `DUST-RES`, `CAKE-RES` | `FROM-RES`: cake described by a dust resistance coefficient (default) or a specific cake resistance |
| `Input\RESISTANCE` | real | `DUST-RES`: how fast the cake drop rises, Pa per kg/m2 of cake per m/s (default 60000) |
| `Input\CAKE_RES` | SPEC-FLT-RES | `CAKE-RES`: specific cake resistance |
| `Input\POROSITY` | fraction | `CAKE-RES`: cake porosity (default 0.75) |
| `Input\DPMED_OPT` | `FILTER-PDROP`, `MEDIUM-RES` | Clean-cloth drop: built in (default), or `PDROP` |
| `Input\PDROP` | PDROP | `MEDIUM-RES`: drop across the clean cloth |
| `Input\AVG_PDROP` | PDROP | `CONSTANT`: the drop |
| `Input\PDROP_UNITS` | unit name | `VEL-FUNCTION`: unit of a, b, c; use `N/sqm` |
| `Input\VEL_UNITS` | unit name | `VEL-FUNCTION`: unit of v, e.g. `m/sec` |
| `Input\PDROP_A` | real | `VEL-FUNCTION`: constant term a |
| `Input\PDROP_B` | real | `VEL-FUNCTION`: linear coefficient b |
| `Input\PDROP_C` | real | `VEL-FUNCTION`: square coefficient c |

## Dust outlet pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\SOLIDP_OPT` | `PDROP`, `INLET`, `AMBIENT`, `USER` | Pressure of `S(OUT)`: that of the clean gas (default), of the feed, 1 atm, or `PRES` |
| `Input\PRES` | PRESSURE | `USER`: the `S(OUT)` pressure |

`S(OUT)` came out at 1.2159 bar (`INLET`), 1.01325 bar (`AMBIENT`) and 1 bar (`USER`); by default it matches the gas, 1.1959 bar.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\PDROP` | PDROP | Mean drop over a cycle |
| `Output\MINIMUM` | PDROP | Drop right after cleaning |
| `Output\MAXIMUM` | PDROP | Drop just before cleaning |
| `Output\THICKNESS` | LENGTH | `DESIGN`: cake thickness before cleaning |
