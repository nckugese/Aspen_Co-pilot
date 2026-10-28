# MultiFrac report, targeting and pseudo streams

Paths are under `\Data\Blocks\{name}\`.

## Report

| Path | Type | Purpose |
|---|---|---|
| `Input\FORMAT` | `PROFILE`, `STAGE`, `COMBINED` | Layout of the stage profiles in the report |
| `Input\TRAY_OPTION` | `BRIEF`, `INCL-TRAYS`, `ALL-TRAYS` | Which stages are reported |
| `Input\ORDER` | `TOP-DOWN`, `BOTTOM-UP` | Stage order |
| `Input\TR_PROPS\{row}` | ID | Property sets reported per stage (rows without labels) |

## Column targeting

| Path | Type | Purpose |
|---|---|---|
| `Input\TARGET` | `TARGET`, `NOTARGET` | Targeting analysis on or off |
| `Input\KEY_SELECT\{col}` | `K-VALUE`, `SPLIT-FRACTI`, `COMP-PROFILE` | How the key components are picked |

## Pseudo streams (streams on `PS(OUT)`)

| Path | Type | Purpose |
|---|---|---|
| `Input\PSEUDO_COL\{stream}` | int | Column it copies from |
| `Input\PSEUDO_STAGE\{stream}` | int | Stage |
| `Input\PSEUDO_PHASE\{stream}` | `L`, `V` | Phase |
| `Input\BASIS_P_FLOW\{stream}` | MOLE-FLOW | Flow of the copy |
