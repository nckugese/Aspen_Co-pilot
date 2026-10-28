# Crusher: given outlet PSD

`PSD_CALC_MET` `USER-SPEC`: the product size distribution is given, by distribution functions or by a table. Paths are under `\Data\Blocks\{name}\`; basics in [crusher.md](crusher.md).

1. Insert a row with an ID label (e.g. `1`) into `OV_DISTFUN` (`insert_row` with a label); the other `OV_*` lists get the same ID.
2. Per ID set `OV_DISTFUN`, `SPEC_OVOPT`, the two values that code names and `OV_FRACTION`. The fractions of all IDs must add up to 1, else the block stays incomplete.

No power is computed: `POWER` stays empty.

`BYPASS` is the share of the feed solids that leaves unchanged; the rest takes the given PSD.

`TABULAR` on the stream-class mesh: set `OV_PSDID` first; then one `OV_ATTR` row per mesh interval appears.

## Distribution functions

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_SUBPSD` | `OVERALL`, `SUBSID` | One PSD for all solid substreams, or one per substream |
| `Input\OPT_OVERALL` | `DISTFUN`, `TABULAR` | Given by distribution functions or by a table |
| `Input\OV_DISTFUN\{id}` | `RRSB`, `GGS`, `NORMAL`, `LOG-NORMAL` | Function type of this ID |
| `Input\SPEC_OVOPT\{id}` | `D50RRSB`, `D63RRSB`, `D50EDER`, `D63D50`, `MGGS`, `MD50`, `D50SV`, `D50GMV`, `D50GGS`, `D63GGS`, `MD63`, `D63EDER`, `D63GMV`, `D63SV` | Which two values are given: D50, D63, M (largest size) with RRSB/GGS n (`RRSB`, `GGS`), EDER steepness, SV standard deviation or GMV geometric deviation |
| `Input\OV_FRACTION\{id}` | fraction | Mass share of this function |
| `Input\OV_D50\{id}` | LENGTH | Median size |
| `Input\OV_D63\{id}` | LENGTH | Size that 63.2 % of the mass passes |
| `Input\OV_DIAM\{id}` | LENGTH | Largest size |
| `Input\OV_RRSBN\{id}` | real | Spread exponent n of the RRSB curve |
| `Input\OV_GGSN\{id}` | real | Spread exponent n of the GGS curve |
| `Input\OV_STEEPNES\{id}` | real | Steepness D25/D75 |
| `Input\OV_STDDEV\{id}` | LENGTH | Standard deviation (`NORMAL`) |
| `Input\OV_GMDEV\{id}` | real | Geometric mean deviation (`LOG-NORMAL`) |

## Tables

| Path | Type | Purpose |
|---|---|---|
| `Input\OV_PSDID` | `PSD` | Mesh of the table (stream-class PSD mesh) |
| `Input\OV_ATTR\{row}` | fraction | Mass fraction of the mesh interval |
| `Input\OV_MESHOPT` | `PREDEF`, `LOCAL` | Table on the stream-class mesh or on a mesh of its own |
| `Input\USER_OVLOWER\{row}` | LENGTH | `LOCAL`: lower limit of the interval; insert rows here |
| `Input\USER_OVUPPER\{row}` | LENGTH | `LOCAL`: upper limit of the interval |
| `Input\USER_OVVALUE\{row}` | fraction | `LOCAL`: share of the solids in that size range |
| `Input\S_OPT\{substream}` | `DISTFUN`, `TABULAR` | `SUBSID`: how this substream's PSD is given (only `TABULAR` is covered here) |
| `Input\SUBSATT\{substream}\{row}` | fraction | `SUBSID` table: mass fraction of the mesh interval |
| `Input\BYPASS` | fraction | Share of the feed solids that bypass the crusher |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\OUTLET_D50` | LENGTH | Median size of the product solids |
| `Output\OUTLET_D80` | LENGTH | Size that 80 % of the product solids pass |
