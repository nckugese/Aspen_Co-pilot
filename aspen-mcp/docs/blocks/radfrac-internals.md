# RadFrac column internals

Paths are under `\Data\Blocks\{name}\`. Internals size or rate trays and packing section by section.

Tray Sizing / Tray Rating / Pack Sizing / Pack Rating are older objects, separate from internals; in V15 their runs converge with empty results, so use internals.

1. `add_element` on `Subobjects\Column Internals` with an ID, e.g. `INT-1`.
2. `add_element` on `Subobjects\Column Internals\{int}\Subobjects\Sections` with a section ID, e.g. `CS-1`.
3. Set the section's stage range, then its type and geometry.

Every section field is `Input\CA_<KW>\{int}\{sec}` (more than 200 of them); the main ones are below.

A new section is a tray section in interactive sizing.

With a reboiler, the last section must end above the reboiler stage (`CA_STAGE2` < `NSTAGE`).

| Path | Type | Purpose |
|---|---|---|
| `Input\CA_STAGE1\{int}\{sec}` | int | Section starts at this stage |
| `Input\CA_STAGE2\{int}\{sec}` | int | Section ends at this stage |
| `Input\CA_INTERNAL\{int}\{sec}` | `TRAY`, `PACKING` | Trays or packing |
| `Input\CA_SIZING\{int}\{sec}` | `INTER-SIZING`, `RATING` | Size the diameter, or rate a given one |
| `Input\CA_TRAYTYPE\{int}\{sec}` | SIEVE, BUBBLE-CAP, BALLAST-V1, ... | Tray type |
| `Input\CA_NPASS\{int}\{sec}` | int | Flow passes per tray |
| `Input\CA_TRAY_SPC\{int}\{sec}` | LENGTH | Tray spacing |
| `Input\CA_DIAM\{int}\{sec}` | LENGTH | Section diameter (needed for `RATING`) |
| `Input\CA_PACKTYPE\{int}\{sec}` | PALL, RASCHIG, MELLAPAK, ... | Packing type (`CA_INTERNAL=PACKING`) |
| `Input\CA_PACK_HT\{int}\{sec}` | LENGTH | Packed height |

## Results

The result names depend on the section's type and sizing mode:

| Path | Type | Purpose |
|---|---|---|
| `Output\CA_DIAM6\{int}\{sec}` | LENGTH | Tray, `INTER-SIZING`: diameter |
| `Output\CA_DPSEC4\{int}\{sec}` | PDROP | Tray, `INTER-SIZING`: total drop over the section |
| `Output\CA_FLD_FAC5\{int}\{sec}` | % | Tray, `RATING`: percent of flood |
| `Output\CA_DPSEC3\{int}\{sec}` | PDROP | Tray, `RATING`: total drop over the section |
| `Output\CA_DIAM2\{int}\{sec}` | LENGTH | Packing, `INTER-SIZING`: diameter |
| `Output\CA_DPSEC2\{int}\{sec}` | PDROP | Packing, `INTER-SIZING`: total drop over the section |
| `Output\CA_FLD_FAC1\{int}\{sec}` | % | Packing, `RATING`: percent of flood |
| `Output\CA_DPSEC1\{int}\{sec}` | PDROP | Packing, `RATING`: total drop over the section |
