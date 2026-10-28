# Material stream options

Flash options, reference temperatures, price and description of a material stream ([streams.md](streams.md)).

Root: `\Data\Streams\{id}`

## Flash options

| Path | Type | Purpose |
|---|---|---|
| `Input\NPHASE\MIXED` | `1`, `2`, `3` | Phases the stream's own flash looks for (blocks keep their own) |
| `Input\PHASE\MIXED` | `V`, `L` | The phase when `NPHASE` is 1 |
| `Input\FREE_WATER\MIXED` | `NO`, `YES`, `DIRTY` | Free-water handling in the stream's flash |
| `Input\MAXIT\MIXED` | int | Flash iteration limit |
| `Input\TOL\MIXED` | real | Flash tolerance |
| `Input\FL_OPTION\MIXED` | `NOFLASH` | Do not flash the stream at its inputs |

`FREE_WATER` `YES` is refused while `NPHASE` is 3.

## Reference temperatures

| Path | Type | Purpose |
|---|---|---|
| `Input\VOL_TREF\MIXED` | TEMPERATURE | Temperature a volume `TOTFLOW` refers to |
| `Input\CONC_TREF\MIXED` | TEMPERATURE | Temperature concentrations refer to |
| `Input\FLOWBASE\MIXED` | `VOLUME` | Written as well, or neither reference temperature reaches the run |

With `VOL_TREF` 25 C and `FLOWBASE` `VOLUME`, 5 cum/hr at 80 C ran as a larger actual flow; with `VOL_TREF` alone, as 5 cum/hr at 80 C.

With `CONC_TREF` 25 C and `FLOWBASE` `VOLUME`, 1 kmol/cum gave 4.69 instead of 5 kmol/hr of benzene; with `CONC_TREF` alone, 5.

## Price

| Path | Type | Purpose |
|---|---|---|
| `Input\PRICE` | UNIT-PRICE | Cost of one unit of mass |

| Path | Type | Purpose |
|---|---|---|
| `Output\MASS_PRICE` | UNIT-PRICE | Price used |
| `Output\STCOST` | COST-RATE | Cost per hour: price times mass flow |

## Description

| Path | Type | Purpose |
|---|---|---|
| `Input\DESCRIPTION` | text | Free text kept with the stream |
