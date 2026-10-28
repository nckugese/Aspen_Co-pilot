# RCSTR jacket and coil heat transfer

Paths are under `\Data\Blocks\{name}\`. Needs `EQUIP_MODE` = `EQUIP-BASED` ([rcstr-equipment.md](rcstr-equipment.md)). `HTRANMODE` = `RIGOROUS` computes the duty from one jacket or coil; `HEATXMODE` picks it.

With `RIGOROUS` the outlet temperature is computed: the `TEMP` entered is not held.

## Setup

| Path | Type | Purpose |
|---|---|---|
| `Input\HTRANMODE` | `SHORTCUT`, `RIGOROUS` | Duty from the thermal spec, or from the jacket or coil |
| `Input\HEATXMODE` | `JKCOL`, `JKHET`, `COICOL`, `COIHET` | Cooling jacket, heating jacket, cooling coil, heating coil |
| `Input\COIHEATAREA` | AREA | Coil area (coils) |

## Cooling jacket (`JKCOL`)

| Path | Type | Purpose |
|---|---|---|
| `Input\JKCOLOPT` | `TEMP`, `LMTD` | Fixed medium temperature, or medium inlet and flow (log-mean) |
| `Input\JKCOLMEDT` | TEMPERATURE | Medium temperature (`TEMP`) |
| `Input\JKCOLMTI` | TEMPERATURE | Medium inlet temperature (`LMTD`) |
| `Input\JKCOLFLW` | MASS-FLOW | Medium flow (`LMTD`) |
| `Input\JKCOLCP` | MASS-ENTROPY | Medium heat capacity (`LMTD`) |
| `Input\JKCOLUA` | HEAT-TRANS-C | U between the medium and the contents |

## Heating jacket (`JKHET`)

| Path | Type | Purpose |
|---|---|---|
| `Input\JKHETOPT` | `TEMP`, `LMTD`, `STEAM` | Fixed medium temperature, log-mean, or condensing steam |
| `Input\JKHETMEDT` | TEMPERATURE | Medium temperature (`TEMP`) |
| `Input\JKHETOPSTM` | `PRESSURE`, `TEMPERATURE` | Steam given by its pressure or temperature (`STEAM`) |
| `Input\JKHETPRES` | PRESSURE | Steam pressure |
| `Input\JKHETUA` | HEAT-TRANS-C | U between the medium and the contents |

## Coils (`COICOL`, `COIHET`)

The coil fields follow the jacket ones with prefix `COICOL` / `COIHET`: `...OPT`, `...MEDT`, `...UA`.

| Path | Type | Purpose |
|---|---|---|
| `Input\COICOLOPT` | `TEMP`, `LMTD` | Cooling coil medium option |
| `Input\COIHETOPT` | `TEMP`, `LMTD`, `STEAM` | Heating coil medium option |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Duty through the jacket or coil |
| `Output\B_TEMP` | TEMPERATURE | Computed reactor temperature |
