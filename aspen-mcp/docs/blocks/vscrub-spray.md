# VScrub: spray tower

`SCRUB_TYPE` `SPRAY` with `MODEL` `CALVERT`: droplets from nozzles fall through the rising gas. Paths are under `\Data\Blocks\{name}\`; basics in [vscrub.md](vscrub.md).

The liquid feed must be above the gas pressure; for example water at 3 atm to gas at 1.2 atm; the nozzle pressure drop is the difference.

## Droplets

| Path | Type | Purpose |
|---|---|---|
| `Input\SAUDIAM_OPT` | `CALSAUDIAM`, `SPESAUDIAM`, `SPEREGAVE` | Droplet size from the nozzles (default), given, or (`DESIGN` only) found for a given relative velocity |
| `Input\DIAM_ORIFICE` | LENGTH | `CALSAUDIAM`: nozzle orifice diameter |
| `Input\SPRAY_ANGLE` | real | `CALSAUDIAM`: cone angle of each nozzle jet, in deg |
| `Input\NUM_NOZZLE` | int | `CALSAUDIAM`: number of nozzles (default 1) |
| `Input\DROP_DIA` | LENGTH | `SPESAUDIAM`: droplet Sauter diameter |
| `Input\REL_GAS_VEL` | VELOCITY | Gas velocity relative to the droplets (required in `SIMULATION`) |

## Input | Operating Options: gas pressure drop

| Path | Type | Purpose |
|---|---|---|
| `Input\PDROP_OPT` | `CONSTANT`, `VEL-FUNCTION` | Fixed pressure drop (default 0), or a quadratic in the gas velocity |
| `Input\GAS_PDROP` | PDROP | `CONSTANT`: gas pressure drop |
| `Input\PDROP_A` | real | `VEL-FUNCTION`: constant term a, in `PDROP_UNITS`; `PDROP_B`, `PDROP_C` multiply velocity and velocity squared |
| `Input\PDROP_UNITS` | `bar`, `atm`, `psi`, `N/sqm` | `VEL-FUNCTION`: unit of the result (required) |
| `Input\VEL_UNITS` | `m/sec`, `ft/sec` | `VEL-FUNCTION`: unit of the velocity (required) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\GAS_VEL` | VELOCITY | Gas velocity used |
| `Output\NUMBER` | int | Number of nozzles |
| `Output\FEED_FLOW` | MASS-FLOW | Liquid per nozzle |
| `Output\PDROP` | PDROP | Liquid pressure drop over the nozzles |
| `Output\PDRP` | PDROP | Gas pressure drop |
