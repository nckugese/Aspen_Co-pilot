# CFuge: disc stack

`TYPE` = `DISC`. Paths are under `\Data\Blocks\{name}\`; basics in [cfuge.md](cfuge.md).

Only `SCHUBERT` uses the disc geometry; the other models run on `WETNESS` (and a cut size).

## Classification

| Path | Type | Purpose |
|---|---|---|
| `Input\DISC_SEDIM` | `IDEAL-SEP`, `IDEAL-CLASS`, `SQ-FUN-CLASS`, `SCHUBERT` | Settling model: all solids to the cake, sharp cut, linear cut, or channel settling between the discs |
| `Input\CUT_SIZE` | LENGTH | Cut size |
| `Input\BOUND_SIZE` | LENGTH | Size above which every particle settles (`SQ-FUN-CLASS`) |
| `Input\SHARPNESS` | real | Sharpness of the cut (`SCHUBERT`) |
| `Input\CHAN_FAC` | real | `SCHUBERT`: correction for settling in the channels |
| `Input\CHAN_IN_FAC` | real | `SCHUBERT`: correction for settling at the channel inlets |
| `Input\ARATIO_FAC` | real | `SCHUBERT`: area ratio correction |

## Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\NUM_DISC` | int | Number of discs |
| `Input\DISC_ANGLE` | deg | Disc angle |
| `Input\OUT_RAD` | LENGTH | Outer disc radius |
| `Input\IN_RAD` | LENGTH | Inner disc radius |
| `Input\CHAN_HEIGHT` | LENGTH | Gap between two discs |
| `Input\DISC_SPEED` | FREQUENCY | Rotor speed |

## Deliquoring

| Path | Type | Purpose |
|---|---|---|
| `Input\DISC_DELIQ` | `SPEC-RM` | Cake moisture model: the only one is a fixed `WETNESS` |
