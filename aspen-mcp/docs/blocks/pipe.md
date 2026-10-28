# Pipe

One straight pipe of fixed diameter and slope, with optional fittings; gives the pressure drop and outlet state. For a line of several segments use Pipeline. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `P(OUT)` product.

To run it needs `LENGTH` and an inner diameter (`IN_DIAM`, or a nominal size with `OSCHED`); everything else has a default (flat pipe, feed temperature held, outlet pressure calculated).

## Setup | Pipe Parameters

| Path | Type | Purpose |
|---|---|---|
| `Input\PIPE_METH` | `FLUID`, `SOLIDS` | Fluid flow, or pneumatic solids conveying ([pipe-solids.md](pipe-solids.md)) |
| `Input\LENGTH` | LENGTH | Pipe length |
| `Input\OPT_DIAM` | `OINNER`, `OSCHED` | Inner diameter given, or taken from a pipe schedule |
| `Input\IN_DIAM` | LENGTH | Inner diameter (`OINNER`) |
| `Input\MATERIAL` | `CARBON-STEEL`, `STAINLESS` | Schedule material (`OSCHED`) |
| `Input\SCHEDULE` | string | Schedule: `10` ... `160` for carbon steel, `5S`, `10S`, `40S`, `80S` for stainless |
| `Input\NOMINAL_DIAM` | string | Nominal size, `0.25-IN` ... `96-IN` (set after `MATERIAL` and `SCHEDULE`) |
| `Input\OPT_ELEV` | `ORISE`, `OANGLE` | Slope given as a height change or as an angle |
| `Input\ELEVATION` | LENGTH | Outlet height above the inlet (`ORISE`; negative: downhill) |
| `Input\ANGLE` | ANGLE | Angle from horizontal, upward positive (`OANGLE`) |

## Setup | Thermal Specification

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `T-CONST`, `T-SPEC`, `THERMAL`, `ADIABATIC` | Temperature held at the inlet value, outlet temperature given, heat exchange with the surroundings, or no heat exchange |
| `Input\T_OUT` | TEMPERATURE | Outlet temperature (`T-SPEC`, or `PRES_CALC=INLET`) |
| `Input\TAMB_IN` | TEMPERATURE | Surroundings temperature at the inlet (`THERMAL`; `TAMB_OUT` at the outlet) |
| `Input\H_T_COEFF` | HEAT-TRANS-C | U value to the surroundings (`THERMAL`) |
| `Input\FLUX` | HEAT-FLUX | Heat added per length of pipe, negative removes (`THERMAL`), e.g. `Watt/m` |

With `THERMAL` the two heat terms add up; `CHK_FLUX=NO` drops the flux and `CHK_BALANC=NO` drops the U term (both NO: no heat exchanged).

## Advanced | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES_CALC` | `OUTLET`, `INLET` | Calculate the outlet pressure from the feed, or the inlet pressure from a given outlet |
| `Input\OPT_OUTLET` | `VALUES`, `STREAM` | Outlet conditions given here, or taken from the product stream's input (`INLET`) |
| `Input\P_OUT` | PRESSURE | Outlet pressure (`INLET`, `VALUES`) |
| `Input\T_IN` | TEMPERATURE | Inlet temperature (`INLET` with `T-SPEC`) |
| `Input\FLOW_CALC` | `OUTLET`, `INLET` | Flow and composition from the feed, or from the product stream's input |

`PRES_CALC=INLET` also needs `T_OUT`, whatever `TYPE` is; without it the block fails.

With `PRES_CALC=INLET` and `T-SPEC`, `T_IN` and `T_OUT` fix both ends' temperatures.

With `FLOW_CALC=INLET` give the product stream a flow and composition; the feed's results take them. Left empty, the block warns and uses the feed.

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\IN_PRES` | PRESSURE | Inlet pressure |
| `Output\OUT_PRES` | PRESSURE | Outlet pressure |
| `Output\DPTOTL` | PRESSURE | Total drop; `DPFRIC`, `DPELEV`, `DPACC` its friction, elevation and acceleration parts |
| `Output\OUT_TEMP` | TEMPERATURE | Outlet temperature (`IN_TEMP` inlet) |
| `Output\DUTY` | ENTHALPY-FLO | Heat added to the fluid |
| `Output\EQUIV-LEN` | LENGTH | Length plus the fittings' equivalent length |
| `Output\IN_VELOC` | VELOCITY | Mixture velocity at the inlet (`OUT_VELOC` outlet) |

More: [fittings](pipe-fittings.md), [methods and convergence](pipe-methods.md), [solids conveying](pipe-solids.md), [flash and property grid](pipe-properties.md).

Not covered: Dynamic (Aspen Plus Dynamics only); User Subroutines (diameter, pressure drop, holdup) (user Fortran subroutines).
