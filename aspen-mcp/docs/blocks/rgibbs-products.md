# RGibbs products, inerts and outlet streams

Paths are under `\Data\Blocks\{name}\`.

## Setup | Products

| Path | Type | Purpose |
|---|---|---|
| `Input\PROD_SPEC` | `SYSTEM`, `PRODUCTS`, `PHASES` | Candidate products: every component, only the listed ones, or listed phase by phase |

1. `PRODUCTS`: `insert_row` on `Input\PHASE`, label the row with the component, then write its phase code.

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASE\{comp}` | `V`, `L`, `S`, `SS` | Phase that product may take: vapor, liquid, solid solution, a pure single solid |

A component left off the `PRODUCTS` list is not formed: without `CO2` on it the reformer makes none.

A conventional component such as graphite becomes a solid product only when listed with `SS`; typed `SOLID` in a CISOLID substream it is a candidate without any list, and the carbon leaves in that substream.

| Path | Type | Purpose |
|---|---|---|
| `Input\MERGE_SOLIDS` | `NO`, `YES` | With several CISOLID substreams, send all solid products to the first one |

1. `PHASES`: `insert_row` on `Input\PHASE_KODE` labelled with the phase number (1, 2, ...) and write its code; rows of `COMP_SPEC` and `COMPS` with that number appear with it.
2. With `COMP_SPEC` `LIST`, `insert_row` on `Input\COMPS\{n}` once per component and write the IDs to `#0`, `#1`, ...

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASE_KODE\{n}` | `V`, `L`, `S`, `SS` | Kind of phase n |
| `Input\COMP_SPEC\{n}` | `ALL`, `LIST` | Every component may be in phase n, or only those listed |
| `Input\COMPS\{n}\{row}` | component | A component allowed in phase n |

## Setup | Inerts

A row: `insert_row` on the list labelled with the component.

| Path | Type | Purpose |
|---|---|---|
| `Input\FLOW\{comp}` | MOLE-FLOW | Feed flow of that component kept out of the equilibrium |
| `Input\FRAC\{comp}` | fraction | Same, as a fraction of its feed flow |

The inert part leaves unchanged: 2 kmol/hr of inert methane comes out as 2.0 kmol/hr.

## Setup | Assign Streams

| Path | Type | Purpose |
|---|---|---|
| `Input\ASSIGN_PH` | `INTERNAL`, `KEY-COMPS` | Phases placed in the outlets by RGibbs, or by key components |

1. `insert_row` on `Input\KEY_CID` labelled with an outlet stream; a `CUTOFF` row for that stream comes with it.
2. `insert_row` on `Input\KEY_CID\{stream}` and write the key component to `#0` (more rows, more keys).
3. Write `CUTOFF\{stream}`: without it the input stays incomplete and the run does not start.

| Path | Type | Purpose |
|---|---|---|
| `Input\KEY_CID\{stream}\{row}` | component | Key component of that outlet |
| `Input\CUTOFF\{stream}` | fraction | Least mole fraction of the keys a phase needs to go to that outlet |

Keys override the internal order: with only the first outlet keyed on `H2O`, it takes the condensed water and the outlet without keys takes the gas.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\SOL_FLOW\{comp}` | MOLE-FLOW | Flow of each pure solid formed |
