# USER: Property Settings 2

Block Options of a USER block hold two property settings. Settings 1 are the usual block property fields (see [common.md](common.md)); settings 2 are a second set an outlet flash can pick. Paths are under `\Data\Blocks\{name}\`.

Each settings-2 field is the settings-1 keyword with a `C` in front (`CFRWATEROPSE` is cut to 12 characters).

| Path | Type | Purpose |
|---|---|---|
| `Input\COPSETNAME` | method name | Property method of settings 2 |
| `Input\CFRWATEROPSE` | method name | Free-water property method of settings 2 |
| `Input\CSOLU_WATER` | `0`, `1`, `2`, `3`, `4`, `5` | Water solubility method of settings 2 |
| `Input\CHENRY_COMPS` | Henry-comps ID | Henry components of settings 2 |
| `Input\CCHEMISTRY` | Chemistry ID | Chemistry of settings 2 |

1. To use settings 2 in an outlet flash, set `Input\PROPERTIES\{stream}` to `2` ([user-stream-flash.md](user-stream-flash.md)).

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\TEMP_OUT\MIXED` | TEMPERATURE | Outlet flashed with settings 2 (60 C) |
