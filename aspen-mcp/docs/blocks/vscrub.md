# VScrub (wet scrubber)

Removes dust from a gas with a scrubbing liquid: a venturi scrubber, a spray tower, or a simple solids separator with fixed splits. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` dusty gas, `L(IN)` scrubbing liquid, `G(OUT)` cleaned gas, `S(OUT)` liquid with the collected solids. A stream on `L(IN)` is needed in every type: without one the run stops before the block.

The dust is a solid substream of the gas feed; a working setup is calcite in a `CIPSD` substream (stream class `MIXCIPSD`) with a size distribution, which the efficiency curves act on.

What each type needs before it can run:

`VENTURI` with `YUNG`: the throat size for the chosen shape (`DIAM_THROAT` when round) and `LEN_THROAT`.

`VENTURI` with `CALVERT`: the throat size only.

`SPRAY`: `MODEL` `CALVERT` (the default `YUNG` leaves it incomplete), `REL_GAS_VEL` and a droplet spec, by default `DIAM_ORIFICE` and `SPRAY_ANGLE` ([spray tower](vscrub-spray.md)).

`SPRAY` sprays the liquid through nozzles: the `L(IN)` stream must be at a higher pressure than the gas, or the block ends in error.

`SOLIDS-SEP`: `PRES` plus the two specs that `PHASEP_OPT` names ([solids separator](vscrub-solids-separator.md)).

`MODE` `DESIGN`: the target `EFF` ([design](vscrub-design.md)).

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\SCRUB_TYPE` | `VENTURI`, `SPRAY`, `SOLIDS-SEP` | Scrubber model; no default |
| `Input\MODE` | `SIMULATION`, `DESIGN` | `VENTURI`, `SPRAY`: rate a given unit (default), or size it for `EFF` |
| `Input\MODEL` | `YUNG`, `CALVERT` | Efficiency correlation (default `YUNG`; `SPRAY` takes only `CALVERT`) |
| `Input\DIAM_THROAT` | LENGTH | Round throat diameter ([other shapes](vscrub-venturi-throat.md)) |
| `Input\LEN_THROAT` | LENGTH | `YUNG`: throat length |
| `Input\REL_GAS_VEL` | VELOCITY | `SPRAY`: gas velocity relative to the droplets |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EFF_OUT` | fraction | Share of the feed dust caught |
| `Output\PDRP` | PDROP | Gas pressure drop |
| `Output\VELOCITY` | VELOCITY | `VENTURI`: gas velocity in the throat |
| `Output\SAUTER_DIAM` | LENGTH | Droplet size (Sauter mean) |
| `Output\VOL_RATIO` | ratio | Liquid over gas, by volume |
| `Output\MASS_RATIO` | ratio | Liquid over gas, by mass |
| `Output\LOAD_IN` | MASS-DENSITY | Dust per volume of gas at the inlet (`LOAD_OUT` at the outlet) |

`SOLD_RECOV` reads 1 for `VENTURI` and `SPRAY` whatever the catch; use `EFF_OUT` there.

More: [venturi throat](vscrub-venturi-throat.md), [spray tower](vscrub-spray.md), [design](vscrub-design.md), [solids separator](vscrub-solids-separator.md), [operating options](vscrub-operating-options.md).

Not covered: Heating curves, Utility (shared forms that this block's tree does not carry); NPHASE 1 (the single-phase outlet flash failed on gas with water).
