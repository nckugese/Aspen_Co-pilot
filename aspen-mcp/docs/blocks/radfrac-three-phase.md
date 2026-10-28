# RadFrac with two liquid phases

Paths are under `\Data\Blocks\{name}\`. For a second liquid on the stages and for decanters, set `NO_PHASE` to 3 first.

| Path | Type | Purpose |
|---|---|---|
| `Input\NO_PHASE` | int | 3 checks every stage in the range below for a second liquid |
| `Input\TRAY2\{stage}` | int | Range checked for two liquids: label = first stage, value = last stage |
| `Input\COMP_LIST\{row}` | component | Key component that marks the second liquid (list without labels) |
| `Input\BLKOPFREWAT` | `YES`, `NO`, `DIRTY` | Free water decanted on `WD(OUT)` (`YES` or `DIRTY`); runs with `NO_PHASE` 2 |

With free water, give the distillate `PROD_PHASE\{stream}` `L1`; the `WD(OUT)` stream gets `W` by itself. Left at `L`, the run stops in input translation.

With `NO_PHASE` 3 keep `CONV_METH` `STANDARD`. `PETROLEUM` sets `ALGORITHM` `SUM-RATES`, which ignores `TRAY2` and `COMP_LIST`: the column is solved with one liquid and ends with a warning that the liquid may be unstable (BLKSTAT 2).

## Decanters

1. `add_element` on `Subobjects\Decanters` with a stage number as ID (`1` is the condenser); other IDs are refused.

| Path | Type | Purpose |
|---|---|---|
| `Input\L1_SPEC\{dec}` | fraction | Share of the first liquid returned |
| `Input\L2_SPEC\{dec}` | fraction | Share of the second liquid returned |

Give `L1_SPEC` or `L2_SPEC`, not both: writing one locks the other.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_DEC_TEMP\{dec}` | `TEMP`, `SUBCOOL` | Decanter given by temperature or subcooling |
| `Input\DEC_TEMP\{dec}` | TEMPERATURE | Decanter temperature |

To take the second liquid out on its own, put a stream on `SP(OUT)` at stage 1 with `PROD_PHASE` `L2` and give the distillate `PROD_PHASE` `L1`.
