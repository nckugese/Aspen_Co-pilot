# Filter: deliquoring

How far the cake drains after filtration, for `GENERAL`, `HOLDICH` and `ALLES` (not `BROWNELL`, not `SOLIDS-SEP`). Paths are under `\Data\Blocks\{name}\`; basics in [filter.md](filter.md).

## Model

| Path | Type | Purpose |
|---|---|---|
| `Input\DELIQ_MODEL` | `SCHUBERT`, `NICOLAOU` | Drainage curve of the cake |
| `Input\REM_SAT` | fraction | Saturation that cannot be drained |
| `Input\SCHUBERT_N` | real | `SCHUBERT`: curve exponent (required) |
| `Input\NICOLAOU_A` | real | `NICOLAOU`: curve parameter A; also B, C |
| `Input\NICOLAOU_B` | real | `NICOLAOU`: curve parameter B |
| `Input\NICOLAOU_C` | real | `NICOLAOU`: curve parameter C |
| `Input\CAPRWET_OPT` | `CAP-PRES1`, `WET-ANGLE1` | Entry pressure of the cake given directly, or from a wetting angle |
| `Input\CAP_PRES` | PRESSURE | Capillary entry pressure of the cake |
| `Input\WET_ANGLE` | ANGLE | Wetting angle of the liquid on the solids |

## Gas

A gas stream on `F2(IN)` (type `GAS-IN`) and an outlet on `P2(OUT)` (type `DEQ-OUT`) blow the cake; on a drum `DELIQ_ANGLE` is then required.

| Path | Type | Purpose |
|---|---|---|
| `Input\DELIQ_ANGLE` | ANGLE | Drum: angle over which gas flows through the cake |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\CAKE_SAT_C` | fraction | Cake saturation at discharge |
| `Output\CAP_PRES_C` | PRESSURE | Capillary entry pressure used |
