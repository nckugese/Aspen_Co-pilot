# Balance

Sets the flow, and if asked the enthalpy, of chosen streams so that mass and energy balances you write around blocks or between stream lists hold.

Root: `\Data\Flowsheeting Options\Balance\{id}`

`{bal}` is a balance's row (`#0`, `#1`, ...) and `{row}` one entry of its list.

1. `add_element` on `\Data\Flowsheeting Options\Balance` with an ID.
2. `insert_row` on `Input\OPT_MBLST`: row `#0` appears in every mass-balance list. Set `OPT_MBLST\#0`.
3. Each list of that row takes entries: `insert_row` on `Input\INLETS\#0` (or `OUTLETS`, `BLOCKS`, `COMPS`), then `set_value` on `Input\INLETS\#0\#0`, `#1`, ...
4. `insert_row` on `Input\CALC_SID`, then set `CALC_SID\#0` to the stream to compute and `FLOW\#0`.
5. Place it after the block that makes the streams it reads: `WHEN` `AFTER`, `BL_TYPE` `BLOCK`, `BLOCK_ID`.

Left at the default, it runs just before the first block that uses the stream it computes. That worked for G on the heater after the loop, but with G as a makeup into the loop's own mixer it ran before the flash and the run ended with errors.

Its status is `Output\BSTAT`; `Output\BLKSTAT` stays empty.

## Mass balance

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_MBLST\{bal}` | `BLOCK`, `STREAM` | Around the listed blocks, or between an inlet and an outlet stream list |
| `Input\BLOCKS\{bal}\{row}` | block ID | `BLOCK`: a block inside the balance |
| `Input\INLETS\{bal}\{row}` | stream ID | `STREAM`: a stream going in |
| `Input\OUTLETS\{bal}\{row}` | stream ID | `STREAM`: a stream coming out |
| `Input\COMPS\{bal}\{row}` | component ID, `ALL` | Balance each listed component (needed with `FLOW` `COMPS`) |

## Energy balance

`insert_row` on `Input\OPT_EBLST` gives row `#0` of the energy-balance lists; fill them as above.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_EBLST\{bal}` | `STREAM` | Between an inlet and an outlet stream list |
| `Input\E_BAL_INLETS\{bal}\{row}` | stream ID | A stream going in |
| `Input\E_BAL_OUTLET\{bal}\{row}` | stream ID | A stream coming out |
| `Input\RHS\{bal}` | ENTHALPY-FLO | Value the energy balance is held to; 0: what goes in comes out |

## Streams to compute

| Path | Type | Purpose |
|---|---|---|
| `Input\CALC_SID\{row}` | stream ID | A stream whose flow it sets |
| `Input\FLOW\{row}` | `TOTAL`, `COMPS` | `TOTAL`: scale the stream, keeping its composition; `COMPS`: set the flows of the components in `CALC_COMPS` |
| `Input\CALC_COMPS\{row}\{row}` | component ID, `ALL` | `COMPS`: the components to set |
| `Input\ENTHALPY\{row}` | `YES`, `NO` | `YES`: also set its enthalpy from the energy balance |

With `TOTAL` the makeup G took the vapor's 3651.4 kg/hr at its own 50/50 composition; with `COMPS` it took the vapor's component flows; with `ENTHALPY` `YES` its temperature moved to 139 C.

## Sequence and solver

| Path | Type | Purpose |
|---|---|---|
| `Input\WHEN` | `AFTER` | Runs right after the block in `BLOCK_ID` |
| `Input\BL_TYPE` | `BLOCK` | Kind of object `BLOCK_ID` names |
| `Input\BLOCK_ID` | block ID | The block it runs after |
| `Input\EXECUTE` | `ALWAYS`, `ONCE`, `NEVER` | How often it runs |
| `Input\MAXIT` | int | Iteration limit of its own solver |
| `Input\TOL` | real | Tolerance of its own solver |
| `Input\TERM_LEVEL` | int 0-10 | Detail of messages on the control panel |
| `Input\SIM_LEVEL` | int 0-10 | Detail of messages in the history |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BSTAT` | int | 0 when the balances were solved |
| `Output\STREAMID\{n}` | stream ID | Stream of each computed value |
| `Output\TYPE\{n}` | string | What was computed: `MASSFLOW`, `HEATFLOW` |
| `Output\VAR_VAL\{n}` | real | The value computed |
| `Output\VAR_UNIT\{n}` | unit | Its unit |
