# Crusher: grindability

How hard the solids are to grind, and how the power is turned into size reduction and heat. `BWI` is in [crusher.md](crusher.md). Paths are under `\Data\Blocks\{name}\`.

`HGI` alone also gives a power: the block takes the work index from it.

`COMM_LAW` changes the product only with `PSD_CALC_MET` `POWER`; with the BOM types every law gives the same power and product.

`OPEN_CIRCUIT` `YES` raises the power for the same product (here by about a third).

`MECH_EFF` below 1 turns part of the power into heat: the product leaves warmer, with the same size distribution.

## Input | Grindability

| Path | Type | Purpose |
|---|---|---|
| `Input\HGI\{substream}` | real | Grindability on the Hardgrove scale, per solid substream |
| `Input\COMM_LAW` | `BOND`, `RITTINGER`, `KICK` | Comminution law relating energy to size reduction |
| `Input\OPEN_CIRCUIT` | `NO`, `YES` | Mill runs in open circuit (no classifier recycle) |
| `Input\MECH_EFF` | fraction | Mechanical efficiency (default 1) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\POWER` | POWER | Grinding power |
