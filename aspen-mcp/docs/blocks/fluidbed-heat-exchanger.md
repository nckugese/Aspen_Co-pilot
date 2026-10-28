# FluidBed: heat exchanger

A horizontal tube bundle in the bed; the medium in the tubes runs from `H(IN)` to `H(OUT)`. Paths are under `\Data\Blocks\{name}\`; basics in [fluidbed.md](fluidbed.md).

1. Connect a stream to `H(IN)` and one to `H(OUT)`: the bundle fields below become required.
2. Fill the bundle fields below: with them the block is complete again. `EXCHANGER` can stay `NO`: the runs used the bundle (`HXFLAG` 1) without it.

| Path | Type | Purpose |
|---|---|---|
| `Input\HX_START_LOC` | fraction | Bottom of the bundle, fraction of `HEIGHT` |
| `Input\HX_END_LOC` | fraction | Top of the bundle, fraction of `HEIGHT` |
| `Input\TUBE_LENGTH` | LENGTH | Tube length |
| `Input\TUBE_OD` | LENGTH | Tube outside diameter |
| `Input\TUBE_PITCH` | LENGTH | Gap between neighbouring tube walls |
| `Input\NUM_TUBES` | int | Tubes in the bundle |
| `Input\NUM_LAYERS` | int | Tube layers |
| `Input\HT_COEFF` | HEAT-TRANS-C | U value between tubes and bed |
| `Input\USE_LMTD` | `NO`, `YES` | `YES`: drive the heat flow with the log-mean temperature gap |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EXQCALC` | ENTHALPY-FLO | Duty of the tube bundle (negative: heat into the bed) |
| `Output\HXFLAG` | int | 1 when the bundle was used |
