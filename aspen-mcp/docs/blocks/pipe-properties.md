# Pipe flash and property grid

Paths are under `\Data\Blocks\{name}\` (Setup | Flash Options, Advanced | Property Grid). Fluid flow only.

## Setup | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the flashes |
| `Input\PHASE` | `V`, `L` | The phase when `NPHASE=1` |
| `Input\MAXIT` | int | Flash iteration limit |
| `Input\TOL` | real | Flash tolerance |
| `Input\PROP_SETS\{row}` | Prop-Set ID | Property sets to report along the pipe; `insert_row` then write the row |

A single-component feed with the default `T-CONST` and a 2-phase flash ends with a warning; `NPHASE=1`, `ADIABATIC` or `THERMAL` run clean.

## Advanced | Property Grid

A pressure-temperature grid: properties are interpolated from it instead of flashing at every step.

| Path | Type | Purpose |
|---|---|---|
| `Input\P_T_TABLE` | `NO`, `YES` | Use a property grid |
| `Input\OPT_ENTRY` | `RANGE`, `LIST`, `BLOCK` | Grid as ranges, as lists, or copied from another pipe |
| `Input\PMIN` | PRESSURE | Lowest grid pressure (`RANGE`; `PMAX` highest) |
| `Input\NPRES` | int | Pressures in the grid (`RANGE`) |
| `Input\TMIN` | TEMPERATURE | Lowest grid temperature (`RANGE`; `TMAX` highest) |
| `Input\NTEMP` | int | Temperatures in the grid (`RANGE`) |

1. `LIST`: `insert_row` on `Input\PRES` once per pressure, then write `Input\PRES\#0`, `#1`, ...; the same for `Input\TEMP`.

| Path | Type | Purpose |
|---|---|---|
| `Input\BLOCKID` | block ID | Pipe whose grid is copied (`BLOCK`) |

`BLOCK` needs the named pipe to run first (e.g. upstream of this one); otherwise the run warns and goes on without a grid.

| Path | Type | Purpose |
|---|---|---|
| `Input\CBAR` | PRESSURE | Cricondenbar, optional |
| `Input\RECY_REUSE` | `NO`, `YES` | Reuse the grid in later passes of a convergence loop |
| `Input\EDIT_REUSE` | `NO`, `YES` | Reuse the grid in later runs |
| `Input\TABLES` | `NO`, `YES` | Write the grid into the report |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\OUT_PRES` | PRESSURE | Outlet pressure with the grid |
