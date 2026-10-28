# RCSTR mass transfer

Paths are under `\Data\Blocks\{name}\`. With `NPHASE` 2 the vapor and liquid can be kept apart, exchanging components at a set rate instead of reaching equilibrium.

1. Set `NPHASE` = `2` and `MT_OPTION` = `CONSTANT-KLA`.
2. Per component: `insert_row` on `Input\KLA_SPEC`, `set_label` with the component ID, then `set_value` on `Input\KLA_SPEC\{comp}`.

A stream connected to `VI(IN)` switches `VAPOR_INLET` to `YES`; that vapor enters the vapor phase.

## Mass Transfer

| Path | Type | Purpose |
|---|---|---|
| `Input\MT_OPTION` | `NO-MASS-TRAN`, `CONSTANT-KLA` | Phase equilibrium, or a fixed volumetric coefficient per component |
| `Input\KLA_SPEC\{comp}` | INVERSE-TIME | kLa for that component |
| `Input\FLASH_INLET` | `NO`, `YES` | Flash the feed before it enters |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\VAP_VOL` | VOLUME | Vapor volume |
| `Output\B_VFRAC` | fraction | Outlet vapor fraction |
