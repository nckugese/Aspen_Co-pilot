# ESP: design mode

`MODE` `DESIGN` sizes the unit for a target efficiency: plate count, height and length, or tube count and length. Paths are under `\Data\Blocks\{name}\`; basics in [esp.md](esp.md).

The size limits and `GAS_VEL` act only with `CRAWFORD`: a `DEUTSCH` design, plate or tube, came out the same with them set.

With `CRAWFORD`, `MIN_LEN` 1 m lengthened the plates from 0.62 to 2.54 m and `MAX_WIDTH` 1 m kept the pack below 1 m.

`GAS_VEL` is `CRAWFORD`'s starting velocity; keep it between `MIN_VEL` and `MAX_VEL` ([operation](esp-operation.md)), or the run warns and starts halfway between them.

Aspen refuses `MAX_HT` and `MAX_WIDTH` below 1 m and `MIN_LEN` above 5 m.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\EFF` | fraction | Target share of the feed dust caught |
| `Input\GAS_VEL` | VELOCITY | `CRAWFORD`: starting gas velocity (default 2 m/s) |
| `Input\MAX_HT` | LENGTH | `CRAWFORD`: tallest plate allowed (default 8.4 m) |
| `Input\MAX_WIDTH` | LENGTH | `CRAWFORD`: widest plate pack allowed (default 8.4 m) |
| `Input\MIN_LEN` | LENGTH | `CRAWFORD`: shortest plate length allowed (default 0.1 m) |
| `Input\MAX_LEN` | LENGTH | `CRAWFORD`: longest plate length allowed (default 6.3 m) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\NUMBER` | int | `PLATE`: plates needed |
| `Output\HEIGHT` | LENGTH | `PLATE`: plate height found |
| `Output\LENGTH` | LENGTH | `PLATE`: plate length found |
| `Output\NUM_TUBES` | int | `TUBULAR`: tubes needed |
| `Output\LEN_TUBE` | LENGTH | `TUBULAR`: tube length found |
| `Output\EFF_OUT` | fraction | Efficiency reached |
