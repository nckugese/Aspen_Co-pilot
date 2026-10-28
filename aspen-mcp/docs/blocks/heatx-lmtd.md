# HeatX LMTD correction

Paths are under `\Data\Blocks\{name}\`. The factor applied to the log-mean temperature difference.

## Setup | LMTD

| Path | Type | Purpose |
|---|---|---|
| `Input\F_OPTION` | `CONSTANT`, `CALCULATED`, `GEOMETRY` | Constant, calculated from the flow arrangement, or from the geometry (`MODE=DETAILED`) |
| `Input\LMTD_CORRECT` | ratio | Constant correction factor |

With `F_OPTION=CONSTANT` the run uses `LMTD_CORRECT` as the factor.

| Path | Type | Purpose |
|---|---|---|
| `Input\FT_MIN` | ratio | Smallest factor allowed |
| `Input\MAX_NSHELLS` | real | Upper limit on shells for `TYPE=CALC-NSHELLS` |
| `Input\MIN_FLS_PTS` | int | Fewest flash points along the exchanger |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\HX_FMTD` | ratio | Correction factor used |
| `Output\HX_DTLM` | DELTA-T | Corrected LMTD |
