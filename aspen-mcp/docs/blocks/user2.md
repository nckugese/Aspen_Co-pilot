# USER2

Runs your own unit model: a subroutine you compile (this file) or an Excel workbook ([user2-excel.md](user2-excel.md)). Aspen passes the inlet streams and your parameter arrays and takes back the outlet streams. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F1(IN)` material inlets, `P1(OUT)` material outlets.

## Making the model reachable (in this order)

1. Write the subroutine with the argument list of the template `usrus2.f` in `<Aspen Plus>\Engine\User` (inlet and outlet stream arrays and their IDs, substreams, parameter and work arrays, then `NRXN`, `NBRXN`). Any language works if the DLL exports the name in upper case and takes every argument by reference; a C DLL built with MSVC ran.
2. List the DLL's full path in a plain text linker options file, one DLL per line.
3. Point the run at that file with `set_engine_file(session, <path to the file>)` (kind `linker_options` is the default; the file must exist, and an empty path clears the setting). The GUI has it under Run Settings, tab Engine Files, field Linker options. The .bkp stores it, so a saved file runs again without this step.
4. Set `Input\USRMODEL` to the exported name. check_inputs does not ask for it: left empty, the block runs with nothing called, the outlets get zero flow and BLKSTAT is 2 (mass imbalance). Without the linker file the run stops before any block, with no results.

## What the subroutine receives

`SIN` / `SOUT` hold one column of `NTOT` values per stream (`NMATI` inlets, `NMATO` outlets), in the order the streams were connected. For a MIXED-only stream class `NTOT` = components + 9: component mole flows (kmol/s), total flow, T (K), P (Pa), mass enthalpy (J/kg), vapor and liquid fractions, mass entropy (J/kg-K), density (kg/m3), molecular weight.

The outlet connected first is outlet 1.

Stream IDs in `IDSMI` / `IDSMO` come 4 integer words apart in V15 (the template's comments say 2).

An integer parameter left blank arrives as 99999999 (Aspen's missing value).

## Setup | Subroutines

| Path | Type | Purpose |
|---|---|---|
| `Input\USRMODEL` | subroutine name | Model subroutine called on every block pass |
| `Input\USRREPORT` | subroutine name | Optional subroutine called when the report is written |
| `Input\USER_SUBS\{row}` | subroutine name | Other subroutines to link with the model, rows `#0`..; a name no DLL exports stops the run |
| `Input\NIWORK` | int | Size of IWORK, scratch integers kept by Aspen |
| `Input\NWORK` | int | Size of WORK, scratch reals kept by Aspen |

## Setup | User Arrays

| Path | Type | Purpose |
|---|---|---|
| `Input\NINT` | int, 1-10000 | How many INT values the model gets (default 1) |
| `Input\NREAL` | int | How many REAL values the model gets (default 1) |
| `Input\NCHAR` | int, 1-10000 | How many text values are stored (default 1) |
| `Input\VALUE_LIST\{row}` | int | INT values, rows `#0`.. (row `#0` = INT(1)) |
| `Input\RVALUE_LIST\{row}` | real | REAL values, rows `#0`.. |
| `Input\CHAR_LIST\{row}` | text | Character values, rows `#0`.. |

The arrays run: NINT 2 arrives with INT(1) = 1, and NIWORK / NWORK 5 arrive as given.

## Setup | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\BYPASS_USER` | `YES`, `NO` | YES (default): skip the subroutine while the total inlet flow is zero |
| `Input\FLASH_FEEDS` | `NO`, `YES` | YES: flash the inlets before the call |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\MODEL_SUB` | name | Model subroutine that ran |
| `Output\REPORT_SUB` | name | Report subroutine that ran |
| `Output\VAR_VAL\{id}` | real | REAL array after the call, rows `1`.. |

A value the subroutine writes into REAL comes back in `VAR_VAL` (at the row the subroutine writes, for example outlet 1's flow in kmol/s).

| Path | Type | Purpose |
|---|---|---|
| `Output\BAL_MOLO_TFL` | MOLE-FLOW | Total outlet mole flow (mass balance check) |
| `\Data\Streams\{stream}\Output\MOLEFLMX\MIXED` | MOLE-FLOW | First outlet's flow |

More: [user2-excel.md](user2-excel.md) (Excel model), [user2-stream-flash.md](user2-stream-flash.md) (flash an outlet after the call), [user2-streams.md](user2-streams.md) (pass other streams).

Not covered: Petro Characterization (petroleum characterization by a user subroutine; needs assay pseudocomponents and a compiled routine, not checked); Configured Variables (labels for the array entries, a GUI table not in the tree); Heat and work streams (the `HS` / `WS` ports, not checked); Reactions (a reaction set listed in RXN_ID stops V15's input translation (BLDSNT.5, REACTIONS refused as a keyword)).
