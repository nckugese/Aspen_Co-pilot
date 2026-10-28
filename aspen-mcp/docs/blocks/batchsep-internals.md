# BatchSep column internals

Paths are under `\Data\Blocks\{name}\`; `{int}` is the internals ID, `{id}` the section number (Column Internals form).

1. `add_element` on `Subobjects\Column Internals` with an ID, e.g. `INT-1`, and set `CA_ACTIVE1\{int}` `YES`.
2. `insert_row` on `Input\CA_STAGE1\{int}` and label the row with the section number, e.g. `1`; the other section fields get the same row.
3. Set the stage range, the internal type and its geometry.

Section fields use RadFrac's `CA_*` keywords ([radfrac-internals.md](radfrac-internals.md)); the main ones:

| Path | Type | Purpose |
|---|---|---|
| `Input\CA_STAGE1\{int}\{id}` | int | Section begins here |
| `Input\CA_STAGE2\{int}\{id}` | int | Last stage |
| `Input\CA_INTERNAL\{int}\{id}` | `TRAY`, `PACKING` | Trays or packing |
| `Input\CA_ACTIVE\{int}\{id}` | `YES`, `NO` | Section in use |
| `Input\CA_DIAM\{int}\{id}` | LENGTH | Section diameter |
| `Input\CA_TRAY_SPC\{int}\{id}` | LENGTH | Tray spacing |
| `Input\CA_TRAYTYPE\{int}\{id}` | `SIEVE`, `BUBBLE-CAP` | Tray type |
| `Input\CA_PACK_HT\{int}\{id}` | LENGTH | Packed height (`PACKING`) |
