# PetroFrac property sections

Paths are under `\Data\Blocks\{name}\`. A different property method on a range of main-column stages.

1. `insert_row` on `Input\PM_STAGE1`: row `#0` appears in `PM_STAGE1`, `PM_STAGE2` and `PM_OPSETNAME` together.
2. Set the row's stage range and property method.

| Path | Type | Purpose |
|---|---|---|
| `Input\PM_STAGE1\{row}` | int | First stage of the range |
| `Input\PM_STAGE2\{row}` | int | Last stage of the range |
| `Input\PM_OPSETNAME\{row}` | method name | Property method on that range |

## Strippers

1. `insert_row` on `Input\PZ_OPSETNAME\{stripper}` and `set_label` with the first stripper stage of the range; set the method and the last stage on that label.

| Path | Type | Purpose |
|---|---|---|
| `Input\PZ_OPSETNAME\{stripper}\{stage}` | method name | Property method from that stripper stage |
| `Input\PZ_STAGE2\{stripper}\{stage}` | int | Last stripper stage of the range |
