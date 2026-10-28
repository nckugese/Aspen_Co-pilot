# Filter

Separates a slurry into filtrate and cake: a simple solids separator, or a rated rotary drum, belt or disc vacuum filter with cake build-up, washing and deliquoring. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` slurry, `L(OUT)` filtrate, `S(OUT)` cake. `F2(IN)` takes wash liquid or deliquoring gas and `P2(OUT)` the wash filtrate or the deliquoring outlet; each stream on them needs its type ([washing](filter-washing.md)). `SOLIDS-SEP` is refused while a stream is on them.

The feed needs a solid substream; a working setup is calcite in a `CIPSD` substream (stream class `MIXCIPSD`) with a size distribution.

What each type needs before it can run:

`SOLIDS-SEP`: `PRES` plus the two specs that `PHASEP_OPT` names ([solids separator](filter-solids-separator.md)).

`DRUM` (models `GENERAL`, `HOLDICH`, `ALLES`): `MODEL`, `DIAM`, `WIDTH`, `REVS`, `FDELIQ_ANGLE`, `PDROP`, `DELIQ_PDROP` and the deliquoring specs `CAP_PRES` and `SCHUBERT_N`.

`BELT`: `MODEL`, `BELT_LENGTH`, `BELT_WIDTH`, `BELT_SPEED`, `FILT_AFRAC` and the same four.

`DISC`: a gas stream on `F2(IN)` and a deliquoring outlet on `P2(OUT)`, `MODEL`, `DISC_OUT_RAD`, `DISC_IN_RAD`, `DISC_DEPTH`, `DISC_SPEED` and the same four.

`BROWNELL` (drum only): `DIAM`, `WIDTH` and `REVS`; set `SOLID_FRAC` too, or the run ends with a warning.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `SOLIDS-SEP`, `DRUM`, `BELT`, `DISC` | Filter model |
| `Input\MODE` | `SIMULATION`, `DESIGN` | Rated types: rate a given filter, or size one |
| `Input\MODEL` | `GENERAL`, `HOLDICH`, `ALLES`, `BROWNELL` | Rated types: filtration model |
| `Input\PDROP` | PDROP | Pressure difference across the cake while filtering |
| `Input\DELIQ_PDROP` | PDROP | Pressure difference while deliquoring |
| `Input\MEDIUM_RES` | FILTER-RESIS | Resistance of the filter cloth |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\SRECOVERY` | fraction | Share of feed solids in the cake |
| `Output\LRECOVERY` | fraction | Share of feed liquid in the filtrate |
| `Output\CAKE_SFRAC` | fraction | Cake solids content, mass basis |
| `Output\CAKE_THICK_C` | LENGTH | Cake thickness |
| `Output\TOT_AREA` | AREA | Total filter area |
| `Output\CAKE_RES_C` | INVERSE-AREA | Cake resistance used |

More: [solids separator](filter-solids-separator.md), [simulation](filter-simulation.md), [design](filter-design.md), [filter cake](filter-cake.md), [deliquoring](filter-deliquoring.md), [washing](filter-washing.md), [convergence](filter-convergence.md).

Not covered: Heating curves, Utility (shared forms that this block's tree does not carry); Disc design (did not converge).
