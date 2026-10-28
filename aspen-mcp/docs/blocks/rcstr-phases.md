# RCSTR phases and phase-based sizing

Paths are under `\Data\Blocks\{name}\`. `NPHASE` 2 lets vapor and liquid coexist in the tank; 3 adds a second liquid.

The phase-based size specs need `NPHASE` 2 or 3 and `SPEC_PHASE`; their phase value then belongs to that phase.

`RES-TIME-PH-VOL-FRAC` needs a volume estimate `VOL_EST` ([rcstr-convergence.md](rcstr-convergence.md)) to converge.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_TYPE` | `TOT-VOL-PH-VOL`, `TOT-VOL-PH-VOL-FRAC`, `TOT-VOL-PH-RES-TIME`, `RES-TIME-PH-VOL-FRAC`, `PH-RES-TIME-PH-VOL-FRAC` | Size by total volume or residence time plus one phase's volume, volume share or residence time |
| `Input\SPEC_PHASE` | `CONDENSED`, `VAPOR` | Phase the phase spec refers to |
| `Input\REACT_VOL` | VOLUME | Volume of that phase |
| `Input\REACT_VOL_FR` | fraction | Share of the volume taken by that phase |
| `Input\PH_RES_TIME` | TIME | Time that phase spends in the tank |

## Setup | Streams

More than one stream on `P(OUT)`: give each its phase.

| Path | Type | Purpose |
|---|---|---|
| `Input\PROD_PHASE\{stream}` | `V`, `L` | Phase leaving in that product stream |

## Three phases

| Path | Type | Purpose |
|---|---|---|
| `Input\COMP_LIST\{row}` | component ID | Key component that marks the second liquid (unlabelled rows) |
| `Input\L2_CUTOFF` | fraction | Key-component share above which a liquid counts as the second one |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\VAP_VOL` | VOLUME | Vapor volume |
| `Output\LIQ_VOL` | VOLUME | Liquid volume |
| `Output\VAP_RES_TIME` | TIME | Vapor residence time |
| `Output\COND_RES_TIM` | TIME | Time the liquid stays in the tank |
| `Output\LIQ1_VOL` | VOLUME | First-liquid volume |
