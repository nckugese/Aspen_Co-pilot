# Compr calculation options

Paths are under `\Data\Blocks\{name}\`.

`SPEC_TEMP=YES` with `TEMP` fixes the outlet temperature and the block works out the efficiency; this holds for the polytropic and positive-displacement types. With an isentropic type `TEMP` is ignored.

A suction nozzle (`SUCT_NOZ_DIA`, `SUCT_K_FACT`) lowers the pressure the compression starts from (`Output\IN_PRES`).

## Setup | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_TEMP` | `NO`, `YES` | Give the outlet temperature and compute the efficiency |
| `Input\TEMP` | TEMPERATURE | Outlet temperature for `SPEC_TEMP=YES` |
| `Input\CPR_METHOD` | `RIGOROUS`, `APPROXIMATE` | How the heat-capacity ratio is found |
| `Input\GPSA_BASIS` | `SUCTION`, `AVERAGE` | GPSA types: properties at suction or averaged over inlet and outlet |
| `Input\CLFR` | fraction | Clearance fraction, positive-displacement types |
| `Input\DEWPOINT_CHK` | `NONE`, `INFORMATION`, `WARNING`, `ERROR` | What to report when the inlet is near its dew point |
| `Input\DEWPOINT_TOL` | real | Margin used by that dew-point check |
| `Input\SUCT_NOZ_DIA` | LENGTH | Suction nozzle diameter |
| `Input\SUCT_K_FACT` | real | Suction nozzle loss coefficient (K) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\IN_CPR` | ratio | Cp/Cv at the inlet |
| `Output\IN_PRES` | PRESSURE | Pressure after the suction nozzle |
| `Output\EV` | fraction | Volumetric efficiency (positive displacement) |
| `Output\DIS` | VOLUME-FLOW | Displacement (positive displacement) |
