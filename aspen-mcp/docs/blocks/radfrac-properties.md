# RadFrac property sections

Paths are under `\Data\Blocks\{name}\`. A different property method on a range of stages.

1. `insert_row` on `Input\P_STYPE`: row `#0` appears in `P_STYPE`, `STAGE1`, `STAGE2` and `P_SOPSETNAME` together.
2. Set the row's kind, stage range and property method.

| Path | Type | Purpose |
|---|---|---|
| `Input\P_STYPE\{row}` | `SEGMENT` | What the row applies to (a stage range) |
| `Input\STAGE1\{row}` | int | First stage of the range |
| `Input\STAGE2\{row}` | int | Last stage of the range |
| `Input\P_SOPSETNAME\{row}` | method name | Property method on that range |
