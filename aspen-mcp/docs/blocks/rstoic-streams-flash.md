# RStoic streams, heat streams and flash options

Paths are under `\Data\Blocks\{name}\`. After the reactions a flash at the outlet specs splits the product into phases ([rstoic.md](rstoic.md)).

## Setup | Streams

More than one stream on `P(OUT)`: give each the phase it takes.

| Path | Type | Purpose |
|---|---|---|
| `Input\PROD_PHASE\{stream}` | `V`, `L`, `L1`, `L2`, `W`, `VL`, `VL1`, `LW` | Phase leaving in that product stream (`W` free water) |

`L1`, `L2` and `VL1` need `NPHASE` 3; `W`, `VL` and `LW` need `BLKOPFREWAT` `YES`.

## Heat streams

A heat stream on `HS(IN)` counts against the duty: `QNET` is `QCALC` less the inlet duty, and a heat stream on `HS(OUT)` carries `QNET` away.

| Path | Type | Purpose |
|---|---|---|
| `Output\QNET` | ENTHALPY-FLO | Net duty after the inlet heat stream |

## Setup | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Outlet flash iteration limit (default 30) |
| `Input\TOL` | real | Outlet flash tolerance (default 1e-4) |
| `Input\T_EST` | TEMPERATURE | Starting guess for the outlet temperature (specs without T) |
| `Input\P_EST` | PRESSURE | Starting guess for the outlet pressure (specs without P) |
| `Input\BLKOPFREWAT` | `NO`, `YES` | Free-water phase in the outlet flash |

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature found |
