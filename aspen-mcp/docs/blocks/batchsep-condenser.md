# BatchSep condenser and reflux drum

Paths are under `\Data\Blocks\{name}\`. Setup | Condenser, Second Condenser and Reflux (drum) sheets.

## Partial condenser (`CONDENSER` `PARTIAL`)

| Path | Type | Purpose |
|---|---|---|
| `Input\PARTIALSPEC` | `TEMP`, `VFRAC`, `CTEMP` | Fix the condenser temperature, the vapor fraction, or compute it from the coolant |
| `Input\T` | TEMPERATURE | Condenser temperature (`TEMP`) |

The distillate leaves at that temperature.

| Path | Type | Purpose |
|---|---|---|
| `Input\VFR` | fraction | Vapor fraction leaving the condenser (`VFRAC`) |
| `Input\TCOOLIN` | TEMPERATURE | Coolant inlet temperature (`CTEMP`) |
| `Input\FCOOL` | MASS-FLOW | Coolant flow (`CTEMP`) |
| `Input\UCOND` | HEAT-TRANS-C | Heat-transfer coefficient (`CTEMP`) |
| `Input\A` | AREA | Heat-transfer area (`CTEMP`) |

## Subcooling (`TOTAL`)

| Path | Type | Purpose |
|---|---|---|
| `Input\SUBCSPEC` | `NONE`, `TEMP`, `SUBCOOL` | No subcooling, a reflux temperature, or degrees below the bubble point |
| `Input\TSUB` | TEMPERATURE | Subcooled temperature (`TEMP`) |
| `Input\SUBCOOLING` | real | Amount below the bubble point (`SUBCOOL`; global temperature unit) |

## Second condenser (`PARTIAL2`)

The first condenser runs at `T`; its vapor goes on to the second condenser.

| Path | Type | Purpose |
|---|---|---|
| `Input\CONDENSER2` | `TOTAL`, `PARTIAL` | Second condenser type |
| `Input\T2` | TEMPERATURE | Second-condenser temperature (`PARTIAL`) |
| `Input\COND2_PRES` | PRESSURE | Second-condenser pressure (Setup \| Pressure) |

## Reflux drum

| Path | Type | Purpose |
|---|---|---|
| `Input\REFLUXDRUM` | `NO`, `YES` | Model a reflux drum between condenser and column |
| `Input\DRUM_GEOM` | `DL`, `DV`, `LV` | Drum size from two of diameter, length, volume |
| `Input\DRUM_V` | VOLUME | Drum volume |
| `Input\DRUM_DIAM` | LENGTH | Drum diameter |
| `Input\DRUM_LENGTH` | LENGTH | Drum length |

## Results

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\TEMP_OUT\MIXED` | TEMPERATURE | Distillate temperature |
