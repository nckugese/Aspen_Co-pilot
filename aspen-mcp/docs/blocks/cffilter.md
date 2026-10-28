# CfFilter (crossflow filter)

Crossflow membrane filtration of a slurry: the liquid flows along plate channels or capillaries and part of it passes the membrane, so the solids are concentrated. `TYPE` `SOLIDS-SEP` is a plain split instead ([solids separator](cffilter-solids-separator.md)). Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` slurry feed, `P(OUT)` permeate (the liquid that passed the membrane), `R(OUT)` retentate (all solids plus the rest of the liquid). `P(OUT)` leaves at the feed pressure minus `PDROP`, `R(OUT)` at the feed pressure.

Feed the block above ambient pressure by more than `PDROP`: with a 1 atm feed and `PDROP` 1 bar the run ends with a warning (a 3 bar feed with that drop runs cleanly).

The feed needs a solid substream; a working setup is calcite in a `CIPSD` substream (stream class `MIXCIPSD`) with a size distribution.

What each type needs before it can run:

`PLATE`: `MODEL`, `WIDTH`, `HEIGHT`, `LENGTH`, `AVG_VELOCITY`, `PDROP`, plus the model's own inputs.

`CAPILLARY`: `CAP_DIAMETER` and `CAP_LENGTH` in place of the channel sizes.

`SHORT-CUT` needs `FILTR_RATE`; `ALTMANN` needs `POROSITY` and `FILTER_RES`; `DESIGN` mode needs `CONC_FACTOR`.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `SOLIDS-SEP`, `PLATE`, `CAPILLARY` | Module kind, or a plain solids split |
| `Input\MODE` | `SIMULATION`, `DESIGN` | Rate the given modules, or find how many modules reach `CONC_FACTOR` |
| `Input\MODEL` | `SHORT-CUT`, `ALTMANN` | Permeate flux: a given specific rate, or computed from the cake layer on the membrane |
| `Input\WIDTH` | LENGTH | `PLATE`: channel width |
| `Input\HEIGHT` | LENGTH | `PLATE`: channel height (gap) |
| `Input\LENGTH` | LENGTH | `PLATE`: channel length |
| `Input\NUM_CHANNEL` | int | `PLATE`: channels per module (default 2) |
| `Input\CAP_DIAMETER` | LENGTH | `CAPILLARY`: inner tube diameter |
| `Input\CAP_LENGTH` | LENGTH | `CAPILLARY`: tube length |
| `Input\CAP_NUM` | int | `CAPILLARY`: tubes per module (default 2) |
| `Input\MODULE_NUM` | int | Modules in parallel (default 1); `SIMULATION` mode |
| `Input\AVG_VELOCITY` | VELOCITY | Mean crossflow velocity in a channel or tube |
| `Input\PDROP` | PDROP | Transmembrane pressure difference |
| `Input\FILTR_RATE` | FLUX | `SHORT-CUT`: permeate volume per membrane area and time |
| `Input\POROSITY` | fraction | `ALTMANN`: void fraction of the solids deposit on the membrane |
| `Input\FILTER_RES` | FILTER-RESIS | `ALTMANN`: membrane resistance |
| `Input\CONC_FACTOR` | real | `DESIGN`: target concentration factor of the solids |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TOT_AREA` | AREA | Total membrane area |
| `Output\MODULE_AREA` | AREA | Membrane area of one module |
| `Output\CALC_CFAC` | real | Concentration factor reached |
| `Output\CIRC_FLOW` | VOLUME-FLOW | Flow circulated along the membrane |
| `Output\MOD_PDROP` | PRESSURE | Pressure loss along one module |
| `Output\REYNOLDS` | real | Reynolds number in a channel |
| `Output\CALC_FRATE` | FLUX | `ALTMANN`: computed permeate flux |
| `Output\CALC_NMOD` | int | `DESIGN`: modules needed |
| `Output\REQ_AREA` | AREA | `DESIGN`: membrane area needed |

More: [solids separator](cffilter-solids-separator.md).

Not covered: Heating curves, Utility (shared forms that this block's tree does not carry).
