# PetroFrac tray and packing sizing / rating

Paths are under `\Data\Blocks\{name}\`. Sizing finds the diameter of a stage range; rating checks a given diameter.

1. `add_element` on `Subobjects\Tray Sizing`, `Tray Rating`, `Pack Sizing` or `Pack Rating` with an ID, e.g. `1`; the fields are keyed by that ID.
2. Set the stage range (`TS_STAGE1` / `TS_STAGE2`; prefixes `TR_`, `PS_`, `PR_` for the others) and the tray or packing type; rating also needs the diameter.

## Tray sizing and rating

| Path | Type | Purpose |
|---|---|---|
| `Input\TS_TRAYTYPE\{id}` | `SIEVE`, `CAPS`, `BALLAST`, `FLEXI`, `FLOAT` | Tray type (sizing) |
| `Input\TS_TSPACE\{id}` | LENGTH | Tray spacing (sizing) |
| `Input\TR_TRAYTYPE\{id}` | `SIEVE`, `CAPS`, `BALLAST`, `FLEXI`, `FLOAT` | Tray type (rating) |
| `Input\TR_DIAM\{id}` | LENGTH | Column diameter being rated |

## Packing sizing and rating

| Path | Type | Purpose |
|---|---|---|
| `Input\PS_PACKTYPE\{id}` | PALL, RASCHIG, BERL, ... | Packing type |
| `Input\PS_VENDOR\{id}` | text, e.g. `GENERIC` | Packing vendor |
| `Input\PS_PACK_MAT\{id}` | text, e.g. `METAL` | Packing material |
| `Input\PS_PACK_SIZE\{id}` | text, e.g. `1-IN OR 25-MM` | Packing size |

Their choices follow the packing type: set `PS_PACKTYPE` first.

Without vendor, material and size the packing object stays incomplete and the run does not start.

| Path | Type | Purpose |
|---|---|---|
| `Input\PS_HETP\{id}` | LENGTH | HETP: packed height that makes one stage |
| `Input\PR_VENDOR\{id}` | text | Rating: the same fields with prefix `PR_` (`PR_PACKTYPE`, `PR_VENDOR`, ...) |
| `Input\PR_DIAM\{id}` | LENGTH | Column diameter being rated |

## Strippers

1. The same four objects exist per stripper: `add_element` on `Subobjects\Strippers\{stripper}\Subobjects\Tray Sizing` (or `Tray Rating`, `Pack Sizing`, `Pack Rating`); fields start with `STS`, `STR`, `SPS`, `SPR` and are keyed by the stripper ID, then the object ID.

| Path | Type | Purpose |
|---|---|---|
| `Input\STSSTAGE1\{stripper}\{id}` | int | Stripper tray sizing: first stage (`STSSTAGE2` the last) |
| `Input\STRDIAM\{stripper}\{id}` | LENGTH | Stripper tray rating: diameter |
| `Input\SPSPACKTYPE\{stripper}\{id}` | PALL, RASCHIG, BERL, ... | Stripper packing sizing: packing type (vendor, material and size are needed here too) |
| `Input\SPRDIAM\{stripper}\{id}` | LENGTH | Stripper packing rating: diameter |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\DIAM4\{id}` | LENGTH | Tray sizing: diameter |
| `Output\FLOOD_FAC6\{id}` | fraction | Tray rating: highest flooding approach |
| `Output\DCBACKUP2\{id}` | fraction | Tray rating: highest downcomer backup |
| `Output\DIAM2\{id}` | LENGTH | Packing sizing: diameter |
| `Output\DP_SECTION2\{id}` | PDROP | Packing sizing: pressure drop over the range |
