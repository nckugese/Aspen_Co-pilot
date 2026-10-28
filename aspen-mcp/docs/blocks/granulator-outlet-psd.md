# Granulator: given outlet PSD

`METHOD` = `USER-SPEC`: the product size distribution is given, as distribution functions or a table, for all solid substreams or per substream; the solid mass passes through. Paths are under `\Data\Blocks\{name}\`; basics in [granulator.md](granulator.md).

1. Insert one row per function into `OV_DISTFUN` (`insert_row`, labels `1`, `2`, ...); the other `OV_*` lists get the same rows.
2. Per function write `OV_DISTFUN\{id}`, `SPEC_OVOPT\{id}`, the two values the code names and `OV_FRACTION\{id}` (the fractions add up to 1).

Pairs that ran: `GGS` with `D63GGS`, `MGGS`, `D63D50`, `MD50`, `D50GGS`, `MD63`; `RRSB` with `D63D50`, `D50RRSB`, `D63RRSB`, `D50EDER`, `D63EDER`; `LOG-NORMAL` with `D50GMV`, `D63GMV`; `NORMAL` with `D50SV`, `D63SV`. In a code, M is the largest size, EDER the steepness.

`AVERAGE` is the product D50 and `DC_WIDTH1` its Sauter mean diameter: a table with half the mass in 400-500 µm and half in 500-700 µm gives 500 and 514 µm.

## Functions

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_SUBPSD` | `OVERALL`, `SUBSID` | One PSD for all solid substreams, or one per substream |
| `Input\OPT_OVERALL` | `DISTFUN`, `TABULAR` | Distribution functions or a table |
| `Input\OV_DISTFUN\{id}` | `GGS`, `RRSB`, `LOG-NORMAL`, `NORMAL` | Function type |
| `Input\SPEC_OVOPT\{id}` | `D63GGS`, `MGGS`, `D63D50`, `MD50`, `D50GGS`, `MD63`, `D50EDER`, `D50RRSB`, `D63EDER`, `D63RRSB`, `D50GMV`, `D63GMV`, `D50SV`, `D63SV` | Which two values define it |
| `Input\OV_D50\{id}` | LENGTH | Mass median size |
| `Input\OV_D63\{id}` | LENGTH | Size with 63.2 % of the mass finer |
| `Input\OV_DIAM\{id}` | LENGTH | Largest size (`M*` codes) |
| `Input\OV_GGSN\{id}` | real | GGS exponent |
| `Input\OV_RRSBN\{id}` | real | RRSB exponent |
| `Input\OV_STEEPNES\{id}` | ratio | D25/D75, below 1 (`*EDER`) |
| `Input\OV_GMDEV\{id}` | real | `LOG-NORMAL`: spread, as the sd of ln(size) |
| `Input\OV_STDDEV\{id}` | LENGTH | `NORMAL`: standard deviation |
| `Input\OV_FRACTION\{id}` | fraction | Mass share of this function |
| `Input\BYPASS` | fraction | Share of the feed solids that keep their own PSD (1: no change) |

## Table

| Path | Type | Purpose |
|---|---|---|
| `Input\OV_MESHOPT` | `PREDEF`, `LOCAL` | Table on the stream class mesh, or on its own intervals |

1. `PREDEF`: write `OV_PSDID` (`PSD`); its intervals appear as rows `OV_ATTR\#0`, `#1`, ...

| Path | Type | Purpose |
|---|---|---|
| `Input\OV_PSDID` | `PSD` | Mesh the table uses |
| `Input\OV_ATTR\{row}` | fraction | Mass fraction in mesh interval n |

2. `LOCAL`: insert one row per interval into `USER_OVLOWER`; `USER_OVUPPER` and `USER_OVVALUE` get the same row.

| Path | Type | Purpose |
|---|---|---|
| `Input\USER_OVLOWER\{row}` | LENGTH | Interval start (smaller size) |
| `Input\USER_OVUPPER\{row}` | LENGTH | Interval end (larger size) |
| `Input\USER_OVVALUE\{row}` | fraction | Mass fraction in the interval |
| `Input\INTERPOLATE` | `LINEAR`, `LIN-SPLINE`, `LOG-SPLINE` | Interpolation of the table: linear, spline, spline on an RRSB grid |

## Per substream (`SUBSID`)

The same inputs exist with the substream as the first index: `S_OPT\{substream}`, `S_DISTFUN\{substream}\{id}` (insert labelled rows on `S_DISTFUN\{substream}`), `SPEC_SUBOPT`, `SUB_D50` and the other `SUB_*` values, `S_FRACTION`, `SUBSATT\{substream}\#n` for a table, `S_MESHOPT` with `USER_SLOWER`/`USER_SUPPER`/`USER_SVALUE`, and `SUBBYPASS\{substream}`.

| Path | Type | Purpose |
|---|---|---|
| `Input\S_OPT\{substream}` | `DISTFUN`, `TABULAR` | Functions or a table for this substream |
| `Input\SUB_D50\{substream}\{id}` | LENGTH | Mass median size of function id |
| `Input\SUBSATT\{substream}\{row}` | fraction | Mass fraction in mesh interval n |
| `Input\SUBBYPASS\{substream}` | fraction | Bypass share of this substream |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\AVERAGE` | LENGTH | Product D50 |
| `Output\DC_WIDTH1` | LENGTH | Sauter mean size (d32) of the product |
