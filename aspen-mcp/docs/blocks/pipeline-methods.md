# Pipeline methods

Paths are under `\Data\Blocks\{name}\` (form Setup | Methods). Fluid flow only (`PIPE_METH=FLUID`).

| Path | Type | Purpose |
|---|---|---|
| `Input\INTEGRATION` | `YES`, `NO` | Integrate along each segment, or one closed-form equation per segment (single-phase lines) |
| `Input\INT_METHOD` | `GEAR`, `HAMMING` | Integrator (`INTEGRATION=YES`) |
| `Input\CL_FORM_METH` | `AGA`, `WEYMOUTH`, `PANHANDLE-A`, `PANHANDLE-B`, `SMITH`, `OLIPHANT`, `HAZEN-WILL` | Closed-form equation (`INTEGRATION=NO`); `HAZEN-WILL` is for water-like liquids |
| `Input\EFFICIENCY\{seg}` | real | Per segment: closed-form efficiency factor, 1 = clean pipe; with `HAZEN-WILL` it is the C factor |

With `HAZEN-WILL` set `EFFICIENCY` to the C factor (about 100-150): left at its default the drop comes out thousands of times too large and the run fails.

## Correlations by slope (`INTEGRATION=YES`)

`FRIC_*` set the friction pressure drop, `HOLDUP_*` the liquid holdup, each for horizontal (`HORIZ`), upward inclined (`INCL`), vertical (`VERTICA` / `VERTI`) and downhill (`DOWNHIL` / `DOWNH`) segments.

| Path | Type | Purpose |
|---|---|---|
| `Input\FRIC_HORIZ` | `BEGGS-BRILL`, `DUKLER`, `LOCK-MART`, `DARCY`, `HTFS` | Friction, horizontal |
| `Input\FRIC_INCL` | `BEGGS-BRILL`, `DUKLER`, `ORKI`, `AWR`, `H-BROWN`, `DARCY`, `HTFS` | Friction, inclined |
| `Input\FRIC_VERTICA` | `BEGGS-BRILL`, `ORKI`, `AWR`, `H-BROWN`, `DARCY`, `HTFS` | Friction, vertical |
| `Input\FRIC_DOWNHIL` | `BEGGS-BRILL`, `SLACK`, `DARCY`, `HTFS` | Friction, downhill |
| `Input\HOLDUP_HORIZ` | `BEGGS-BRILL`, `EATON`, `LOCK-MART`, `HOOG`, `HUGH`, `HTFS` | Holdup, horizontal |
| `Input\HOLDUP_INCL` | `BEGGS-BRILL`, `FLANIGAN`, `ORKI`, `AWR`, `H-BROWN`, `HTFS` | Holdup, inclined |
| `Input\HOLDUP_VERTI` | `BEGGS-BRILL`, `ORKI`, `AWR`, `H-BROWN`, `HTFS` | Holdup, vertical |
| `Input\HOLDUP_DOWNH` | `BEGGS-BRILL`, `SLACK`, `HTFS` | Holdup, downhill |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\HOLDUP_OUT\{node}` | fraction | Liquid holdup (volume fraction) at each node |
| `Output\REGIME\{node}` | string | Two-phase pattern found at each node, e.g. `WAVE`, `SLUG` |
| `Output\DPFRIC\{node}` | PRESSURE | Friction part of each segment's drop |
| `Output\EFFICIENCY_OUT\{seg}` | real | Efficiency used per segment, percent |
