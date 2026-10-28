# RPlug profiles

Paths are under `\Data\Blocks\{name}\`. A temperature, medium-temperature, heat-flux or diameter that changes along the tube, given as (location, value) pairs.

1. Set the mode: `OPT_TSPEC` = `TEMP-PROF` (with `TYPE` = `T-SPEC`), `TYPE` = `TCOOL-PROF` or `QFLUX-PROF`, or `OPT_DIA` = `PROFILE`.
2. Per point: `insert_row` on the value list; its location row (`#n` in the paired list) appears with it.
3. Write the location as a fraction of the length (0 inlet, 1 outlet), then the value.

Between points the value is interpolated linearly.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_TEMP\{row}` | TEMPERATURE | Process temperature at that point (`TEMP-PROF`) |
| `Input\LOC\{row}` | fraction | Its location |
| `Input\TCOOL\{row}` | TEMPERATURE | Medium temperature at that point (`TCOOL-PROF`, with `U`) |
| `Input\TCOOL_LOC\{row}` | fraction | Its location |
| `Input\QFLUX\{row}` | FLUX-HEAT-AR | Heat flux into the process stream, per wall area (`QFLUX-PROF`) |
| `Input\QFLUX_LOC\{row}` | fraction | Its location |

## Setup | Diameter

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_DIA` | `CONSTANT`, `PROFILE` | One diameter (`DIAM`) or a profile |
| `Input\DIA\{row}` | LENGTH | Diameter at that point |
| `Input\DIA_LOC\{row}` | fraction | Its location |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\TCOOL_OUT\{id}` | TEMPERATURE | Medium temperature at each profile point (`TCOOL-PROF`) |
| `Output\B_TEMP\MIXED\{id}` | TEMPERATURE | Process temperature profile |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
