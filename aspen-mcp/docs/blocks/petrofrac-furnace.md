# PetroFrac feed furnace and stripping steam

Paths are under `\Data\Blocks\{name}\`. A feed whose `FEED_CONVEN` is `FURNACE` is heated in the furnace before it enters its stage.

Without a reboiler (`RTYPE` `NONE-BOTFEED`), the distillate rate plus one furnace spec (overflash, duty or outlet temperature) is a full set of specs.

With `CTYPE` `NONE-TOPPA` as well, the furnace spec is the only one and `BASIS_D` is locked.

## Setup | Furnace

| Path | Type | Purpose |
|---|---|---|
| `Input\FRN_MODEL` | `HEATER`, `FLASH`, `FLASH-BYPASS` | Furnace model |
| `Input\BASIS_OVFL` | fraction | Overflash: ratio of the liquid leaving the stage above the furnace feed stage to the furnace feed |
| `Input\FRN_DUTY` | ENTHALPY-FLO | Furnace duty |
| `Input\FRN_TEMP` | TEMPERATURE | Furnace outlet temperature |
| `Input\FRN_PRES` | PRESSURE | Furnace pressure (`FLASH`, `FLASH-BYPASS`) |

## Setup | Steam

`MAIN_STEAM` accepts only a feed on the bottom stage.

| Path | Type | Purpose |
|---|---|---|
| `Input\MAIN_STEAM` | stream ID | Bottom steam feed whose rate `STEAM:PROD` sets |
| `Input\STEAM:PROD` | ratio | Steam rate as a ratio to the product; it replaces the steam stream's own flow |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\GLB_FURN_DUTY` | ENTHALPY-FLO | Furnace duty |
