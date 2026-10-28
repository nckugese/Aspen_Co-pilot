# Flash3

Flash to one vapor and two liquid phases at the conditions given. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `V(OUT)` vapor, `L1(OUT)` first liquid, `L2(OUT)` second liquid, `HS(IN)` / `HS(OUT)` heat streams.

To run it needs `SPEC_OPT` and the two values that code names; a fresh block has `SPEC_OPT` `TP`.

Writing a value does not change `SPEC_OPT`: set the code yourself (e.g. `PV` before `PRES` and `VFRAC`).

Values that the code does not name are kept but not used.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_OPT` | `TP`, `TV`, `PV`, `TD`, `PD`, `PQ`, `TQ` | Which two specs: `T` temperature, `P` pressure, `V` vapor fraction, `D` duty; `Q` the duty of the heat stream on `HS(IN)` |
| `Input\TEMP` | TEMPERATURE | Temperature |
| `Input\PRES` | PRESSURE | Pressure; a negative value is a drop from the feed pressure |
| `Input\VFRAC` | fraction | Vapor fraction (molar) |
| `Input\DUTY` | ENTHALPY-FLO | Heat added (negative removes heat) |

`PRES` -0.1 bar gives an outlet 0.1 bar below the feed.

For `PQ` / `TQ` the duty comes from a heat stream:

1. Place a stream of type `HEAT` and connect it to `HS(IN)`; until then the block is incomplete.
2. Write its duty in `\Data\Streams\{heat}\Input\DUTY`.

`PQ` with a 100 kW heat stream gives the same result as `PD` with `DUTY` 100 kW.

A heat stream on `HS(OUT)` carries the block duty with the sign reversed.

## Input | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\T_EST` | TEMPERATURE | Starting guess for the temperature when it is not specified |
| `Input\P_EST` | PRESSURE | Starting guess for the pressure when it is not specified |
| `Input\MAXIT` | int | Flash iteration limit (default 30) |
| `Input\TOL` | tolerance | Flash tolerance (default 1e-4) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
| `Output\B_VFRAC` | fraction | Vapor fraction |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\LIQ_RATIO` | fraction | First liquid over total liquid (molar) |
| `Output\Y\{comp}` | mole fraction | Vapor composition (`X1`, `X2`: first and second liquid) |
| `Output\K1\{comp}` | number | K-value vapor over first liquid (`K2`: over second liquid) |

More: [key component](flash3-key-components.md), [entrainment](flash3-entrainment.md), [heating curves](flash3-hcurves.md).

Not covered: Dynamics (Aspen Dynamics only).
