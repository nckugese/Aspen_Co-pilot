# Setup

Options for the whole simulation. Each group is a sub-object with its own `Input`, so a row reads `<group>\Input\<field>`.

Root: `\Data\Setup`

## Specifications

| Path | Type | Purpose |
|---|---|---|
| `Global\Input\SCLASS` | `CONVEN`, `MIXCISLD`, `MIXCIPSD` | Stream class: the substreams every stream carries ([setup-streams.md](setup-streams.md)) |
| `Global\Input\INSET` | `ENG`, `MET`, `METCBAR`, `SI` | Unit set of the inputs; values already entered are converted |
| `Global\Input\OUTSET` | `ENG`, `MET`, `METCBAR`, `SI` | Unit set the results are read in after a run |
| `Global\Input\BASIS` | `MOLE`, `MASS`, `STDVOL` | Flow basis new streams start with |
| `Main\Input\FREE_WATER` | `NO`, `YES`, `DIRTY` | Free-water phase in every block; `DIRTY` lets that phase hold other components |
| `Main\Input\TITLE` | string | Title of the run |
| `Main\Input\ATM_PRES` | PRESSURE | Atmospheric pressure behind gauge units |
| `Main\Input\OPER_YEAR` | TIME | Operating time in a year |
| `Account-Info\Input\USER_NAME` | string | User name |
| `Account-Info\Input\PROJECT_NAME` | string | Project name |

A class with an `NC` substream (`MIXNC`, `MIXNCPSD`, `MIXCINC`, `MCINCPSD`) needs a nonconventional component, or the run does not start.

## Unit sets

1. `add_element` on `\Data\Setup\Units-Sets` with a new ID makes a unit set.
2. Write its `Input\BASESET`, then change single quantities under `Unit-Types`.
3. Name it in `Global\Input\INSET` and `OUTSET`.

| Path | Type | Purpose |
|---|---|---|
| `Units-Sets\{set}\Input\BASESET` | `ENG`, `MET`, `METCBAR`, `SI` | Set the new one copies |
| `Units-Sets\{set}\Unit-Types\{cat}` | unit name | Unit of one quantity (`TEMPERATURE`, `PRESSURE`, ...) |

## Diagnostics

| Path | Type | Purpose |
|---|---|---|
| `Diagnostics\Input\SIM_LEVEL` | int 0-10 | Detail of simulation messages in the history |
| `Diagnostics\Input\PROP_LEVEL` | int 0-10 | Detail of property messages in the history |
| `Diagnostics\Input\T_SIM_LEVEL` | int 0-10 | Detail of simulation messages on the control panel |

## IDs

Block and utility IDs: at most 8 characters: letters, digits and `-` (Aspen also takes `+`, `#` and `$`). A longer ID or one with `_` (or `.`, `@`, `%`, `~`) is refused.

A lower-case ID is stored in upper case; the call still reports an error.

Aspen takes a longer stream ID or one with `_`, but the run cuts it: a stream with a longer ID gets no results, and one with `_` can stop the run before it starts. `place_stream` refuses such an ID and names one that fits.

More: [setup-sim-options.md](setup-sim-options.md) (flash defaults, energy balance, checks), [setup-run-mode.md](setup-run-mode.md) (SM / EO, run status), [setup-report.md](setup-report.md), [setup-streams.md](setup-streams.md) (PSD mesh, stream prices), [utilities](../utilities/utilities.md).

Not covered: Stream groups (groups of streams for the flowsheet display, not checked); Currency of a unit set, Carbon tracking (`GHG_STANDARD`, `CARBON_FEE`, `EMISSION_CAL`) (not checked); Variable groups (GUI-only, no tree keywords); Model options (`Model-Option`) (global solver defaults of columns, flashes and RGibbs, not checked); EO configuration (`\Data\EO Configuration`) (equation-oriented settings, not run); Equation-oriented solving (`PARADIGM` `EO`) (did not converge).
