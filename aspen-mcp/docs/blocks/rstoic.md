# RStoic

Reactor with given stoichiometry and a conversion or extent per reaction: no kinetics, no reaction set. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `P(OUT)` products, `HS(IN)` / `HS(OUT)` heat streams ([rstoic-streams-flash.md](rstoic-streams-flash.md)).

A fresh block has `SPEC_OPT` `TP`, `NPHASE` 2, `SERIES` `NO`, `HEAT_OF_REAC` `NO-CALC-SPEC` and `COMBUSTION` `NO`.

Reactions are typed into the block's own tables; `add_reaction_set` / `add_reaction` are not used.

`PQ` and `TQ` take the duty from a heat stream on `HS(IN)`.

Fields of another `SPEC_OPT` left set (a `TEMP` under `PD`) are ignored and need not be cleared: the block is not flagged incomplete and the outlet comes from the specs in force.

A set `PHASE` blocks `NPHASE` 2 or 3: write `""` to `PHASE` before raising `NPHASE`.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_OPT` | `TP`, `TV`, `PV`, `TD`, `PD`, `PQ`, `TQ` | Outlet specs: T temperature, P pressure, V vapor fraction, D duty, Q duty of the inlet heat stream |
| `Input\TEMP` | TEMPERATURE | Outlet temperature |
| `Input\PRES` | PRESSURE | Outlet pressure (0 or less: drop from the feed) |
| `Input\DUTY` | ENTHALPY-FLO | Heat added (`TD`, `PD`; 0 for adiabatic) |
| `Input\VFRAC` | fraction | Outlet vapor fraction (`TV`, `PV`) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases the outlet flash considers |
| `Input\PHASE` | `L`, `V` | The single phase when `NPHASE` is 1 |

## Setup | Reactions

1. `insert_row` on `Input\CONV`, then `set_label` that index with the reaction number (`1`, `2`, ...); this creates the reaction's entries in `KEY_CID`, `COEF`, `COEF1`, `OPT_EXT_CONV` and `EXTENT`.
2. `set_label` (dimension 0) at index 0, 1, 2, ... on `Input\COEF\{id}` with each reactant and on `Input\COEF1\{id}` with each product; no `insert_row` is needed, and with the feed connected the substream `MIXED` (dimension 1) comes by itself.
3. `set_value` the coefficients on `...\{id}\{comp}\MIXED`, then `KEY_CID\{id}` and `CONV\{id}` (or `OPT_EXT_CONV\{id}` `EXTENT` and `EXTENT\{id}`).

`KEY_SSID\{id}` (substream of the key component) can stay empty: `MIXED` is used.

Components labelled before a feed was connected get no substream label (`{comp}\MIXED` is not found), and connecting the feed later does not fill it in: with the feed connected, `set_label` dimension 1 at every index of `COEF\{id}` and `COEF1\{id}` (one per component) with `MIXED`.

One component may not sit on both sides of a reaction: the second label is refused.

Conversion is the fraction of the key component's feed that reacts. With `SERIES` `NO` every reaction works on the feed; with `YES` each works on what the reactions before it (by number) leave.

A conversion or extent that needs more of a reactant than there is gets cut back to use it up; the block ends with a warning (`BLKSTAT` 2).

Coefficients that do not keep the mass balance stop the run before the block is solved.

| Path | Type | Purpose |
|---|---|---|
| `Input\CONV\{id}` | fraction | Share of the key component's feed that reacts |
| `Input\KEY_CID\{id}` | component ID | Key component of the reaction |
| `Input\OPT_EXT_CONV\{id}` | `CONVERSION`, `EXTENT` | Reaction given by conversion, or by a fixed extent |
| `Input\EXTENT\{id}` | MOLE-FLOW | Moles of reaction per time, whatever the feed (good inside a recycle) |
| `Input\COEF\{id}\{comp}\MIXED` | real | Reactant coefficient, negative |
| `Input\COEF1\{id}\{comp}\MIXED` | real | Product coefficient, positive |
| `Input\SERIES` | `NO`, `YES` | Reactions together on the feed, or one after another |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\B_VFRAC` | fraction | Outlet vapor fraction |
| `Output\EXTENT_OUT\{id}` | MOLE-FLOW | Extent of each reaction |
| `Output\R_CONV\{id}` | fraction | Conversion of each reaction's key component |
| `Output\REAC_STOI\{id}` | text | Each reaction written out |

More: [reaction heats](rstoic-heat-of-reaction.md), [selectivity](rstoic-selectivity.md), [combustion](rstoic-combustion.md), [streams, heat streams and flash options](rstoic-streams-flash.md).

Not covered: Dynamics (Aspen Dynamics only); EO Options (equation-oriented options, not checked); Component Attr. (attributes of solids components, needs a solid substream, not checked); PSD (particle size of solids products, needs a solid substream, not checked).
