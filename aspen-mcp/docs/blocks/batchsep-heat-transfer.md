# BatchSep heat transfer

Paths are under `\Data\Blocks\{name}\`. How the pot is heated (Heat Transfer form). Each device has a prefix: `JH` jacket, `CH` coils, `XH` external exchanger; the fields after it are the same.

## Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\JA_HEATING` | int | 1: jacket heating on (default) |
| `Input\COILSHEATING` | int | 1: coil heating on |
| `Input\EXTHXHEATING` | int | 1: heat with the external exchanger |
| `Input\ACOILS` | AREA | Coil area |
| `Input\AEXTHX` | AREA | External exchanger area |

Switch the jacket off (`JA_HEATING` 0) when another device heats, and change that device's duty in a step with location `CLHEATING` or `XHHEATING`.

## Heating spec (`JH_`, `CH_`, `XH_`)

| Path | Type | Purpose |
|---|---|---|
| `Input\JH_OPT` | `DUTY`, `TEMP`, `LMTD` | Duty, medium temperature, or medium inlet temperature + flow |
| `Input\JH_DUTY` | ENTHALPY-FLO | Duty (`DUTY`) |
| `Input\JH_TMED` | TEMPERATURE | Medium temperature (`TEMP`) |
| `Input\JH_TMEDIN` | TEMPERATURE | Medium inlet temperature (`LMTD`) |
| `Input\JH_FMMED` | MASS-FLOW | Medium flow (`LMTD`) |
| `Input\JH_U` | HEAT-TRANS-C | Overall coefficient (`TEMP`, `LMTD`) |
| `Input\CH_OPT` | `DUTY`, `TEMP`, `LMTD` | Coil spec |
| `Input\CH_DUTY` | ENTHALPY-FLO | Coil duty |
| `Input\XH_OPT` | `DUTY`, `TEMP`, `LMTD` | External exchanger spec |
| `Input\XH_DUTY` | ENTHALPY-FLO | External exchanger duty |

With `TEMP` the duty follows from the medium: the jtemp run distils without any duty given.

Each spec needs its step parameter (location `JKHEATING`, `CLHEATING` or `XHHEATING`): `DUTY`, `MED-TEMP`, or `MED-INL-TEMP` with `MED-MASSFLOW`; without it the pot is not heated.

## Heat loss, heat capacity, side duty

| Path | Type | Purpose |
|---|---|---|
| `Input\HEATLOSS` | int | 1: loss to the surroundings on |
| `Input\POT_UENV` | HEAT-TRANS-C | Pot-to-ambient coefficient |
| `Input\TAMB` | TEMPERATURE | Ambient temperature |
| `Input\HEATCAP` | `FALSE`, `TRUE` | Include the pot wall's heat capacity |
| `Input\POT_MASS` | MASS | Pot metal mass |
| `Input\POT_CP` | MASS-HEAT-CA | Its heat capacity |
| `Input\STG_DUTY\{stage}` | ENTHALPY-FLO | Duty on a stage (Side Duty; negative removes heat) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\MOLEFLMX\MIXED` | MOLE-FLOW | Distillate with the medium at 160 C |
