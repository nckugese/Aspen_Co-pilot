# HeatX baffles and nozzles

Paths are under `\Data\Blocks\{name}\`. Used with `MODE=DETAILED`.

## Geometry | Baffles

| Path | Type | Purpose |
|---|---|---|
| `Input\BAFFLE_TYPE` | `SEGMENTAL`, `ROD` | Baffle type |
| `Input\NSEG_BAFFLE` | int | How many baffles the shell holds |
| `Input\BAFFLE_CUT` | fraction | Cut height as a share of shell diameter |
| `Input\SHELL_BFL_SP` | LENGTH | Shell-to-baffle clearance |
| `Input\TUBE_BFL_SP` | LENGTH | Tube-to-baffle-hole clearance |
| `Input\SMID_BFL_SP` | LENGTH | Spacing between baffles |
| `Input\TUBES_IN_WIN` | `YES`, `NO` | Whether the window zones carry tubes |

Rod baffles (`BAFFLE_TYPE=ROD`):

`ROD_LENGTH` must be longer than `RING_INDIAM`.

| Path | Type | Purpose |
|---|---|---|
| `Input\RING_INDIAM` | LENGTH | Ring inside diameter |
| `Input\RING_OUTDIAM` | LENGTH | Ring outside diameter |
| `Input\ROD_DIAM` | LENGTH | Rod diameter |
| `Input\ROD_LENGTH` | LENGTH | Total rod length per baffle |

## Geometry | Nozzles

| Path | Type | Purpose |
|---|---|---|
| `Input\SNOZ_INDIAM` | LENGTH | Bore of the shell-side entry nozzle (`SNOZ_OUTDIAM` exit) |
| `Input\TNOZ_INDIAM` | LENGTH | Bore of the tube-side entry nozzle (`TNOZ_OUTDIAM` exit) |

## Results

The shell and tube drops each add up from a bundle part and a nozzle part.

| Path | Type | Purpose |
|---|---|---|
| `Output\HX_STDP` | PDROP | Shell-side drop: bundle `HX_SBDP` plus nozzles `HX_SNDP` |
| `Output\HX_TTDP` | PDROP | Tube-side drop: tubes `HX_TBDP` plus nozzles `HX_TNDP` |
