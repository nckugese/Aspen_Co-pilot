# HXFlux

Heat transfer between a hot side and a cold side that are given only by temperatures: convective (duty = U x area x LMTD) or a furnace radiant section ([radiant](hxflux-radiant.md)). Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: only `HS(IN)` and `HS(OUT)` for heat streams ([links](hxflux-streams.md)); it needs no material stream.

To run it needs both inlet temperatures, `THOT_IN` and `TCOLD_IN`, plus four of `THOT_OUT`, `TCOLD_OUT`, `DUTY`, `U` and `AREA`; the one left blank is computed.

A fifth of those is refused: clear one (write `""`) before setting another.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\THOT_IN` | TEMPERATURE | Temperature where the hot side enters |
| `Input\THOT_OUT` | TEMPERATURE | Temperature where the hot side leaves |
| `Input\TCOLD_IN` | TEMPERATURE | Temperature where the cold side enters |
| `Input\TCOLD_OUT` | TEMPERATURE | Temperature where the cold side leaves |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty |
| `Input\U` | HEAT-TRANS-C | U, overall coefficient from hot to cold side |
| `Input\AREA` | AREA | Heat transfer area |
| `Input\LMTD_CORR` | real | Factor applied to the LMTD (default 1) |
| `Input\FLOW_DIR` | `COUNTERCURRE`, `COCURRENT` | Counter-current (default) or co-current flow |

## Input | Heat Transfer Options

| Path | Type | Purpose |
|---|---|---|
| `Input\HEAT_TR_MODE` | `CONVECTIVE`, `RADIANT` | Convective exchange, or a furnace radiant section ([radiant](hxflux-radiant.md)) |
| `Input\AREA_OPT` | `SPEC`, `IMM-BUNDLE` | Area as `AREA`, or from the liquid level on a tube bundle ([immersed bundle](hxflux-immersed-bundle.md)) |
| `Input\LMTD_METHOD` | `RIGOROUS`, `APPROXIMATE` | How the LMTD is evaluated |

## Input | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Iteration limit when an outlet temperature is computed (default 20) |
| `Input\TOL` | tolerance | Tolerance of that iteration (default 1e-4) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Duty |
| `Output\AREA_CALC` | AREA | Area |
| `Output\U-OVER-COEF` | HEAT-TRANS-C | Overall coefficient |
| `Output\LMTD` | DELTA-T | LMTD the duty is based on |
| `Output\U-LMTD-CORR` | real | LMTD factor used |
| `Output\HOTINT` | TEMPERATURE | Hot inlet temperature |
| `Output\HOT_TEMP` | TEMPERATURE | Hot outlet temperature |
| `Output\IN_TEMP` | TEMPERATURE | Cold inlet temperature |
| `Output\COLD_TEMP` | TEMPERATURE | Cold outlet temperature |

More: [stream and heat-stream links](hxflux-streams.md), [radiant section](hxflux-radiant.md), [immersed tube bundle](hxflux-immersed-bundle.md).

Not covered: EO variables (`OPT_*` = `EO-VARIABLE`, the `*_EO` names and the initial temperatures and duty on Calculation Options: equation-oriented only, not checked); Sequential modular connection (SM_CONN) (not checked); Heating curves, Utility (shared forms that this block's tree does not carry).
