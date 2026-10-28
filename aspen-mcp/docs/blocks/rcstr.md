# RCSTR

Continuous stirred tank with kinetic reactions; the contents and the outlet have one composition and temperature. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `P(OUT)` product, `VI(IN)` vapor inlet ([mass transfer](rcstr-mass-transfer.md)), `HS(IN)` / `HS(OUT)` heat streams.

It needs a reaction set in `RXN_ID` and the value of the thermal spec; without either the input stays incomplete and the block is not solved.

`PRES` left blank keeps the feed pressure; a negative value is a drop from the feed pressure.

Leave the size value blank and the run still ends with `BLKSTAT` 0, but with no volume and next to no conversion: always set `VOL` or `RES_TIME`.

A fresh block has `PHASE` = `V` (vapor only) and `NPHASE` = `1`: a liquid reactor needs `PHASE` = `L`.

`RXN_ID` starts with no rows: `insert_row`, then `set_value` on `Input\RXN_ID\#0` with the set's ID; one row per reaction set.

A POWERLAW reaction whose `ACT_ENERGY` is left blank reacts not at all, with no message; an entered 0 works. Set it in the reaction set.

`RES_TIME` is the total residence time: after the run `Output\TOT_RES_TIME` equals it.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES` | PRESSURE | Reactor pressure |
| `Input\SPEC_OPT` | `TEMP`, `DUTY`, `VFRAC` | Thermal spec: temperature, heat duty or vapor fraction |
| `Input\TEMP` | TEMPERATURE | Reactor temperature (`TEMP`) |
| `Input\DUTY` | ENTHALPY-FLO | Heat added (`DUTY`; 0 is adiabatic) |
| `Input\VFRAC` | fraction | Vapor fraction (`VFRAC`, needs `NPHASE` 2 or 3) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the reactor: 1, vapor-liquid, vapor-liquid-liquid ([rcstr-phases.md](rcstr-phases.md)) |
| `Input\PHASE` | `L`, `V` | The phase when `NPHASE` is 1 |
| `Input\SPEC_TYPE` | `TOT-VOL`, `RES-TIME` | Size spec: reactor volume or residence time (phase-based codes: [rcstr-phases.md](rcstr-phases.md)) |
| `Input\VOL` | VOLUME | Reactor volume |
| `Input\RES_TIME` | TIME | Residence time |
| `Input\EQUIP_MODE` | `CONCEPTUAL`, `EQUIP-BASED` | Plain volume, or a described vessel ([rcstr-equipment.md](rcstr-equipment.md)) |

## Setup | Reactions

| Path | Type | Purpose |
|---|---|---|
| `Input\RXN_ID\{row}` | ID | Reaction set used (`\Data\Reactions\Reactions\{id}`) |
| `Input\REACSYS` | `YES`, `NO` | Use the reaction sets (`NO` turns reactions off) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\TOT_VOL` | VOLUME | Reactor volume |
| `Output\TOT_RES_TIME` | TIME | Total residence time |
| `Output\B_VFRAC` | fraction | Outlet vapor fraction |
| `Output\REAC_LRATE\{id}` | MOLE-FLOW | Rate of each liquid reaction, by reaction number |
| `Output\REAC_VRATE\{id}` | MOLE-FLOW | Rate of each vapor reaction, by reaction number |

More: [phases and phase-based sizing](rcstr-phases.md), [equipment-based vessel](rcstr-equipment.md), [jacket and coil heat transfer](rcstr-heat-transfer.md), [catalyst](rcstr-catalyst.md), [mass transfer](rcstr-mass-transfer.md), [convergence and estimates](rcstr-convergence.md).

Not covered: Dynamics (Aspen Dynamics only); EO Options (equation-oriented options, not checked); Heat-transfer results (jacket and coil result views, no keywords in the RCSTR COM tree); User Subroutine (user Fortran kinetics); Component Attributes (component attributes of solids, not checked); PSD (particle size distribution of solids, not checked); Generalized estimates (general flow estimates, not checked); Custom kLa (user kLa correlation, not checked); Process-side film coefficients (film-coefficient correlations, not checked); Side duty, External exchanger cooling, External exchanger heating (no keywords in the RCSTR COM tree); Crystallization (CRYSTSYS / CRYST_ID crystallization sets, not checked).
