# Free-radical reaction set (FREE-RAD)

Chain-growth polymerization by radicals: lists of species, then one typed row per elementary reaction; an RCSTR, RPlug or RBatch uses the set through its `RXN_ID`. Rules shared by all reaction sets: [reactions.md](reactions.md).

Root: `\Data\Reactions\Reactions\{id}`

Species and reactants are component IDs; the polymer is a component of `TYPE` `POLYMER`, each segment one of `TYPE` `SEGMENT`.

## Setup

1. `add_reaction_set` with `reaction_type='FREE-RAD'` (the tool passes any type through).
2. Species: `insert_row` on a list (`Input\INITIATOR`, `Input\MONOMER`, ...), then `set_value` on `Input\<list>\#0` with the component.
3. Segment of each monomer: `insert_row` on `Input\R_SEG`, `set_label` with the monomer ID, then `set_value` with the segment ID.
4. Reactions: `insert_row` on `Input\FRRTYPE` once per reaction; `CID1`, `CID2`, `FRPRE_EXP` and the other row keywords get the same rows.
5. Put the set's ID on the reactor's `RXN_ID` row.

`GENRXN` = `YES` is an action: it fills the reaction rows at once from the species lists (8 rows for one initiator, monomer, solvent and agent), each with `FRPRE_EXP` = 0, and the field reads `NO` again.

Rows left at `FRPRE_EXP` = 0 do not react: such a set converges and makes no polymer.

## Species

| Path | Type | Purpose |
|---|---|---|
| `Input\INITIATOR\{row}` | ID | Initiator |
| `Input\MONOMER\{row}` | ID | Monomer |
| `Input\SOLVENT\{row}` | ID | Solvent (chains can transfer to it) |
| `Input\CHAINTAG\{row}` | ID | Chain-transfer agent |
| `Input\INHIBITOR\{row}` | ID | Inhibitor |
| `Input\CATALYST\{row}` | ID | Catalyst (catalytic initiation) |
| `Input\COINITIATOR\{row}` | ID | Co-initiator |
| `Input\BI_INITIATOR\{row}` | ID | Initiator with two radical-forming groups |
| `Input\POLYMER` | ID | Polymer component the chains belong to |
| `Input\R_SEG\{monomer}` | ID | Segment a monomer becomes in the chain |

## Reactions (one row each)

| Path | Type | Purpose |
|---|---|---|
| `Input\FRRTYPE\{row}` | `INIT-DEC`, `INIT-CAT`, `INIT-SP`, `BI-INIT-DEC`, `SEC-INIT-DEC`, `CHAIN-INI`, `PROPAGATION`, `CHAT-AGENT`, `CHAT-MON`, `CHAT-POL`, `CHAT-SOL`, `B-SCISSION`, `TERM-DIS`, `TERM-COMB`, `INHIBITION`, `SC-BRANCH`, `HTH-PROP`, `CIS-PROP`, `TRANS-PROP`, `TDB-POLY`, `PDB-POLY` | Reaction type |
| `Input\CID1\{row}` | ID | First species of the row (initiator, monomer of the radical end, ...) |
| `Input\CID2\{row}` | ID | Second species (the monomer, agent or solvent it meets) |
| `Input\FRPRE_EXP\{row}` | INVERSE-TIME | Pre-exponential factor |
| `Input\FRACT_ENERGY\{row}` | MOLE-ENTHALP | Activation energy |
| `Input\FRACT_VOL\{row}` | MOLE-VOLUME | Activation volume |
| `Input\REF_TEMP\{row}` | TEMPERATURE | Reference temperature of the rate constant |
| `Input\EFFIC\{row}` | fraction | Initiator efficiency (`INIT-DEC` rows) |
| `Input\NRADS\{row}` | int | Radicals one initiator molecule gives (`INIT-DEC` rows) |
| `Input\FRTDB_FRAC\{row}` | fraction | Share of dead chains left with a terminal double bond (transfer rows such as `CHAT-MON`) |
| `Input\INCRX\{row}` | `YES`, `NO` | Use the row (`NO` keeps it but leaves it out) |

## Options

| Path | Type | Purpose |
|---|---|---|
| `Input\GENRXN` | YES (action) | Write the reaction rows from the filled species lists; reads back `NO` |
| `Input\QSSA` | `NO`, `YES` | Quasi-steady-state radicals instead of integrating them |
| `Input\PHASE` | `L`, `V`, `L1`, `L2` | Phase the reactions run in |

## Gel effect

| Path | Type | Purpose |
|---|---|---|
| `Input\OGELEF` | `NO`, `YES` | Turn the gel-effect corrections on |
| `Input\CORR_NO\{n}` | int | Correlation number of gel-effect entry `{n}` (`insert_row` + `set_label` `{n}`) |
| `Input\GE_PARAMS\{n}\{row}` | real | Its parameters, one unlabelled row each |
| `Input\GEID\{row}` | int | Gel-effect entry applied to a reaction row |

## Results (product stream, after a run)

Polymer attributes of a stream sit at `Output\COMP_ATTR\<element>\<attribute>\<polymer>\MIXED`; a single-value attribute repeats its name as the element (`MWN\MWN`).

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{prod}\Output\MASSFLOW\MIXED\{poly}` | MASS-FLOW | Polymer made |
| `\Data\Streams\{prod}\Output\COMP_ATTR\MWN\MWN\{poly}\MIXED` | real | Molar mass, number mean |
| `\Data\Streams\{prod}\Output\COMP_ATTR\DPN\DPN\{poly}\MIXED` | real | Number-average chain length |
| `\Data\Streams\{prod}\Output\COMP_ATTR\PDI\PDI\{poly}\MIXED` | real | Polydispersity index |
