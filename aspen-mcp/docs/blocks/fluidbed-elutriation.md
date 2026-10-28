# FluidBed: elutriation and TDH

Fines carried out with the gas, and the transport disengaging height (TDH) above the bed. On the Specifications sheet. Paths are under `\Data\Blocks\{name}\`; basics in [fluidbed.md](fluidbed.md).

Each model has default parameters, so choosing a model is enough to run.

A freeboard shorter than the TDH (from the solids profile or from the chosen correlation) ends the run with a warning, block status 2. Here: `MF_VEL_CORR` `ERGUN` warned at `HEIGHT` 3 m, not at 5 m; `FOURNOL` gave a TDH near 30 m at 30 kmol/hr gas and warned, but not at 10 kmol/hr.

| Path | Type | Purpose |
|---|---|---|
| `Input\ELUT_MODEL` | `TASIRIN`, `COLAKYAN`, `ZENZ`, `SCIAZKO`, `GELDART`, `USER` | Elutriation correlation (default `TASIRIN`; `USER` is the extended Geldart form with parameters A-E) |

Parameters, each used only by its model:

| Path | Type | Purpose |
|---|---|---|
| `Input\TG_A1` | real | `TASIRIN`: one of six parameters `TG_A1`, `TG_B1`, `TG_C1`, `TG_A2`, `TG_B2`, `TG_C2` |
| `Input\CL_A` | real | `COLAKYAN`: parameters `CL_A`, `CL_B` |
| `Input\ZW_A1` | real | `ZENZ`: parameters `ZW_A1`, `ZW_B1`, `ZW_A2`, `ZW_B2` |
| `Input\SCIAZKO_A` | real | `SCIAZKO`: parameter A |
| `Input\GELDART_A` | real | `GELDART`: parameters `GELDART_A`, `GELDART_B` |
| `Input\ELUT_A` | real | `USER`: parameters `ELUT_A` to `ELUT_E` |
| `Input\DECAY_CONST` | real | Decay constant of the solids fraction in the freeboard (default 3) |

## Transport disengaging height

| Path | Type | Purpose |
|---|---|---|
| `Input\TDH_MODEL` | `GEORGE-GRACE`, `CHAN`, `FOURNOL`, `FUNG` | TDH correlation (default `GEORGE-GRACE`) |
| `Input\MAX_DCVDH` | real | Slope of the solids fraction over height that marks the TDH on the profile |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TDH_FOM_CORR` | LENGTH | TDH from the chosen correlation |
| `Output\TDH_FROM_PROF` | LENGTH | TDH from the solids fraction profile |
