# Pump

Raises the pressure of a liquid; as a hydraulic turbine it lets a liquid down and recovers power. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `P(OUT)` product, `WD(OUT)` free water ([pump-flash-options.md](pump-flash-options.md)), `WS(IN)`/`WS(OUT)` work streams. A work stream on `WS(OUT)` carries the net work (its `Output\POWER_OUT`).

To run it needs `OPT_SPEC` and the field it names, or a work stream on `WS(IN)` (below); `PUMP_TYPE` starts as `PUMP`.

A work stream on `WS(IN)` sets the power instead of `OPT_SPEC`; give its `Input\POWER` negative: -2 kW gave `BRAKE_POWER` 2 kW and `WNET` 0, while +2 kW counts as power taken out and the outlet pressure goes below zero (the block fails). Work streams: [../streams/streams-heat-work.md](../streams/streams-heat-work.md).

The `PUMP` shown in `PUMP_TYPE` is a default, not an input: a Pump with nothing written is left out of the input file (EDBSEM.1) and the run does not start, even with a work stream on `WS(IN)`. Writing `PUMP_TYPE=PUMP` is enough.

Writing `PRES` (or `DELP`, `PRATIO`, `POWER`) does not set `OPT_SPEC`: the block stays incomplete until `OPT_SPEC` is written.

Only the field `OPT_SPEC` names is used; the other spec fields keep their values and are ignored.

Without `EFF` Aspen estimates the efficiency itself (for example about 0.42 for a liquid at about 10 cum/hr), it does not assume 1; `Output\CEFF` gives the value used.

`BRAKE_POWER` is `FLUID_POWER` / `EFF` for a pump and `FLUID_POWER` x `EFF` for a turbine; `ELEC_POWER` divides or multiplies by `DEFF` the same way.

With `PUMP_TYPE=TURBINE`, `DELP` is the pressure drop, `PRATIO` is below 1 and `POWER` is the power recovered, all entered positive; the power results come out negative.

Negative `DELP` or `POWER` is refused.

A feed holding vapor ends the run with an error; `VFRAC_CHK` sets this ([pump-flash-options.md](pump-flash-options.md)).

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\PUMP_TYPE` | `PUMP`, `TURBINE` | `PUMP` raises pressure, `TURBINE` recovers power |
| `Input\OPT_SPEC` | `PRES`, `DELP`, `PRATIO`, `POWER`, `USE-CURVE` | Which spec sets the outlet; `USE-CURVE`: performance curves ([pump-curves.md](pump-curves.md)) |
| `Input\PRES` | PRESSURE | Outlet pressure |
| `Input\DELP` | PDROP | Pressure rise (for a turbine, the drop) |
| `Input\PRATIO` | ratio | Outlet over inlet pressure |
| `Input\POWER` | POWER | Power put in (pump) or recovered (turbine) |
| `Input\EFF` | fraction | Pump or turbine efficiency; blank: estimated |
| `Input\DEFF` | fraction | Driver efficiency, default 1 |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\FLUID_POWER` | POWER | Power given to the liquid |
| `Output\BRAKE_POWER` | POWER | Shaft power |
| `Output\ELEC_POWER` | POWER | Driver power |
| `Output\WNET` | POWER | Net work (negative for a turbine) |
| `Output\POC` | PRESSURE | Outlet pressure |
| `Output\PDRP` | PDROP | Pressure change |
| `Output\PRES_RATIO` | ratio | Pressure ratio (only with `OPT_SPEC=PRATIO`) |
| `Output\HEAD_CAL` | HEAD | Head developed |
| `Output\CEFF` | fraction | Efficiency used |
| `Output\VFLOW` | VOLUME-FLOW | Inlet volume flow |
| `Output\TOC` | TEMPERATURE | Outlet temperature |
| `Output\NPSH-AVAIL` | HEAD | NPSH available ([pump-npsh.md](pump-npsh.md)) |

More: [performance curves](pump-curves.md), [shaft speed and scaling](pump-speed.md), [NPSH and specific speeds](pump-npsh.md), [flash options and vapor check](pump-flash-options.md).

Not covered: User subroutines (user Fortran subroutines); User curves (user curve subroutines (`OPT_CFORMAT=USER-CURVES`), user Fortran).
