# ESP: operation options

The Operation Options sheet of `PLATE` and `TUBULAR`: electrode spacing, wire data for `CRAWFORD`, gas velocity limits and the pressure drop. Paths are under `\Data\Blocks\{name}\`; basics in [esp.md](esp.md).

`PLATE`: the pack width is 2 x `PLATE_WIRE` x (`NPLATE` - 1); 0.15 m with 3 plates gave 0.6 m.

`DIAM`, `ROUGHNESS` and `VOLT_BREAK` set `CRAWFORD`'s corona voltage: 21 kV with the defaults, 34 kV with the values above.

`STDDEV_VEL` changed the `CRAWFORD` result only; `DEUTSCH` stayed the same.

## Electrodes and gas

| Path | Type | Purpose |
|---|---|---|
| `Input\PLATE_WIRE` | LENGTH | Gap from a plate to the discharge wires (default 0.114 m) |
| `Input\WIRE_WIRE` | LENGTH | Spacing between neighbouring wires (default 0.15 m) |
| `Input\DIAM` | LENGTH | Wire diameter (default 0.003 m) |
| `Input\ROUGHNESS` | real | Wire roughness factor (default 0.6) |
| `Input\VOLT_BREAK` | real | Breakdown field strength of the gas (default 3e6) |
| `Input\STDDEV_VEL` | real | Relative spread of the gas velocity (default 0.15) |
| `Input\MIN_VEL` | VELOCITY | Lowest gas velocity accepted (default 0.5 m/s) |
| `Input\MAX_VEL` | VELOCITY | Highest gas velocity accepted (default 3 m/s) |

## Pressure drop

| Path | Type | Purpose |
|---|---|---|
| `Input\PDROP_OPT` | `FROM-RHOV2`, `CONSTANT`, `VEL-FUNCTION` | How the gas pressure drop is found: from the dynamic pressure (default), a fixed value, or a velocity polynomial |
| `Input\RHOV2_FAC` | real | `FROM-RHOV2`: multiplier on the dynamic pressure (default 91) |

The drop is proportional to `RHOV2_FAC`: 50 in place of 91 cut it to 50/91.

| Path | Type | Purpose |
|---|---|---|
| `Input\PDROP_SPEC` | PDROP | `CONSTANT`: the drop |

`CONSTANT`: `PDRP` equals `PDROP_SPEC`.

| Path | Type | Purpose |
|---|---|---|
| `Input\PDROP_UNITS` | unit name | `VEL-FUNCTION`: unit of the drop, e.g. `bar` |
| `Input\VEL_UNITS` | unit name | `VEL-FUNCTION`: unit of the velocity, e.g. `m/sec` |
| `Input\PDROP_A` | real | `VEL-FUNCTION`: constant term a |
| `Input\PDROP_B` | real | `VEL-FUNCTION`: linear coefficient b |
| `Input\PDROP_C` | real | `VEL-FUNCTION`: square coefficient c |

`VEL-FUNCTION`: drop = a + b v + c v^2, with v the gas velocity of the run.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\PDRP` | PDROP | Gas pressure drop |
| `Output\VELOCITY` | VELOCITY | Gas velocity |
| `Output\VOLTAGE` | VOLTAGE | `CRAWFORD`: corona voltage with the changed wire data |
