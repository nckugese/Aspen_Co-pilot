# VScrub: operating options

The Operating Options sheet of `VENTURI` and `SPRAY` (not `SOLIDS-SEP`), besides the design limits ([design](vscrub-design.md)) and the spray pressure drop ([spray tower](vscrub-spray.md)). Paths are under `\Data\Blocks\{name}\`; basics in [vscrub.md](vscrub.md).

With `OUTLT_EQUIL` `NO` the cleaned gas left at the gas inlet temperature (60 C); the default `YES` cooled it to about 24 C against the water.

| Path | Type | Purpose |
|---|---|---|
| `Input\OUTLT_EQUIL` | `YES`, `NO` | Bring the outlets to equilibrium (default `YES`), or keep the inlet conditions |
| `Input\OUTPRE_OPT` | `MINOUTPRES`, `MAXPREDROP` | Pressure limit: a lowest outlet pressure (default) or a largest pressure drop |
| `Input\PMIN` | PRESSURE | `MINOUTPRES`: lowest outlet pressure (default 0.5) |
| `Input\MAX_PDROP` | PDROP | `MAXPREDROP`: largest pressure drop |

Neither limit changed the results of these runs (pressure drop 0.057 bar).

## Calvert

| Path | Type | Purpose |
|---|---|---|
| `Input\PARAM_F` | real | Calvert factor f of the collection curve (default 0.25) |
| `Input\BETA` | real | Calvert beta of the pressure-loss relation, 0 to 1 (default 0.85) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EFF_OUT` | fraction | Efficiency with the changed Calvert parameters |
| `Output\PDRP` | PDROP | Gas pressure drop with them |
