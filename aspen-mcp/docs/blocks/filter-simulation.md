# Filter: simulation parameters

`MODE` = `SIMULATION` (default): the filter size and speed are given, the block computes the cake and the recoveries. Paths are under `\Data\Blocks\{name}\`; basics in [filter.md](filter.md).

## Drum

| Path | Type | Purpose |
|---|---|---|
| `Input\DIAM` | LENGTH | Drum diameter |
| `Input\WIDTH` | LENGTH | Drum width |
| `Input\REVS` | FREQUENCY | Drum speed |
| `Input\ANGDEP_OPT` | `FILT-ANGLE`, `IMM-DEPTH` | Submerged part given as an angle or as a depth |
| `Input\ANGLE` | ANGLE | Filtration angle (default 120 deg) |
| `Input\DEPTH` | LENGTH | Immersion depth of the drum |
| `Input\FDELIQ_ANGLE` | ANGLE | Angle from the end of filtration to cake discharge |
| `Input\NSEG_DRUM` | int | Segments the drum is divided into (default 12) |
| `Input\SOLID_FRAC` | fraction | `BROWNELL`: cake solids content, mass basis |

## Belt

| Path | Type | Purpose |
|---|---|---|
| `Input\BELT_LENGTH` | LENGTH | Belt length |
| `Input\BELT_WIDTH` | LENGTH | Belt width |
| `Input\BELT_SPEED` | VELOCITY | Belt speed |
| `Input\FILT_AFRAC` | fraction | Share of the belt used for filtration |
| `Input\DELIQ_AFRAC` | fraction | Share used for deliquoring |

## Disc

| Path | Type | Purpose |
|---|---|---|
| `Input\DISC_OUT_RAD` | LENGTH | Outer disc radius |
| `Input\DISC_IN_RAD` | LENGTH | Inner disc radius; larger than outer radius minus immersion depth |
| `Input\DISC_DEPTH` | LENGTH | Immersion depth of the discs |
| `Input\NDISC` | int | Number of discs (default 1) |
| `Input\DISC_SPEED` | FREQUENCY | Disc speed |
| `Input\NSEG_DISC` | int | Segments per disc (default 12) |
| `Input\IGN_HSPRES` | `YES`, `NO` | `ALLES` disc: leave out the hydrostatic pressure of the trough |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\PDROP_CALC` | PDROP | `BROWNELL`: pressure difference used |
| `Output\VILT_VFLOW` | VOLUME-FLOW | Filtrate volume flow |
