# Ziegler-Natta reaction set (ZIEGLER-NAT)

Coordination polymerization on catalyst sites: species lists, then one typed row per reaction and site type. Rules shared by all reaction sets: [reactions.md](reactions.md).

Root: `\Data\Reactions\Reactions\{id}`

Species and reactants are component IDs; the polymer is a component of `TYPE` `POLYMER`, each segment one of `TYPE` `SEGMENT`.

## Setup

1. `add_reaction_set` with `reaction_type='ZIEGLER-NAT'`.
2. Species: `insert_row` on a list (`Input\CATALYST`, `Input\MONOMER`, ...), then `set_value` on `Input\<list>\#0`.
3. Segment of each monomer: `insert_row` on `Input\R_SEG`, `set_label` with the monomer ID, `set_value` with the segment.
4. Reactions: `insert_row` on `Input\ZINTYPE` once per reaction and site type; `SITE_ID`, `CID1`, `ZNPRE_EXP` and the other row keywords get the same rows.
5. Give the catalyst in the feed its sites: `set_value` on `\Data\Streams\{feed}\Input\ELEM\MIXED\{catalyst}\CPSFRAC\#0` = 1 (all sites potential).
6. Put the set's ID on the reactor's `RXN_ID` row.

Without that site fraction the catalyst brings no sites: the run converges and makes no polymer.

`SITE_ID` is the site type; `\Data\Components\Polymers\Input\NSITES` sets how many there are (4 in this model).

## Species

| Path | Type | Purpose |
|---|---|---|
| `Input\CATALYST\{row}` | ID | Catalyst |
| `Input\COCATALYST\{row}` | ID | Cocatalyst |
| `Input\MONOMER\{row}` | ID | Monomer |
| `Input\HYDROGEN\{row}` | ID | Hydrogen (chain transfer) |
| `Input\ELECDONOR\{row}` | ID | Electron donor |
| `Input\POISON\{row}` | ID | Catalyst poison |
| `Input\SOLVENT\{row}` | ID | Solvent |
| `Input\CHAINTAG\{row}` | ID | Chain-transfer agent |
| `Input\BYPRODUCT\{row}` | ID | By-product |
| `Input\POLYMER` | ID | Polymer component |
| `Input\R_SEG\{monomer}` | ID | Segment a monomer becomes |

## Reactions (one row each)

| Path | Type | Purpose |
|---|---|---|
| `Input\ZINTYPE\{row}` | `ACT-SPON`, `ACT-COCAT`, `ACT-EDONOR`, `ACT-H2`, `ACT-MON`, `CHAIN-INI`, `PROPAGATION`, `CHAT-MON`, `CHAT-AGENT`, `CHAT-SOL`, `CHAT-COCAT`, `CHAT-H2`, `CHAT-EDONOR`, `CHAT-SPON`, `DEACT-POISON`, `DEACT-COCAT`, `DEACT-MON`, `DEACT-EDONOR`, `DEACT-H2`, `DEACT-SPON`, `COCAT-POISON`, `FSINH-H2`, `RSINH-H2`, `FSINH-POISON`, `RSINH-POISON`, `TDB-POLY`, `ATACT-PROP`, `CAT-ACTIVATE` | Reaction type |
| `Input\SITE_ID\{row}` | int | Site type of the row (once `ZINTYPE` is set) |
| `Input\CID1\{row}` | ID | First species (catalyst, monomer, or segment of the growing end) |
| `Input\CID2\{row}` | ID | Second species (monomer, cocatalyst, hydrogen, ...) |
| `Input\ZNPRE_EXP\{row}` | INVERSE-TIME | Pre-exponential factor |
| `Input\ZNACT_ENERGY\{row}` | MOLE-ENTHALP | Activation energy |
| `Input\ZNORDER\{row}` | real | Reaction order in the second species |
| `Input\REF_TEMP\{row}` | TEMPERATURE | Reference temperature of the rate constant |
| `Input\INCRX\{row}` | `YES`, `NO` | Use the row |

## Options

| Path | Type | Purpose |
|---|---|---|
| `Input\PHASE` | `L`, `V`, `L1`, `L2` | Phase the reactions run in |

## Results (product stream, after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{prod}\Output\MASSFLOW\MIXED\{poly}` | MASS-FLOW | Polymer made |
| `\Data\Streams\{prod}\Output\COMP_ATTR\MWN\MWN\{poly}\MIXED` | real | Molar mass, number mean |
| `\Data\Streams\{prod}\Output\COMP_ATTR\SITE_1\SMWN\{poly}\MIXED` | real | The same for the chains of site type 1 |
| `\Data\Streams\{prod}\Output\COMP_ATTR\CPSFRAC\CPSFRAC\{catalyst}\MIXED` | fraction | Potential sites left on the catalyst |
