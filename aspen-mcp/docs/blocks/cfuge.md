# CFuge (centrifuge)

Separates a slurry into a liquid stream and a solids cake: a simple solids separator, or a rated decanter, disc stack, pusher or perforated basket centrifuge. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` slurry feed, `L(OUT)` liquid, `P(OUT)` solids cake. Leave `O(OUT)` empty: with a stream on it the block stays incomplete in every type.

The feed needs a solid substream; a working setup is calcite in a `CIPSD` substream (stream class `MIXCIPSD`) with a size distribution, which the classifying models act on.

What each type needs before it can run:

`SOLIDS-SEP`: `PRES` plus the two specs that `PHASEP_OPT` names.

`DECANTER` and `DISC`: only `WETNESS` (their default models are ideal separation and a specified residual moisture); other models need geometry ([decanter](cfuge-decanter.md), [disc](cfuge-disc.md)).

`PUSHER`: the residual moisture of stage 1, `PUSHER_RM\1` ([pusher](cfuge-pusher.md)).

`PERF-BASKET`: one basket row (`DIAM`, `REVS`), `MEDIUM_RES` and a deliquoring spec; with `CAKE_RES` and `DIAM_PART` also set the run ends without warnings ([basket](cfuge-basket.md)).

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `SOLIDS-SEP`, `DECANTER`, `DISC`, `PUSHER`, `PERF-BASKET` | Centrifuge model |
| `Input\PHASEP_OPT` | `SPLP`, `SPLL`, `SPSL`, `LPSL`, `LLSL` | SOLIDS-SEP: which two specs set the split (SP = solids fraction to `P(OUT)`, LP = solids load of the liquid, LL = liquid load of the cake, SL = liquid fraction to `L(OUT)`) |
| `Input\SOLID_SPLIT` | fraction | Share of feed solids sent to `P(OUT)` |
| `Input\FLUID_SPLIT` | fraction | Share of feed liquid sent to `L(OUT)` |
| `Input\SOLID_LOAD` | mass ratio | Solids carried in the liquid outlet, kg per kg |
| `Input\FLUID_LOAD` | mass ratio | Liquid carried in the cake, kg per kg |
| `Input\PRES` | PRESSURE | SOLIDS-SEP outlet pressure |
| `Input\OPT_OPERATE` | `OPT-HEATDU`, `OPT-TEMP`, `OPT-DELT` | SOLIDS-SEP outlet thermal spec: duty (default), temperature or temperature change |
| `Input\DUTY` | ENTHALPY-FLO | Heat duty (default 0, adiabatic) |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\DELT` | DELTA-T | Outlet temperature change |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash |
| `Input\PHASE` | `L`, `V`, `S` | The phase when `NPHASE` is 1 |
| `Input\CLASS_CHAR` | `SIZE`, `VELOCITY` | SOLIDS-SEP: classify the solids by particle size or by settling velocity |
| `Input\SC_SHARP` | real | Sharpness of that classification |
| `Input\FINES_OFFSET` | fraction | Fines that bypass to the cake; smaller than `SOLID_SPLIT` |

## Input | Deliquoring (all rated types)

| Path | Type | Purpose |
|---|---|---|
| `Input\WETNESS` | fraction | Residual moisture of the cake |
| `Input\MOIST_BASIS` | `WET`, `DRY` | Moisture basis: per kg wet cake or per kg dry solids |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\SOLD_RECOV` | fraction | Share of feed solids in the cake |
| `Output\FLUD_RECOV` | fraction | Share of feed liquid in the liquid outlet |
| `Output\SOLD_LOAD` | mass ratio | Liquid carried in the cake, kg per kg |
| `Output\FLUD_LOAD` | mass ratio | Solids carried in the liquid outlet, kg per kg |
| `Output\D50` | LENGTH | Particle size split half and half (classification) |
| `Output\SEP_GRADE` | fraction | Overall separation grade of the solids |
| `Output\RES_MOISTURE` | fraction | Residual moisture of the cake |
| `Output\DRY_CONTENT` | fraction | Dry solids content of the cake |

More: [decanter](cfuge-decanter.md), [disc](cfuge-disc.md), [pusher](cfuge-pusher.md), [perforated basket](cfuge-basket.md).

Not covered: Decanter Redeker deliquoring (the run stops without results); Decanter Schubert deliquoring (stays incomplete with every input tried); Heating curves, Utility (shared forms that this block's tree does not carry).
