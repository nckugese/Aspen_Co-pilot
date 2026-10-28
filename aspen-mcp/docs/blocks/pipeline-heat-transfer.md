# Pipeline heat transfer

Paths are under `\Data\Blocks\{name}\`. `THERMAL` picks how the fluid temperature is found.

`THERMAL=NO` with `CONSTANT` holds the inlet temperature (the feed's, or `T_INLET`) along the line.

| Path | Type | Purpose |
|---|---|---|
| `Input\THERMAL` | `NO`, `YES` | Temperature profile given, or found from heat exchange with the surroundings |
| `Input\TPROFILE` | `CONSTANT`, `LINEAR` | Given profile: one temperature, or a value at each node (`THERMAL=NO`) |
| `Input\IN_TEMPS\{seg}` | TEMPERATURE | Given temperature where the segment starts (`LINEAR`) |
| `Input\OUT_TEMPS\{seg}` | TEMPERATURE | Given temperature where the segment ends (`LINEAR`) |

With `LINEAR` the outlet temperature is the last segment's `OUT_TEMPS`.

## THERMAL=YES (per segment)

Give either the ambient temperatures with `UVAL`, or `HEATFLUX`.

| Path | Type | Purpose |
|---|---|---|
| `Input\IN_TAMB\{seg}` | TEMPERATURE | Surroundings temperature at the segment inlet |
| `Input\OUT_TAMB\{seg}` | TEMPERATURE | Surroundings temperature at the segment outlet |
| `Input\UVAL\{seg}` | HEAT-TRANS-C | U value between the pipe contents and the surroundings |
| `Input\HEATFLUX\{seg}` | HEAT-FLUX | Heat added per length of pipe (negative: removed), e.g. `Watt/m` |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP_OUT` | TEMPERATURE | Outlet temperature |
| `Output\ENTH_BAL` | ENTHALPY-FLO | Heat exchanged over the line (negative: lost) |
| `Output\IN_TEMP\{node}` | TEMPERATURE | Fluid temperature at each node |
| `Output\TAMBIENT\{node}` | TEMPERATURE | Surroundings temperature at each node |
