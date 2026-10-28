# USER

Calls a unit-operation subroutine you compile yourself; Aspen hands it the inlet stream vectors and your parameters and takes back the outlet vectors. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

## Making the model reachable (in this order)

1. Write the subroutine with the argument list of the template `usrusr.f` in `<Aspen Plus>\Engine\User` (four inlet and four outlet stream vectors, then substreams, parameters, work arrays). Any language works if the DLL exports the name in upper case and takes every argument by reference; a C DLL built with MSVC ran.
2. List the DLL's full path in a plain text linker options file, one DLL per line.
3. Point the run at that file with `set_engine_file(session, <path to the file>)` (kind `linker_options` is the default; the file must exist, and an empty path clears the setting). The GUI has it under Run Settings, tab Engine Files, field Linker options. Saving the .bkp keeps it, so a reopened file runs without this step.
4. Set `Input\USRMODEL` to the exported name. Left empty, check_inputs lists the block as incomplete (USRMODEL among the empty fields of its Specifications sheet) and run_simulation refuses to run.

Without the linker file the run stops before the block: no block status, no outlet results. run_simulation quotes the engine's link errors, names the missing subroutine and points to set_engine_file.

## How streams reach the subroutine

Streams on a port are passed in the order they were connected (first connected = SIN1 / SOUT1).

Each MIXED stream vector holds, in SI units: the component mole flows (kmol/s), total flow, T (K), P (Pa), mass enthalpy (J/kg), vapor and liquid fractions, mass entropy (J/kg-K), density (kg/m3) and molecular weight.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\USRMODEL` | subroutine name | Model subroutine called on every block pass |
| `Input\USRREPORT` | subroutine name | Optional subroutine called when the report is written |
| `Input\NINT` | int, 1-10000 | How many INT values the subroutine gets (default 1) |
| `Input\NREAL` | int, 1-10000 | How many REAL values the subroutine gets (default 1) |
| `Input\VALUE_LIST\{row}` | int | Integer parameter values, rows `#0`.. (arrive as INT) |
| `Input\RVALUE_LIST\{row}` | real | Real parameter values, rows `#0`.. (arrive as REAL) |
| `Input\NIWORK` | int | Size of IWORK, scratch integers kept by Aspen |
| `Input\NWORK` | int | Size of WORK, scratch reals kept by Aspen |

## Input | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\BYPASS_USER` | `YES`, `NO` | YES (default): skip the subroutine while the total inlet flow is zero |
| `Input\FLASH_FEEDS` | `NO`, `YES` | YES: flash the inlets before the call |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\MODEL_SUB` | name | Model subroutine that ran |
| `Output\REPORT_SUB` | name | Report subroutine that ran |
| `Output\VAR_VAL\{id}` | real | Real parameter values after the call (row 1 = REAL(1)) |
| `Output\BAL_MOLO_TFL` | MOLE-FLOW | Total outlet mole flow (mass balance check) |
| `\Data\Streams\{stream}\Output\MOLEFLMX\MIXED` | MOLE-FLOW | First outlet's flow |

More: [user-stream-flash.md](user-stream-flash.md) (flash an outlet after the call), [user-property-settings.md](user-property-settings.md) (a second property set).

Not covered: EO Var / Vec, EO variable definition (equation-oriented variable vectors, not checked); Heat and work streams (the `HS` / `WS` ports, not checked).
