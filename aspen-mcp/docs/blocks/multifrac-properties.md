# MultiFrac property sections

Paths are under `\Data\Blocks\{name}\`. A stage range of one column can use another property method.

1. Insert a row on `PN_OPSETNAME\{col}` and label it with the first stage of the range; `PN_STAGE2` gets the same row.

| Path | Type | Purpose |
|---|---|---|
| `Input\PN_STAGE2\{col}\{stage}` | int | Last stage of the range that starts at `{stage}` |
| `Input\PN_OPSETNAME\{col}\{stage}` | method | Property method of that range |
