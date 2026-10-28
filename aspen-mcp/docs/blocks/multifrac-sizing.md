# MultiFrac tray and packing sizing and rating

Paths are under `\Data\Blocks\{name}\`. Each object covers a stage range of one column; sizing finds a diameter, rating checks a given one.

1. `add_element` on `Subobjects\Tray Sizing`, `Tray Rating`, `Packing Sizing` or `Packing Rating` with an ID (`1`). Their fields start with `TS_`, `TA_`, `PS_` and `PR_` and are keyed by that ID.

## Trays

| Path | Type | Purpose |
|---|---|---|
| `Input\TS_COL\{id}` | int | Column (`TA_COL` for rating) |
| `Input\TS_STAGE1\{id}` | int | Section begins at this stage (`TA_STAGE1`) |
| `Input\TS_STAGE2\{id}` | int | Section ends at this stage (`TA_STAGE2`) |
| `Input\TS_TRAYTYPE\{id}` | `SIEVE`, `CAPS`, `BALLAST`, `FLEXI`, `FLOAT` | Tray type (`TA_TRAYTYPE`) |
| `Input\TS_TRAY_SPAC\{id}` | LENGTH | Tray spacing |
| `Input\TS_NPASS\{id}` | int | Flow passes |
| `Input\TA_COL\{id}` | int | Column of a rating object |
| `Input\TA_DIAM\{id}` | LENGTH | Diameter to rate |

## Packing

| Path | Type | Purpose |
|---|---|---|
| `Input\PS_COL\{id}` | int | Column (`PR_COL` for rating); stages `PS_STAGE1` / `PS_STAGE2` |
| `Input\PS_PACKTYPE\{id}` | PALL, RASCHIG, BERL, ... | Packing type (`PR_PACKTYPE`) |
| `Input\PS_VENDOR\{id}` | string | Vendor, e.g. `GENERIC` (`PR_VENDOR`) |
| `Input\PS_PACK_MAT\{id}` | string | Material, e.g. `METAL` (`PR_PACK_MAT`) |
| `Input\PS_PACK_SIZE\{id}` | string | Size, e.g. `1-IN OR 25-MM` (`PR_PACK_SIZE`) |

The size codes depend on type, vendor and material: set those first, `PS_PACK_SIZE` last.

Packing type and HETP are not enough: until vendor, material and size are set the object stays incomplete and the block does not run.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_PS_HETP\{id}` | `HETP`, `HEIGHT` | Packing given by HETP or by total height (`OPT_PR_HETP`) |
| `Input\PS_HETP\{id}` | LENGTH | Height per stage (`PR_HETP`) |
| `Input\PR_DIAM\{id}` | LENGTH | Diameter to rate |

## Results (keyed by the object ID)

| Path | Type | Purpose |
|---|---|---|
| `Output\DIAM4\{id}` | LENGTH | Tray sizing: diameter |
| `Output\FLOOD_FAC6\{id}` | fraction | Tray rating: peak flooding fraction |
| `Output\DP_SECTION3\{id}` | PDROP | Tray rating: pressure drop over the section |
| `Output\DIAM2\{id}` | LENGTH | Packing sizing: diameter |
| `Output\FLOOD_FAC2\{id}` | fraction | Packing rating: peak flooding fraction |
| `Output\DP_SECTION\{id}` | PDROP | Packing rating: pressure drop over the section |
