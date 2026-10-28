# BatchOp heat transfer

Paths are under `\Data\Blocks\{name}\`. Jacket and coils with `HTRANMODE` `RIGOROUS` (Heat Transfer form); the vessel size is in [batchop-geometry.md](batchop-geometry.md).

1. Set `HTRANMODE` to `RIGOROUS` and give the vessel size; without it the integration fails.
2. Switch each device on (1) or off (0) and give every device that is on its medium: the cooling jacket is on by default, and without `JKCOLMEDT` the run fails.

`TYPE` is not used in this mode: the pot follows the media (same result with and without `T-SPEC` 80 C).

With heating and cooling both on, the initial mode picks the one that acts: 1 heating, 0 cooling (default).

## Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\JKHETMODE` | int | Heating jacket on (1) / off (0) |
| `Input\JKCOLMODE` | int | Cooling jacket on / off (default 1) |
| `Input\JKINITMODE` | int | Jacket mode at the start: 1 heating, 0 cooling |
| `Input\COIHETMODE` | int | Heating coils on / off |
| `Input\COICOLMODE` | int | Cooling coils on / off |
| `Input\COIINITMODE` | int | Coil mode at the start: 1 heating, 0 cooling |
| `Input\COIHEATAREA` | AREA | Coil area |

## Jacket heating (`JKHET...`; heating coils use the same names with `COIHET...`)

| Path | Type | Purpose |
|---|---|---|
| `Input\JKHETOPT` | `TEMP`, `LMTD`, `STEAM` | Medium at a fixed temperature, medium inlet and flow, or steam |
| `Input\JKHETMEDT` | TEMPERATURE | Medium temperature (`TEMP`) |
| `Input\JKHETMTI` | TEMPERATURE | Medium inlet temperature (`LMTD`) |
| `Input\JKHETFLW` | MASS-FLOW | Medium flow (`LMTD`) |
| `Input\JKHETCP` | MASS-HEAT-CA | Medium heat capacity (`LMTD`; default water) |
| `Input\JKHETOPSTM` | `PRESSURE`, `TEMPERATURE` | Steam given by pressure or by temperature (`STEAM`) |
| `Input\JKHETPRES` | PRESSURE | Steam pressure |
| `Input\JKHETTEMP` | TEMPERATURE | Steam temperature |
| `Input\JKHETOPTUA` | `OVERALL`, `FILM` | Overall coefficient, or medium-side film plus pot-side film |
| `Input\JKHETUA` | HEAT-TRANS-C | Overall coefficient (default 0.5 kW/sqm-K) |
| `Input\JKHETFILMCO` | HEAT-TRANS-C | Jacket-medium film value (`FILM`) |
| `Input\COIHETMEDT` | TEMPERATURE | Coil medium temperature |

## Jacket cooling (`JKCOL...`; cooling coils `COICOL...`)

| Path | Type | Purpose |
|---|---|---|
| `Input\JKCOLOPT` | `TEMP`, `LMTD` | Medium at a fixed temperature, or medium inlet and flow |
| `Input\JKCOLMEDT` | TEMPERATURE | Cooling medium temperature (`TEMP`) |

## Pot side, heat loss, wall heat capacity

| Path | Type | Purpose |
|---|---|---|
| `Input\FILMHTCOPT` | `FIXED`, `CORRELATION` | Pot-side film coefficient given, or from the agitator ([batchop-geometry.md](batchop-geometry.md)) |
| `Input\POTFILMCOEF` | HEAT-TRANS-C | Film value inside the pot (`FIXED`) |
| `Input\OPTENVLOSS` | int | Heat loss to the surroundings on (1) |
| `Input\UAENV` | HEAT-TRANS-C | Loss coefficient |
| `Input\TAMBIENT` | TEMPERATURE | Ambient temperature (default 20 C) |
| `Input\OPTHEATCP` | int | Wall heat capacity on (1) |
| `Input\MASSPOTMAT` | MASS | Wall mass |
| `Input\POTHEATCP` | MASS-HEAT-CA | Wall heat capacity |
