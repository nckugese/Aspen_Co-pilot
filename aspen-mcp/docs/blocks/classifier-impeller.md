# Classifier: impeller wheels

`METHOD` = `SIFTER` with `TYPE` `IMP-SHORTCUT` or `IMP-HUSEMANN`; pressure drop and the shared sifter inputs are in [sifters](classifier-sifter.md). Paths are under `\Data\Blocks\{name}\`.

`IMP-SHORTCUT`: keep wheel height over radius between 1 and 2; outside that range the run warns.

`IMP-HUSEMANN` needs the blade, discharge and model fields and `STD_FLOW`, but no `SIFT_INP` or `SHARPNESS`. It also needs the wheel height, radius and speed, which the input check does not ask for: without them the run does not start.

## Wheel

| Path | Type | Purpose |
|---|---|---|
| `Input\WHEEL_HEIGHT` | LENGTH | Wheel height |
| `Input\WHEEL_RADIUS` | LENGTH | Wheel radius |
| `Input\WHEEL_SPEED` | INVERSE-TIME | Wheel speed (write it in `1/min` for rpm) |

## Husemann model

| Path | Type | Purpose |
|---|---|---|
| `Input\BLADE_DIST` | LENGTH | Gap between the deflecting blades |
| `Input\BLADE_WIDTH` | LENGTH | Blade width |
| `Input\CRS_DIS_RAD` | LENGTH | Radius of the coarse discharge |
| `Input\FNS_DIS_RAD` | LENGTH | Radius of the fines discharge |
| `Input\HUSEMANN_A` | real | Model parameter A |
| `Input\HUSEMANN_B` | LENGTH | Model parameter B |
| `Input\HUSEMANN_K1` | real | Model factor K1 (default 1) |
| `Input\STD_FLOW` | MASS-FLOW | Reference solids throughput |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\VELOCITY2` | VELOCITY | Cut velocity found |
| `Output\EFFICIENCY` | fraction | Share of the feed solids that leave in `S(OUT)` |
