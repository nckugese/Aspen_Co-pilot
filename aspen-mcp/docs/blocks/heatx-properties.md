# HeatX per-side thermodynamics and allowed phases

Paths are under `\Data\Blocks\{name}\`. HeatX takes property settings per side in place of the block-wide ones in common.md.

## Block Options | Properties

Hot-side fields start with `H`, cold-side fields with `C`.

| Path | Type | Purpose |
|---|---|---|
| `Input\HOPSET` | method name | Property method of the hot side (`COPSET` cold) |
| `Input\HHENRY_COMPS` | ID | Henry-components list of the hot side |
| `Input\HCHEMISTRY` | ID | Chemistry of the hot side |
| `Input\HTRUE_COMPS` | `YES`, `NO` | Electrolytes as true species on the hot side |
| `Input\HFREE_WATER` | `STEAM-TA`, `IAPWS-95`, `IF97`, `IDEAL` | Water-phase method of the hot side |
| `Input\HSOLU_WATER` | `0`, `1`, `2`, `3`, `4`, `5` | Water solubility method of the hot side |

## Setup | Streams (valid phases)

| Path | Type | Purpose |
|---|---|---|
| `Input\HOT_PHASE\{stream}` | `V`, `L`, `L1`, `L2`, `W`, `VL`, `VL1`, `LW` | Phases the hot side may form; keyed by the hot outlet stream |
| `Input\COLD_PHASE\{stream}` | `V`, `L`, `L1`, `L2`, `W`, `VL`, `VL1`, `LW` | Same for the cold side, keyed by the cold outlet stream |
