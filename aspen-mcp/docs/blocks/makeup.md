# Makeup

Tops up a stream, typically a recycle: it varies the flows of its makeup feeds (and, if asked, a purge) until the outlet has the target total flow and composition, then flashes the outlet. Paths are under `\Data\Blocks\{name}\`. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` the stream to top up, `FM(IN)` makeup feeds (any number), `O(OUT)` the outlet, `P(OUT)` the purge.

Connect the outlet to `O(OUT)`, not `P(OUT)`: once a target is written check_inputs requires `O(OUT)`, and a block with only `P(OUT)` connected returns no results.

A makeup feed's own flow is only a starting value; the block replaces it and keeps that feed's composition, temperature and pressure.

Every stream on `FM(IN)` is varied, whether or not `SID` lists it; `SID` rows only attach bounds.

Give one independent target per varied flow (each makeup feed, plus the purge when `VARY_PURGE` is `YES`): the outlet total, then fractions for all components but one. Two makeups need the total and one fraction.

Too few targets is not reported: with no targets, or only a total for two makeups, the run ends with BLKSTAT 0 but the outlet misses the total. Check the outlet flow after every run.

One varied flow too many (two makeups and the purge against a total and a composition) ends with a warning that the specifications cannot be met.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\BASIS` | `MOLE`, `MASS` | Which outlet total is used: `OUTMLFL` (default) or `OUTMAFL` |
| `Input\OUTMLFL` | MOLE-FLOW | Target outlet total flow when `BASIS` is `MOLE` |
| `Input\OUTMAFL` | MASS-FLOW | Target outlet total flow when `BASIS` is `MASS`; with `BASIS` left at `MOLE` this value is ignored |

1. Composition targets: `insert_row` on `Input\COMPS` (rows are unlabeled `#0`, `#1`, ...), then write the component ID to `COMPS\#i`; `BASIS_FRAC`, `MOLEFRAC` and `MASSFRAC` get the same row.
2. Makeup bounds (optional): `insert_row` on `Input\SID` and write a makeup stream name to `SID\#i`; `BASIS_FLOW`, `MOLEFLOW` and `MASSFLOW` get the same row.

| Path | Type | Purpose |
|---|---|---|
| `Input\COMPS\{row}` | component ID | Component of this target row |
| `Input\BASIS_FRAC\{row}` | `MOLE`, `MASS` | Basis of this row's fraction |
| `Input\MOLEFRAC\{row}` | fraction | Target mole fraction in the outlet |
| `Input\MASSFRAC\{row}` | fraction | Target mass fraction in the outlet |
| `Input\SID\{row}` | stream ID | Makeup feed this bound row applies to |
| `Input\BASIS_FLOW\{row}` | `MOLE`, `MASS` | Basis of this row's bound |
| `Input\MOLEFLOW\{row}` | MOLE-FLOW | Upper bound on that makeup flow; it does not cap the flow, going over it only gives a warning |
| `Input\MASSFLOW\{row}` | MASS-FLOW | The same bound on a mass basis |
| `Input\VARY_PURGE` | `NO`, `YES` | `YES` also varies the purge on `P(OUT)`; the purge leaves at the outlet composition, so it trims the total and the makeups set the composition |
| `Input\PURGE_BASIS` | `MOLE`, `MASS` | Basis of the purge bound |
| `Input\PURGE_MOLE` | MOLE-FLOW | Upper bound on the purge flow; going over it only gives a warning |
| `Input\PURGE_MASS` | MASS-FLOW | The same purge bound on a mass basis |

## Results (after a run)

The block's own `Output` holds only the status (`BLKSTAT`, `PER_ERROR`, `PROPSTAT`); the amounts are on the streams.

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\<makeup>\Output\MOLEFLOW\MIXED\{comp}` | MOLE-FLOW | Flow each makeup feed was given (base: benzene 10, toluene 5 kmol/hr) |
| `\Data\Streams\<outlet>\Output\MOLEFLMX\MIXED` | MOLE-FLOW | Outlet total, to confirm the target was met |
| `\Data\Streams\<purge>\Output\MOLEFLMX\MIXED` | MOLE-FLOW | Purge taken (purge run: 30 kmol/hr) |

| Path | Type | Purpose |
|---|---|---|
| `Output\BLKSTAT` | int | 0 when solved; a bound exceeded or a target not met gives a warning status |

More: [flash options](makeup-flash-options.md).

Not covered: none.
