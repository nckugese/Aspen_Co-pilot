# MHeatX

Multistream heat exchanger: any number of hot and cold streams in one energy balance. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `HF(IN)` hot inlets, `CF(IN)` cold inlets, `HP(OUT)` hot outlets, `CP(OUT)` cold outlets, `HLF(IN)`/`CLF(IN)` and `HLP(OUT)`/`CLP(OUT)` heat streams (material streams are refused there), `HWD(OUT)`/`CWD(OUT)` free-water decants. Several streams may share a port.

Every Specifications field is keyed by the inlet stream ID. A stream on `HF(IN)` starts on the `HOT` side, one on `CF(IN)` on `COLD`.

1. Connect the inlets and outlets.
2. Pair each inlet with its outlet: write the outlet ID to `OUT\{inlet}`. Connecting does not do it, and the run does not start without it.
3. Give every stream but one a `SPEC` and then its `VALUE` (`VALUE` opens once `SPEC` is set). The stream left open closes the energy balance.

With every stream specified, or two left open, the run does not start.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\OUT\{stream}` | stream ID | Outlet paired with this inlet |
| `Input\SIDE\{stream}` | `HOT`, `COLD` | Which side this inlet belongs to |
| `Input\SPEC\{stream}` | `TEMP`, `VFRAC`, `DELT`, `DEGSUP`, `DEGSUB`, `DUTY`, `MOLAR-Q`, `MASS-Q` | Outlet spec type: temperature, vapor fraction, temperature change, superheat, subcooling, duty, duty per mole, duty per mass |
| `Input\VALUE\{stream}` | number | Spec value, in the unit `SPECUN` names |
| `Input\SPECUN\{stream}` | unit text | Unit of `VALUE`, e.g. `F` or `kW`; empty means the global unit set's |
| `Input\PRES\{stream}` | PRESSURE | Outlet pressure when > 0; a drop when 0 or less |
| `Input\NPHASE\{stream}` | `1`, `2`, `3` | Phases checked in the stream's flashes |
| `Input\PHASE\{stream}` | `V`, `L` | The one phase when `NPHASE` is 1 |
| `Input\Q_EST\{stream}` | ENTHALPY-FLO | Duty estimate |

`PRES` checked in a run: a drop of 0.5 bar on the 5 atm hot stream and an outlet of 2 bar on the cold one.

Hot-side duties and temperature changes are negative: a positive `DELT` or `DUTY` on a hot stream is refused.

A unit passed with `set_value` on `VALUE` is ignored (`SPECUN` keeps its unit); write `SPECUN` instead.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP\{stream}` | TEMPERATURE | Temperature leaving, per inlet |
| `Output\B_PRES\{stream}` | PRESSURE | Outlet pressure |
| `Output\B_VFRAC\{stream}` | fraction | Outlet vapor fraction |
| `Output\IN_TEMP\{stream}` | TEMPERATURE | Inlet temperature |
| `Output\QCALC\{stream}` | ENTHALPY-FLO | Duty of the stream (hot negative) |
| `Output\QCALC2` | ENTHALPY-FLO | Exchanger duty |

More: [zone analysis, UA and approach](mheatx-zone-analysis.md), [heat leak, convergence, report](mheatx-options.md), [heating curves](mheatx-hcurves.md), [per-stream properties](mheatx-properties.md).

Not covered: Dynamics (Aspen Dynamics only); Heat (load) streams (a heat stream on `HLF(IN)`/`CLF(IN)` without a T-Q profile ends in a warning, its duty counted as leak; not checked further); Free water and decants (free-water phase and the `HWD(OUT)`/`CWD(OUT)` decants, not checked).
