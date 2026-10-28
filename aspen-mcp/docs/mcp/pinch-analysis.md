# Pinch analysis

`pinch_analysis` gives the minimum hot and cold utility, the pinch and the composite curves of a thermal stream table; `pinch_matches` lists the exchanger match sets that reach those targets. Both are computation only: no Aspen session.

In the Workbench the `pinch` statement builds the table from the live model itself: every Heater with one inlet and one outlet, and every RadFrac condenser and reboiler, converted to C and kW ([program format](workbench/program-format.md#pinch)).

## Steps

1. Converge the flowsheet.
2. Build the stream table from the results (below).
3. `pinch_analysis(streams)`; compare `Qh_min` / `Qc_min` with the present utility duties (prices: [utilities](../utilities/utilities.md)).
4. `pinch_matches(streams)` with the same table.
5. Add one HeatX at a time (`place_block`, `connect_stream`) with a trim heater or cooler after it, and run again.

## Stream table

One row per duty a utility serves now. Temperatures in C and duties in kW: convert from the field's unit (`get_node_unit_info`).

| Duty | `t_supply` / `t_target` | `heat_flow_kw` | `type` |
|---|---|---|---|
| Heater | `\Data\Streams\{stream}\Output\TEMP_OUT\MIXED` of the inlet / the outlet | `\Data\Blocks\{name}\Output\QCALC` | from the temperatures |
| RadFrac condenser | `\Data\Blocks\{name}\Output\B_TEMP\1`, both | `Output\COND_DUTY` | `hot` |
| RadFrac reboiler | `Output\B_TEMP\{NSTAGE}`, both | `Output\REB_DUTY` | `cold` |

| Key | Purpose |
|---|---|
| `name` | Stream label (used in `forbidden_pairs` and `weights`) |
| `t_supply`, `t_target` | Start and end temperature, C |
| `heat_flow_kw` | Duty, kW; the sign is ignored |
| `type` | `hot` or `cold`; required when `t_supply` = `t_target` (the duty is then given a 1 C span) |
| `dt_cont` | This stream's share of ΔTmin, C (default `dt_cont_default`); ΔTmin of a pair is the sum of both |
| `zone` | Zone name (default `Plant`) |

Existing process-to-process exchangers: leave them out to target the remaining utilities (retrofit), or add both sides as streams (new design); say which.

A hot product leaving the plant can be added as a hot stream down to the lowest temperature it may leave at; only the part above the pinch lowers the hot utility.

## pinch_analysis

| Parameter | Default | Purpose |
|---|---|---|
| `streams` | | The table above |
| `dt_cont_default` | 5.0 | ΔTmin share of streams without `dt_cont`, C |
| `project_name` | `Plant` | Title the targets are reported under |
| `include_curves` | `False` | Add composite and grand composite curve points (`CURVES_JSON:`, large) |
| `utilities` | | Utility definitions passed to OpenPinch as given |
| `timeout` | 120 | Seconds |

There is one target for the project and, when the streams lie in more than one zone, one for each zone. It returns per target `Qh_min`, `Qc_min`, the maximum recovery, the pinch as a shifted temperature and the utility split, then a `JSON:` line (`Qh_kW`, `Qc_kW`, `Qrecovery_kW`, `pinch_shifted_C`, `hot_utilities`, `cold_utilities`). The real pinch is shifted + `dt_cont` on the hot side and shifted - `dt_cont` on the cold side.

## pinch_matches

| Parameter | Default | Purpose |
|---|---|---|
| `streams` | | The same table |
| `dt_cont_default` | 5.0 | As above |
| `forbidden_pairs` | | `[[hot, cold], ...]` that may not be matched |
| `weights` | | `{"HOT\|COLD": w}`, cost of a match (default 1 each) |
| `extra_units` | 0 | Also list sets with up to this many matches above the minimum |
| `n_alternatives` | 8 | Most sets listed per region |
| `timeout` | 180 | Seconds |

It splits the problem at the pinch and solves the minimum-number-of-matches problem per region (MILP, HiGHS), listing every alternative set that reaches the minimum, each match with its duty. Tags: `[utility]`; `[pinch: ok]` (one exchanger works at the pinch); `[pinch: NEEDS SPLIT]` (energy-feasible, but needs a stream split or a series layout). A region with no feasible set under `forbidden_pairs` says so.

Rank the sets by how easy they are to build (recycle loops crossed, distance, materials), then put the hard exclusions in `forbidden_pairs` and preferences in `weights` and solve again. The pinch rules hold in every set: no heat across the pinch, no cold utility above it, no hot utility below it.

## Backend

Run in a subprocess, never in the server: `uv run --python 3.14 --with OpenPinch==0.4.5` (later OpenPinch releases dropped the entry point used). The first uv call installs Python 3.14 and OpenPinch and gets 420 s more than `timeout`. With neither available, the reply says to install uv (`winget install --id=astral-sh.uv -e`).
