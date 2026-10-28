# Electrolyzer: rigorous model (Geometry)

`MODEL_TYPE` `RIGOROUS` computes the cell voltage from geometry, kinetics and transport. Paths are under `\Data\Blocks\{name}\`; setup in [electrolyzer.md](electrolyzer.md).

It needs `AREA_CELL`, `THICK_ANODE`, `THICK_CATHD` and `THICK_MEMBRN`; alkaline cells also `DIST_MMB_EL`. The other geometry fields have defaults.

The alkaline rigorous model needs a KOH component (the run without it stops with an error naming KOH).

Fields for one side come in pairs ending `_AN`/`_CA` (or `ANODE`/`CATHODE`, `_A`/`_C`): set both.

## Geometry | Electrode

| Path | Type | Purpose |
|---|---|---|
| `Input\AREA_CELL` | AREA | Cell area |
| `Input\CELLSHAPE` | `RECTANGULAR`, `CIRCULAR` | Cell shape |
| `Input\ASPR_CELL` | ratio | Width over length of a rectangular cell |
| `Input\THICK_ANODE` | SHORT-LENGTH | Anode thickness (`THICK_CATHD` cathode) |
| `Input\DIST_MMB_EL` | LENGTH | Gap between electrode and separator (alkaline) |
| `Input\POROSITY_AN` | fraction | Electrode porosity (`POROSITY_CA`) |
| `Input\CURR_DENS_AN` | CURRENT-DENS | Exchange current density on the oxygen side (`CURR_DENS_CA` hydrogen side) |
| `Input\ACT_ENERGY_A` | MOLE-ENTHALP | Activation energy, anode (`ACT_ENERGY_C`) |
| `Input\CHARGE_ANODE` | number | Transfer coefficient of the oxygen-side reaction (`CHARGE_CATHD`) |
| `Input\V_HDU_SPC` | `NO-SLIP`, `CORRELATION` | Gas holdup: no slip, or a correlation |
| `Input\BUB_FAC` | number | Bubble factor (PEM, `CORRELATION`) |

## Geometry | Membrane

| Path | Type | Purpose |
|---|---|---|
| `Input\THICK_MEMBRN` | SHORT-LENGTH | Membrane or separator thickness |
| `Input\DIFFU_SPC` | `SPECIFIED`, `CORRELATION` | Gas diffusivity in the separator: given, or from a correlation |
| `Input\POROSITY_SEP` | fraction | Separator porosity |
| `Input\ODRAG_METHOD` | `SPECIFIED`, `TBASED-CORR`, `WBASED-CORR` | Electro-osmotic drag (PEM): given, or from temperature or water content |
| `Input\OSMO_DRAG_CO` | number | Drag coefficient (`SPECIFIED`) |
| `Input\EQUIV_WEIGHT` | MOLE-WEIGHT | Polymer mass per acid site (PEM) |

## Geometry | Electrical and Calibration

| Path | Type | Purpose |
|---|---|---|
| `Input\LIMT_DENS_AN` | CURRENT-DENS | Limiting current density, anode (`LIMT_DENS_CA`) |
| `Input\VOLT_LOSS` | VOLTAGE | Extra voltage loss per cell |
| `Input\SHUNT_LOS` | fraction | Current lost to shunt paths |
| `Input\FOUL_REST` | RESISTANCE | Extra ohmic resistance per cell (fouling) |

## Drop correlation and solver limits

`PDROP_SPEC` `CORRELATION` runs with the rigorous model; with the shortcut model the run stops asking for an anode pressure-drop spec.

| Path | Type | Purpose |
|---|---|---|
| `Input\ADD_LIQ_HEAD` | `YES`, `NO` | Add the liquid head to the drop (`CORRELATION`) |
| `Input\MAX_ITERATNS` | int | Iteration limit |
| `Input\RELATIVE_TOL` | number | Relative tolerance |
| `Input\ABSOLUTE_TOL` | number | Absolute tolerance |
| `Input\FLASH_MAXIT` | int | Flash iteration limit |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\ELEC-POWER` | ELEC-POWER | Power drawn |
