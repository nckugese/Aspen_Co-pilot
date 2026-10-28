# ClChng

Stream class changer: hands its one feed to its outlet so the stream can continue in another stream class, e.g. from `CONVEN` into the solids class `MIXCISLD`. It has no specifications of its own; both classes come from the streams. Paths are under `\Data\Blocks\{name}\` unless they start with `\Data`; `{stream}` is the outlet. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` the feed, `P(OUT)` the outlet. Each holds one stream; Aspen refuses a second.

Only the ports are required, but write some input before the first run, e.g. `Input\DESCRIPTION`: left blank, the block counts as incomplete and run_simulation will not start.

The outlet keeps the feed's flow, temperature and pressure.

## Stream classes

Give the global class the value most streams need, list the remaining streams under Def-Streams, and put a ClChng wherever a stream crosses from one class to the other.

| Path | Type | Purpose |
|---|---|---|
| `\Data\Setup\Global\Input\SCLASS` | `CONVEN`, `MIXCISLD` | Default class for each stream that no Def-Streams row names |

1. `insert_row` on `\Data\Flowsheet\Def-Streams\Input\SCLASS`, then write the class to `SCLASS\#0` (a second class: row `#1`).
2. `insert_row` on `SLIST\#0`, then write a stream ID to `SLIST\#0\#0`; one more row per stream (`#1`, ...).

| Path | Type | Purpose |
|---|---|---|
| `\Data\Flowsheet\Def-Streams\Input\SCLASS\{row}` | `CONVEN`, `MIXCISLD` | Class of the streams in that row |
| `\Data\Flowsheet\Def-Streams\Input\SLIST\{row}\{row}` | stream ID | One stream of that row's class |

A substream that only the outlet class has starts with zero flow. A feed substream missing from the outlet class is thrown away, so if it carries flow the block ends in error with a mass imbalance.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BAL_MASI_TFL` | MASS-FLOW | Total mass in |
| `Output\BAL_MASO_TFL` | MASS-FLOW | Total mass out |
| `Output\TOT_MASS_REL` | fraction | Relative mass imbalance, 0 when nothing was dropped |
| `\Data\Streams\{stream}\Output\MOLEFLMX\CISOLID` | MOLE-FLOW | Outlet flow of a substream the class added |

Not covered: Heat and work streams (the HS/WS ports accepted them only in part; not run); Flowsheet sections (no way found over COM to put a block in a section; not checked).
