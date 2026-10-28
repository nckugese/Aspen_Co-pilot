# USER2: Stream Flash

Optional: after the model returns, Aspen re-flashes a chosen outlet at the conditions given here; otherwise it flashes each outlet from the T and P the model wrote. Paths are under `\Data\Blocks\{name}\`; `{stream}` is an outlet.

1. Insert a row in `Input\KODE` labelled with the outlet's name (insert_row, then set_label); that creates the stream's row in every field below.
2. Set the flash type, then the values it needs.

| Path | Type | Purpose |
|---|---|---|
| `Input\KODE\{stream}` | `TP`, `PV`, `TV`, `PH`, `TH`, `NOFLASH` | Flash type: the pair of conditions fixed (PH / TH keep the model's enthalpy) |
| `Input\TEMP\{stream}` | TEMPERATURE | Flash temperature |
| `Input\PRES\{stream}` | PRESSURE | Flash pressure |
| `Input\VFRAC\{stream}` | 0-1 | Vapor fraction |
| `Input\NPHASE\{stream}` | `1`, `2`, `3` | Phases considered |
| `Input\PHASE\{stream}` | `V`, `L`, `S` | Single phase assumed, used with NPHASE 1 |
| `Input\FREE_WATER\{stream}` | `NO`, `YES`, `DIRTY` | Free-water phase |
| `Input\PROPERTIES\{stream}` | `1`, `2` | Property settings for the flash: 1 = the block's, 2 = the `C`-prefixed set below |
| `Input\T_EST\{stream}` | TEMPERATURE | Temperature estimate |
| `Input\P_EST\{stream}` | PRESSURE | Pressure estimate |
| `Input\MAXIT\{stream}` | int | Flash iteration limit |
| `Input\TOL\{stream}` | real | Flash tolerance |
| `Input\COPSETNAME` | method name | Property method of settings 2 (`CHENRY_COMPS`, `CCHEMISTRY`, ... follow the same `C` prefix) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\TEMP_OUT\MIXED` | TEMPERATURE | Outlet temperature after the flash (60 C in the TP run) |

In the TP run the flashed outlet leaves at 60 C while the other keeps the model's 95 C.

The PH and TH runs' flashed outlet keeps the molar enthalpy the model wrote.
