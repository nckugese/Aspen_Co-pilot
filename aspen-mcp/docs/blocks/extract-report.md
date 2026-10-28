# Extract report and pseudo streams

Paths are under `\Data\Blocks\{name}\`.

## Report

| Path | Type | Purpose |
|---|---|---|
| `Input\TRAY_OPTION` | `BRIEF`, `INCL-TRAYS`, `ALL-TRAYS` | Which stages the report lists |
| `Input\INC_TRAY2\{row}` | int | A stage to list (`INCL-TRAYS`), unlabelled rows |
| `Input\FORMAT` | `PROFILE`, `STAGE`, `COMBINED` | Layout of the stage report |
| `Input\ORDER` | `TOP-DOWN`, `BOTTOM-UP` | Order of the stages |
| `Input\PROFILE` | `PROFILE`, `NOPROFILE` | Stage profiles in the report |
| `Input\COMPS` | `COMPS`, `NOCOMPS` | Composition profiles in the report |
| `Input\ENTH` | `ENTH`, `NOENTH` | Enthalpy profiles in the report |
| `Input\LLRATIO_REP` | `YES`, `NO` | Report the ratio of the two liquid flows per stage |

`LLRATIO_REP=YES` is what fills `Output\LL_RATIO`.

## Pseudo streams

1. Connect a material stream to `PS(OUT)`; its entries, keyed by the stream name, appear then.
2. Set its stage and liquid; without a flow it takes the whole liquid leaving that stage.

| Path | Type | Purpose |
|---|---|---|
| `Input\PSEUDO_STAGE\{ps}` | int | Stage the pseudo stream copies |
| `Input\PSEUDO_PHASE\{ps}` | `L1`, `L2` | Liquid copied |
| `Input\PSEUDO_FLOW\{ps}` | MOLE-FLOW | Molar flow drawn into the pseudo stream |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\LL_RATIO\{stage}` | ratio | 2nd over 1st liquid flow on a stage |
