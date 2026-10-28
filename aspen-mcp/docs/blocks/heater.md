# Heater

Heater or cooler: brings one feed to the outlet state set by two specs. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks (utility, block options): [common.md](common.md).

Ports: `F(IN)` feeds, `P(OUT)` product, `WD(OUT)` free-water decant ([heater-phases.md](heater-phases.md)), `HS(IN)` / `HS(OUT)` heat streams.

To run it needs `SPEC_OPT` and the two values that code names; a fresh block has `SPEC_OPT` `TP`.

Writing a value does not change `SPEC_OPT`: set the code yourself (e.g. `PV` before `PRES` and `VFRAC`).

Values that the code does not name are kept but not used.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_OPT` | `TP`, `TV`, `TD`, `TDPPARM`, `PV`, `PD`, `PDT`, `PDEGSUP`, `PDEGSUB`, `VDPPARM`, `DDPPARM`, `DTV`, `DTD`, `DTDPPARM`, `DEGSUPDPPARM`, `DEGSUBDPPARM`, `PQ`, `TQ`, `DTQ`, `DPPARMQ` | Which two specs: `T` temperature, `P` pressure, `V` vapor fraction, `D` duty, `DT` temperature change, `DEGSUP` / `DEGSUB` superheat / subcooling, `DPPARM` drop parameter, `Q` the duty of the heat stream on `HS(IN)` |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\PRES` | PRESSURE | Outlet pressure; a negative value is a drop from the feed pressure |
| `Input\VFRAC` | fraction | Outlet vapor fraction |
| `Input\DUTY` | ENTHALPY-FLO | Heat added (negative removes heat) |
| `Input\DELT` | DELTA-T | Outlet minus feed temperature |
| `Input\DEGSUP` | DELTA-T | Outlet temperature above the dew point |
| `Input\DEGSUB` | DELTA-T | Outlet temperature below the bubble point |
| `Input\DPPARM` | number | Pressure-drop correlation parameter: the drop is proportional to it and to the flow squared |
| `Input\DPPARMOPT` | `NO`, `YES` | `YES`: work out `DPPARM` from the drop a pressure spec gives |

`PRES` -0.1 bar gives an outlet 0.1 bar below the feed.

`DELT` -20 C on a 95 C feed gives 75 C.

`DEGSUP` / `DEGSUB` 10 C give 10 C above the dew point / below the bubble point at the outlet pressure.

Doubling `DPPARM` doubles the drop; doubling the flow makes it four times larger.

With `DPPARMOPT` `YES` the parameter that gives the specified drop is reported in `Output\COR_PDRP_FAC`.

Codes without `P` or `DPPARM` (`TV`, `TD`, `DTV`, `DTD`, `TQ`, `DTQ`) leave the outlet pressure to be found.

For the `Q` codes the duty comes from a heat stream:

1. Place a stream of type `HEAT` and connect it to `HS(IN)`; check_inputs does not flag a `Q` code without one.
2. Write its duty in `\Data\Streams\{heat}\Input\DUTY`.

`PQ` with a 500 kW heat stream gives the same outlet as `PD` with `DUTY` 500 kW.

Connecting a heat stream to `HS(IN)` turns `SPEC_OPT` `TP` into `TQ`: `PRES` is then ignored and the outlet pressure is found (0.2 bar in a 50 C, 50 kW test). Set the code again after connecting.

A heat stream on `HS(OUT)` carries the block duty with the sign reversed.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
| `Output\B_VFRAC` | fraction | Outlet vapor fraction |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\PDROP` | PDROP | Feed minus outlet pressure (negative: the pressure rose) |
| `Output\QNET` | ENTHALPY-FLO | Net duty: the part not given by `DUTY` or a heat stream |
| `Output\Y\{comp}` | mole fraction | Vapor composition (`X`: liquid) |

`QNET` equals `QCALC` for `TP` and is 0 when `DUTY` or a heat stream on `HS(IN)` sets the duty.

More: [valid phases and free water](heater-phases.md), [flash options](heater-flash-options.md), [heating curves](heater-hcurves.md).

Not covered: Dynamics (Aspen Dynamics only).
