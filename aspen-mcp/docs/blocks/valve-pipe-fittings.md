# Valve pipe fittings

Reducers between the valve and larger pipe lower its capacity (piping factor Fp). Used with `SET-PRESSURE` and `CALC-PRESSURE`. Paths are under `\Data\Blocks\{name}\`.

## Input | Pipe Fittings

| Path | Type | Purpose |
|---|---|---|
| `Input\CHK_PIPE_FIT` | `NO`, `YES` | Include the fittings |
| `Input\VALVE_DIA` | LENGTH | Valve inlet diameter |
| `Input\IN_PIPE_DIA` | LENGTH | Upstream pipe diameter |
| `Input\OUT_PIPE_DIA` | LENGTH | Downstream pipe diameter |

1. Set `CHK_PIPE_FIT` `YES`.
2. Write `VALVE_DIA`; the pipe diameters are refused until it is set.
3. Write `IN_PIPE_DIA` and `OUT_PIPE_DIA`.

4 in pipes on a 2 in valve give Fp below 1, so the valve has to open further for the same duty.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\PIPE_FIT_FAC` | number | Piping geometry factor Fp |
| `Output\COR_PREC_FAC` | number | FL corrected for the fittings |
