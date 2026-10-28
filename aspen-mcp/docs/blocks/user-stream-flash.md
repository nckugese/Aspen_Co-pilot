# USER: Stream Flash

Optional: after the subroutine returns, Aspen re-flashes a chosen outlet at the conditions given here (otherwise the outlet keeps the state the subroutine wrote). Paths are under `\Data\Blocks\{name}\`; `{stream}` is an outlet.

1. Insert a row in `Input\KODE` labelled with the outlet's name (insert_row, then set_label); that creates the stream's row in every field below.
2. Set the flash type, then the two values it needs.

| Path | Type | Purpose |
|---|---|---|
| `Input\KODE\{stream}` | `TP`, `PV`, `TV`, `PH`, `TH`, `NOFLASH` | Flash type: the pair of conditions fixed (PH / TH keep the subroutine's enthalpy) |
| `Input\TEMP\{stream}` | TEMPERATURE | Flash temperature |
| `Input\PRES\{stream}` | PRESSURE | Flash pressure |
| `Input\VFRAC\{stream}` | 0-1 | Vapor fraction |
| `Input\NPHASE\{stream}` | `1`, `2`, `3` | Phases considered |
| `Input\PHASE\{stream}` | `V`, `L`, `S` | Single phase to assume (used with NPHASE 1) |
| `Input\FREE_WATER\{stream}` | `NO`, `YES`, `DIRTY` | Free-water phase |
| `Input\PROPERTIES\{stream}` | `1`, `2` | Which property settings the flash uses (2: [user-property-settings.md](user-property-settings.md)) |
| `Input\T_EST\{stream}` | TEMPERATURE | Temperature estimate |
| `Input\P_EST\{stream}` | PRESSURE | Pressure estimate |
| `Input\MAXIT\{stream}` | int | Flash iteration limit |
| `Input\TOL\{stream}` | real | Flash tolerance |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\TEMP_OUT\MIXED` | TEMPERATURE | Outlet temperature after the flash (60 C in the TP run) |
| `\Data\Streams\{stream}\Output\VFRAC_OUT\MIXED` | 0-1 | Vapor fraction after the flash; the TV run gives 1 |

The TP run's flashed outlet comes out at 60 C while the other outlet stays at the subroutine's 95 C.

The PH and TH runs' flashed outlet keeps the molar enthalpy the subroutine wrote.
