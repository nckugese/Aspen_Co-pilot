# MHeatX options

Paths are under `\Data\Blocks\{name}\`. Heat leak, the outlet-temperature search and report tables.

## Setup | Options

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_QLEAK` | `QLEAK-FRAC`, `QLEAK` | Heat leak as a fraction of the duty or as an amount |
| `Input\QLEAK_FRAC` | fraction | Leak over exchanger duty |
| `Input\QLEAK` | ENTHALPY-FLO | Leak amount, with `OPT_QLEAK` `QLEAK` |

A positive leak heats the streams: with the hot outlet fixed, the cold stream left open leaves warmer.

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Iteration limit of the outlet-temperature search |
| `Input\TOL` | number | Tolerance of that search |
| `Input\T_LOWER` | TEMPERATURE | Lowest temperature the search tries (`T_UPPER` highest) |
| `Input\TEST` | TEMPERATURE | Starting guess for the search |
| `Input\PROFILE` | `PROFILE`, `NOPROFILE` | Zone profiles in the report |
| `Input\STREAMS` | `STREAMS`, `NOSTREAMS` | Stream profiles in the report |
| `Input\TQTABLES` | `TQTABLES`, `NOTQTABLES` | Add the flash tables to the report |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\QLEAK_OUT` | ENTHALPY-FLO | Heat leak |
