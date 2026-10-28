# RPlug

Plug flow reactor: the feed reacts by the kinetic reactions of its reaction sets as it moves along a tube, with no back-mixing. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `P(OUT)` product, `C(IN)` / `C(OUT)` thermal fluid ([rplug-thermal-fluid.md](rplug-thermal-fluid.md)), `HS(OUT)` heat stream.

It needs `TYPE`, `LENGTH`, `DIAM` and a reaction set in `RXN_ID`; without any one the input stays incomplete and the simulation does not run.

`RXN_ID` starts with no rows: `insert_row`, then `set_value` on `Input\RXN_ID\#0` with the set's ID.

An EMULSION set ([../reactions/reactions-emulsion.md](../reactions/reactions-emulsion.md)) can fail in RPlug: the integration along the tube gives up and the block ends with `BLKSTAT` 1. Such a set may converge in an RBatch ([rbatch.md](rbatch.md)).

A fresh block has `PHASE` = `V` and `NPHASE` = `1`: a liquid reactor needs `PHASE` = `L`.

While `PHASE` holds a value `NPHASE` 2 or 3 is refused: write `PHASE` = `""` first. Going back, write `NPHASE` = `1` before `PHASE`.

`OPT_TSPEC` starts at `INLET-TEMP`: the tube then runs at the feed temperature and `REAC_TEMP` is ignored. Set `CONST-TEMP` to use `REAC_TEMP`.

`PRES` blank or 0 keeps the feed pressure, a value above 0 is the inlet pressure, below 0 a drop at the inlet; `PDROP` is the drop along the tube.

`DIAM` is per tube; `NTUBE` counts only with `CHK_NTUBE` = `YES`.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `T-SPEC`, `ADIABATIC`, `TCOOL-SPEC`, `CO-COOL`, `COUNTER-COOL`, `TCOOL-PROF`, `QFLUX-PROF` | Thermal mode: set temperature, adiabatic, fixed medium temperature, co- or counter-current thermal fluid ([rplug-thermal-fluid.md](rplug-thermal-fluid.md)), medium-temperature or heat-flux profile ([rplug-profiles.md](rplug-profiles.md)) |
| `Input\OPT_TSPEC` | `INLET-TEMP`, `CONST-TEMP`, `TEMP-PROF` | With `T-SPEC`: feed temperature, a constant temperature, or a profile ([rplug-profiles.md](rplug-profiles.md)) |
| `Input\REAC_TEMP` | TEMPERATURE | Reactor temperature (`CONST-TEMP`) |
| `Input\CTEMP` | TEMPERATURE | Medium temperature (`TCOOL-SPEC`) |
| `Input\U` | HEAT-TRANS-C | U between the medium and the process stream, per wall area |

## Setup | Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\LENGTH` | LENGTH | Tube length |
| `Input\DIAM` | LENGTH | Tube diameter |
| `Input\CHK_NTUBE` | `NO`, `YES` | Several identical tubes |
| `Input\NTUBE` | int | Number of tubes |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the process stream: one, vapor-liquid, vapor-liquid-liquid |
| `Input\PHASE` | `L`, `V` | The phase when `NPHASE` is 1 |

## Setup | Pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES` | PRESSURE | Inlet pressure (> 0) or inlet drop (<= 0) |
| `Input\PDROP` | PDROP | Drop along the tube (`OPT_PDROP` = `SPECIFIED`; correlations: [rplug-pressure-drop.md](rplug-pressure-drop.md)) |

## Setup | Reactions

| Path | Type | Purpose |
|---|---|---|
| `Input\RXN_ID\{row}` | ID | Reaction set used (`\Data\Reactions\Reactions\{id}`) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\TMAX` | TEMPERATURE | Highest temperature in the tube |
| `Output\RES_TIME` | TIME | Residence time |

Profiles have `NPOINT` + 1 points (11 by default): `{id}` = 1 is the inlet, the last point the outlet.

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP\MIXED\{id}` | TEMPERATURE | Temperature profile |
| `Output\B_PRES\MIXED\{id}` | PRESSURE | Pressure profile |
| `Output\B_VFRAC\MIXED\{id}` | fraction | Vapor fraction profile |
| `Output\TIME\MIXED\{id}` | TIME | Time from the inlet |

More: [thermal fluid](rplug-thermal-fluid.md), [profiles](rplug-profiles.md), [catalyst](rplug-catalyst.md), [pressure drop and holdup](rplug-pressure-drop.md), [convergence](rplug-convergence.md), [profile report](rplug-report.md).

Not covered: Dynamics (Aspen Dynamics only); User Subroutines (user Fortran subroutines); Profile sections (profile sections left the input incomplete in every setup tried); Property profiles (property-set profiles, not checked); Fluid-solid heat transfer (FLU_SOL_TEMP DIFFERENT with UCM / UCS / USM needs a solid substream; left the input incomplete); EO options (equation-oriented options (DISCR_METH, INITEO, Blocko|Eoopti), not checked).
