# CFuge: pusher

`TYPE` = `PUSHER`. Stage values are lists keyed by the stage number, `{n}` = 1 for the first stage. Paths are under `\Data\Blocks\{name}\`; basics in [cfuge.md](cfuge.md).

Feed a thick slurry: below 0.3 solids volume fraction at the inlet the run ends with a warning (10 kmol/hr calcite in 30 kmol/hr water is thick enough).

`PLUG-FILM` needs the stage geometry (`PUSHER_DIAM`, `PUSHER_LEN`, `STROKE_LEN`, `PUSH_FREQ`, `PUSH_SPEED`), the friction factors, `SAT_FAC` and `SAT_EXP` of stage 1, `WET_ANGLE` and `BULK_RES`.

## Classification

| Path | Type | Purpose |
|---|---|---|
| `Input\PUSH_CLASS` | `IDEAL-SEP`, `IDEAL-CLASS`, `SQ-FUN-CLASS` | Settling model: all solids to the cake, sharp cut at `CUT_SIZE`, linear cut up to `BOUND_SIZE` |
| `Input\CUT_SIZE` | LENGTH | Cut size |
| `Input\BOUND_SIZE` | LENGTH | Size above which every particle is kept |

## Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\NSTAGE` | int | Count of stages on the pusher |
| `Input\PUSHER_DIAM\{n}` | LENGTH | Inside diameter of this stage's sieve drum |
| `Input\PUSHER_LEN\{n}` | LENGTH | Length of this stage's sieve drum |
| `Input\STROKE_LEN` | LENGTH | Stroke length of the pusher |
| `Input\PUSH_FREQ` | INVERSE-TIME | Strokes per unit time |
| `Input\PUSH_SPEED` | FREQUENCY | Drum speed |
| `Input\SIEVE_FRIC` | real | Friction factor of the cake on the sieve |
| `Input\P_DRUM_FRIC` | real | Friction coefficient, top of the cake against the drum |

## Deliquoring

| Path | Type | Purpose |
|---|---|---|
| `Input\PUSH_DELIQ` | `RM`, `PLUG-FILM` | Cake moisture model: given per stage, or plug and film flow |
| `Input\PUSHER_RM\{n}` | fraction | `RM`: residual moisture after the stage |
| `Input\SAT_FAC\{n}` | real | `PLUG-FILM`: saturation factor of the stage |
| `Input\SAT_EXP\{n}` | real | `PLUG-FILM`: saturation exponent of the stage (not on the form) |
| `Input\CAKE_HEIGHT\{n}` | LENGTH | Cake thickness on this stage |
| `Input\WET_ANGLE` | deg | `PLUG-FILM`: wetting angle |
| `Input\WEDGE_SAT` | fraction | `PLUG-FILM`: saturation of the wedges, computed when blank |
| `Input\BULK_RES` | INVERSE-AREA | `PLUG-FILM`: flow resistance of the bulk cake |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\RES_TIME` | TIME | How long the cake stays in the machine |
| `Output\CAKEHEIGHT1` | LENGTH | Cake height on the first stage |
