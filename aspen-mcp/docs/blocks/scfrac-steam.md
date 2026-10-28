# SCFrac steam and free water

Paths are under `\Data\Blocks\{name}\`. Stripping steam enters through `SF(IN)`; the block sizes it from a ratio on each product below the distillate.

1. Connect the steam stream to `SF(IN)` before any Frac Index row: connected afterwards, the block stays flagged incomplete.
2. Give `STEAM:PROD` for every product except the distillate; temperature and pressure are optional.

The block replaces the steam stream's flow with what the ratios ask for.

All the water leaves in `D(OUT)`; with free water on, `FWDECANT` reports the part decanted in the condenser.

| Path | Type | Purpose |
|---|---|---|
| `Input\STEAM:PROD\{stream}` | MASS | Steam mass per barrel of the product |
| `Input\STEAM_TEMP\{stream}` | TEMPERATURE | Temperature of the stripping steam fed for that product |
| `Input\STEAM_PRES\{stream}` | PRESSURE | Pressure of the stripping steam fed for that product |
| `Input\BLKOPFREWAT` | `NO`, `YES` | Free water in the condenser: `YES` decants it |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\STEAM-FLOW\{section}` | MOLE-FLOW | Steam into each section |
| `Output\FWDECANT` | MOLE-FLOW | Free water decanted in the condenser |
