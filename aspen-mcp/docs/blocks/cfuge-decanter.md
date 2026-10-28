# CFuge: decanter

`TYPE` = `DECANTER`. Settling in the bowl (classification) and drainage of the cake (deliquoring) each have a model. Paths are under `\Data\Blocks\{name}\`; basics in [cfuge.md](cfuge.md).

`STOKES` and `SIMP-STOKES` need the bowl geometry: `DIAM_DRUM`, `LEN_CYL`, `POND_DEPTH`, `BLADE_PITCH`, `DEC_SPEED` (plus `DEC_DSPEED` for `STOKES`, `SHARPNESS` for `SIMP-STOKES`).

## Classification

| Path | Type | Purpose |
|---|---|---|
| `Input\DEC_SEDIM` | `IDEAL-SEP`, `IDEAL-CLASS`, `SQ-FUN-CLASS`, `STOKES`, `SIMP-STOKES` | Settling model: all solids to the cake, sharp cut at `CUT_SIZE`, linear cut between `CUT_SIZE` and `BOUND_SIZE`, Stokes settling, or Stokes with a sharpness |
| `Input\CUT_SIZE` | LENGTH | Cut size (`IDEAL-CLASS`, `SQ-FUN-CLASS`) |
| `Input\BOUND_SIZE` | LENGTH | Size above which every particle settles (`SQ-FUN-CLASS`) |
| `Input\SHARPNESS` | real | Sharpness of the cut (`SIMP-STOKES`) |

`DRAG_EFFECT` `YES` also needs `CRIT_SIZE`.

| Path | Type | Purpose |
|---|---|---|
| `Input\DRAG_EFFECT` | `YES`, `NO` | Stokes: include drag of the sediment |
| `Input\DRAG_MODEL` | `LANGELOH`, `BRAUER` | Stokes: drag correlation |
| `Input\CONC_EFFECT` | `YES`, `NO` | Stokes: hindered settling at high solids concentration |
| `Input\CRIT_SIZE` | LENGTH | Stokes: critical particle size; required with `DRAG_EFFECT` `YES` |
| `Input\DRAG_FRIC` | real | Stokes: particle-to-sediment friction coefficient |

## Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\DIAM_DRUM` | LENGTH | Bowl diameter |
| `Input\LEN_CYL` | LENGTH | Length of the cylindrical part |
| `Input\CONE_ANGLE` | deg | Angle of the conical beach |
| `Input\DIAM_OUT` | LENGTH | Diameter where the solids leave the bowl; smaller than `DIAM_DRUM` |
| `Input\POND_DEPTH` | LENGTH | Liquid pond depth, below half of `DIAM_DRUM` |
| `Input\BLADE_PITCH` | LENGTH | Pitch of the screw conveyor |
| `Input\DEC_SPEED` | FREQUENCY | Bowl speed |
| `Input\DEC_DSPEED` | FREQUENCY | Speed difference between bowl and screw |

`STAHL` needs `DIAM_DRUM`, `CONE_ANGLE`, `POND_DEPTH` and `DEC_SPEED`.

`STADAGER` also needs `BULK_RES`, `BULK_ANGLE`, `DRUM_FRIC` and `GAP_WIDTH`; a working run also set `SCREW_FRIC` 0.3, `BLADE_ANGLE` 80, `TRANS_ANGLE` 10, `NSCREWSTARTS` 1 and `BEACH_RESTIM` 10 s.

| Path | Type | Purpose |
|---|---|---|
| `Input\BEACH_RESTIM` | TIME | Residence time of the solids on the beach |
| `Input\BULK_RES` | INVERSE-AREA | Flow resistance of the bulk cake |

## Deliquoring

| Path | Type | Purpose |
|---|---|---|
| `Input\DEC_DELIQ` | `SPEC-RM`, `RM-COURSE`, `STAHL`, `STADAGER` | Cake moisture model: fixed `WETNESS`, a moisture course over throughput, or the Stahl or Stadager correlations |
| `Input\RM_SMALL` | fraction | Cake moisture when the throughput is low (`RM-COURSE`, `STAHL`, `STADAGER`) |
| `Input\CRIT_FLOW` | MASS-FLOW | Throughput where the moisture starts to rise |
| `Input\STAHL_F1` | AREA-SQTIME | Stahl model parameter |
| `Input\STADAGER_F2` | real | Stadager model parameter |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\PART_DIAMR` | LENGTH | Mean particle size used by the model |
