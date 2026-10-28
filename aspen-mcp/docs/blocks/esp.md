# ESP (electrostatic precipitator)

Charged dust drifts out of the gas onto grounded plates or tubes and is collected. `TYPE` `SOLIDS-SEP` is a plain split instead ([solids separator](esp-solids-separator.md)). Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` dusty gas, `G(OUT)` cleaned gas, `S(OUT)` collected dust. The feed needs a solid substream; these runs carried calcite in `CIPSD` (stream class `MIXCIPSD`, sizes 0 to 20 um) in nitrogen.

What each choice needs before it can run:

`PLATE` in `SIMULATION` mode: `HT_PLATE`, `LEN_PLATE`, `NPLATE`.

`TUBULAR`: `RAD_TUBE` and `RAD_ELEC`, plus `LEN_TUBE` and `NTUBE` in `SIMULATION` mode.

`DEUTSCH` and `SVAROVSKY`: `VOLT_LOAD` and `VOLT_PRECIP`.

`CRAWFORD`: the dust's `DIELEC` instead of the voltages; it works out the corona voltage itself.

`CRAWFORD` is for `PLATE` only: a `TUBULAR` block with it stays incomplete.

`MODE` `DESIGN`: the target `EFF` ([design](esp-design.md)).

`SOLIDS-SEP`: `PRES` plus the two specs that `PHASEP_OPT` names.

Keep the plate height within 0.3 to 3 times the pack width and the gas velocity within 0.15 to 5 m/s: outside, the run ends with a warning.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `PLATE`, `TUBULAR`, `SOLIDS-SEP` | Collector shape, or a plain split; no default |
| `Input\MODE` | `SIMULATION`, `DESIGN` | Rate a given unit (default), or size it for `EFF` |
| `Input\MODEL` | `DEUTSCH`, `SVAROVSKY`, `CRAWFORD` | Collection model; no default |
| `Input\HT_PLATE` | LENGTH | `PLATE`: plate height |
| `Input\LEN_PLATE` | LENGTH | `PLATE`: plate length along the gas flow |
| `Input\NPLATE` | int | `PLATE`: number of plates; the gas flows in the gaps between them |
| `Input\RAD_TUBE` | LENGTH | `TUBULAR`: tube radius |
| `Input\RAD_ELEC` | LENGTH | `TUBULAR`: radius of the discharge electrode on the tube axis |
| `Input\LEN_TUBE` | LENGTH | `TUBULAR`: tube length |
| `Input\NTUBE` | int | `TUBULAR`: tubes in parallel |
| `Input\VOLT_LOAD` | VOLTAGE | `DEUTSCH`, `SVAROVSKY`: voltage of the zone that charges the dust |
| `Input\VOLT_PRECIP` | VOLTAGE | `DEUTSCH`, `SVAROVSKY`: voltage of the zone that collects it |
| `Input\K` | real | `DEUTSCH`, `SVAROVSKY`: exponent K of the efficiency relation (default 1) |
| `Input\ALPHA` | real | `DEUTSCH`, `SVAROVSKY`: exponent alpha (default 0.53) |

`K` and `ALPHA` changed the efficiency of both models.

## Input | Dielectric Constant

| Path | Type | Purpose |
|---|---|---|
| `Input\DIELEC\{substream}` | real | `CRAWFORD`: relative permittivity of the particles in each solid substream |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EFF_OUT` | fraction | Share of the feed dust caught |
| `Output\VELOCITY` | VELOCITY | Gas velocity between the plates or in the tubes |
| `Output\PDRP` | PDROP | Gas pressure drop ([operation](esp-operation.md)) |
| `Output\POWER` | POWER | Electrical power |
| `Output\AREA_PRECIP` | AREA | `DEUTSCH`, `SVAROVSKY`: collecting area |
| `Output\VOL_RATIO` | ratio | `DEUTSCH`, `SVAROVSKY`: collecting area per gas volume flow |
| `Output\VOLTAGE` | VOLTAGE | `CRAWFORD`: computed corona voltage |
| `Output\WIDTH` | LENGTH | `PLATE`: overall width across all the gas lanes |
| `Output\NUM_TUBES` | int | `TUBULAR`: number of tubes |
| `Output\GAS_LOAD_IN` | MASS-DENSITY | Dust per volume of gas at the inlet (`GAS_LOAD_OUT` at the outlet) |

More: [design](esp-design.md), [operation](esp-operation.md), [solids separator](esp-solids-separator.md).

Not covered: Heating curves (shared form that this block's tree does not carry); Utility (not checked); NSEG (tube segment count, no effect seen in the runs).
