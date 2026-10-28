# HeatX pressure drop

Paths are under `\Data\Blocks\{name}\`. Hot-side fields start with `H`, cold-side fields with `C`.

## Setup | Pressure Drop

| Path | Type | Purpose |
|---|---|---|
| `Input\HDP_OPTION` | `CONSTANT`, `FLOW`, `GEOMETRY` | Hot drop: from `PRES_HOT`, from a flow correlation, or from the geometry (`MODE=DETAILED`) |
| `Input\CDP_OPTION` | `CONSTANT`, `FLOW`, `GEOMETRY` | Cold drop, same choices |

`FLOW` needs `HDPPARMOP=YES` and `HDPPARM` (cold: `CDPPARMOP`, `CDPPARM`); without the parameter the block stops.

| Path | Type | Purpose |
|---|---|---|
| `Input\HDPPARMOP` | `NO`, `YES` | Give the correlation parameter |
| `Input\HDPPARM` | real (SI) | Correlation parameter |
| `Input\HMAX_DP` | fraction | Largest drop allowed, fraction of the inlet pressure |
| `Input\HDP_SCALE` | real | Factor applied to the calculated drop |
| `Input\P_UPDATE` | `YES`, `NO` | Apply the calculated drop to the outlet |
| `Input\TUBE_DP_FCOR` | correlation code (e.g. `BEGGS-BRILL`) | Two-phase tube friction correlation (detailed) |
| `Input\TUBE_DP_HCOR` | correlation code (e.g. `BEGGS-BRILL`) | Two-phase tube holdup correlation (detailed) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\HX_STDP` | PDROP | Shell-side (hot by default) drop |
| `Output\HX_TTDP` | PDROP | Tube-side drop |
