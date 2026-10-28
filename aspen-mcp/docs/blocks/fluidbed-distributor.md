# FluidBed: gas distributor

The distributor sets the starting bubble size and its own pressure drop. Paths are under `\Data\Blocks\{name}\`; basics in [fluidbed.md](fluidbed.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\DISTR_TYPE` | `PERF-PLATE`, `BUBBLE-CAPS` | Perforated plate (default) or bubble caps |

## Perforated plate

Its orifice count and size are needed in both of its options.

| Path | Type | Purpose |
|---|---|---|
| `Input\NUM_ORIFICE` | int | Orifices in the plate |
| `Input\DIAM_ORIFICE` | LENGTH | Orifice diameter |
| `Input\PERFP_OPT` | `CD-ORIFICE`, `DISTR-DROP` | Pressure drop from a discharge coefficient, or given |
| `Input\CD_ORIFICE` | real | Discharge coefficient of the plate holes (`CD-ORIFICE`, default 0.8) |
| `Input\DISTR_PDROP` | PDROP | Distributor pressure drop (`DISTR-DROP`) |

## Bubble caps

`BUBBLE-CAPS` needs `NUM_CAPS`, `NORIF_CAP` and `DORIF_CAP` in place of the plate orifices.

| Path | Type | Purpose |
|---|---|---|
| `Input\NUM_CAPS` | int | Bubble caps on the distributor |
| `Input\NORIF_CAP` | int | Orifices per cap |
| `Input\DORIF_CAP` | LENGTH | Cap orifice diameter |
| `Input\ORIFICE_OPT` | `CD-ORIF-CAP`, `DISTR-DROP1` | Pressure drop from a discharge coefficient, or given as `DISTR_PDROP` |
| `Input\CD_ORIF_CAP` | real | Discharge coefficient of the cap holes (`CD-ORIF-CAP`, default 0.8) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\DISTR_DPCALC` | PDROP | Distributor pressure drop |
