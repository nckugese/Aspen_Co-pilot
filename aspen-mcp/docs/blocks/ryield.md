# RYield

Reactor set by product yields alone: no stoichiometry, kinetics or reaction set. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `P(OUT)` products, `HS(IN)` / `HS(OUT)` heat streams ([ryield-streams-flash.md](ryield-streams-flash.md)).

A fresh block has `SPEC_OPT` `TP`, `NPHASE` 2 and `USER_YIELD` `NO` (yields entered per component).

`PQ`, `TQ` and `DTQ` take the duty from a heat stream on `HS(IN)`.

A set `PHASE` blocks `NPHASE` 2 or 3: write `""` to `PHASE` before raising `NPHASE`.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_OPT` | `TP`, `TV`, `PV`, `TD`, `PD`, `PQ`, `TQ`, `DTP`, `DTV`, `DTD`, `DTQ` | The two outlet specs: T temperature, P pressure, V vapor fraction, D duty, Q duty of the inlet heat stream, DT temperature change |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\PRES` | PRESSURE | Outlet pressure (0 or less: drop from the feed) |
| `Input\DUTY` | ENTHALPY-FLO | Heat added (`TD`, `PD`, `DTD`) |
| `Input\VFRAC` | fraction | Outlet vapor fraction (`TV`, `PV`, `DTV`) |
| `Input\DELT` | DELTA-T | Outlet minus feed temperature (`DT...`) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases the outlet flash considers |
| `Input\PHASE` | `L`, `V` | The single phase when `NPHASE` is 1 |

## Setup | Yield

1. Connect the feed to `F(IN)` first.
2. For each product component: `insert_row` on `Input\MOLE_YIELD` (it returns the new row's index), then `set_label` (dimension 0) at that index with the component; with the feed connected the substream label `MIXED` (dimension 1) comes by itself.
3. `set_value` on `Input\MOLE_YIELD\{comp}\MIXED`; for a mass yield also write `MASS` to `Input\BASIS\{comp}\MIXED`.

Components labelled before a feed was connected get no substream label: their entries show as `#0`, `#1`, ... and `{comp}\MIXED` is not found; connecting the feed later does not fill it in. Repair, with the feed connected, with `set_label` dimension 1 at every index (0 to the number of components minus 1) with `MIXED`.

Yields are amounts per unit mass of the feed that is not inert; the product is the yields times that mass, and inert components leave unchanged.

Yields that do not account for exactly that mass are scaled to fit, and the block ends with a warning (`BLKSTAT` 2). Mass yields adding up to 1 avoid it; mole yields need the sum of yield times molecular weight to be 1 with Aspen's own molecular weights (yields rounded to 6 decimals already warn).

A feed component with no yield that is not listed as inert is used up.

With `ATOM_BAL_CHK` `YES` (default) yields that do not keep each element's balance end with a warning; `NO` skips that check.

| Path | Type | Purpose |
|---|---|---|
| `Input\USER_YIELD` | `NO`, `NO2` | Component yields, or lump / de-lump rules ([ryield-component-mapping.md](ryield-component-mapping.md)) |
| `Input\MOLE_YIELD\{comp}\MIXED` | real | Yield of a product component (per kg of non-inert feed) |
| `Input\BASIS\{comp}\MIXED` | `MOLE`, `MASS` | Basis of that yield (default `MOLE`): kmol or kg per kg |
| `Input\COMP_LIST\{row}` | component ID | Inert components, carried through untouched (unlabelled rows) |
| `Input\ATOM_BAL_CHK` | `YES`, `NO` | Check the element balance of the yields |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\B_VFRAC` | fraction | Outlet vapor fraction |
| `Output\B_IDELT` | DELTA-T | Temperature change (`DT...` specs) |
| `Output\ATOM\{id}` | symbol | Element of each balance row |
| `Output\AMOLOUT\{id}` | MOLE-FLOW | Element flow out |
| `Output\AMOLIN\{id}` | MOLE-FLOW | Element flow in |

More: [streams, heat streams and flash options](ryield-streams-flash.md), [component mapping (lump / de-lump)](ryield-component-mapping.md).

Not covered: Assay Analysis (petroleum properties of the product, `USER_YIELD` `NO3`; needs assay pseudocomponents, not checked); Dynamics (Aspen Dynamics only); User Subroutine (user Fortran yield subroutine, `USER_YIELD` `YES`); Free water (`BLKOPFREWAT`, not checked); PSD (particle size and component attributes of solids products, not checked).
