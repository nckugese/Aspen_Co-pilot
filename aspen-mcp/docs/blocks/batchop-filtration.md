# BatchOp filtration

Paths are under `\Data\Blocks\{name}\`. A filter that takes liquid out of a slurry through `FT(OUT)` during the batch (Setup | Filtration). `{stream}` is the `FT(OUT)` stream.

1. Connect a stream to `FT(OUT)` and set `FILTER` to `YES`.
2. Give the area and pressure drop for that stream and the cake and medium resistances.

| Path | Type | Purpose |
|---|---|---|
| `Input\FILTER` | `NO`, `YES` | Filtrate flows from time 0 (`YES`) |
| `Input\FILTAREA\{stream}` | AREA | Filter area |
| `Input\PDROP\{stream}` | PDROP | Driving pressure difference over the filter |
| `Input\CAKE_RES` | INVERSE-AREA | Specific cake resistance |
| `Input\MEDIUM_RES` | FILTER-RESIS | Filter medium resistance |
| `Input\POROSITY` | fraction | Cake porosity |

`FT(OUT)` shows the filtrate rate at the end, and the filtrate leaves the pot: 1 sqm took most of the water out in 2 hr (`RP(OUT)` mixed flow 16.6 of 50 kmol/hr), 0.01 sqm hardly any (49.6).
