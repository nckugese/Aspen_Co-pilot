# RadFrac convergence and estimates

Paths are under `\Data\Blocks\{name}\`.

Setting `CONV_METH` (Setup) changes `ALGORITHM` to match its preset.

| Path | Type | Purpose |
|---|---|---|
| `Input\ALGORITHM` | `STANDARD`, `SUM-RATES`, `NONIDEAL`, `NEWTON` | Solution algorithm |
| `Input\MAXOL` | int | Outer-loop iteration limit |
| `Input\TOLOL` | real | Outer-loop tolerance |
| `Input\DAMPING` | `NONE`, `MILD`, `MEDIUM`, `SEVERE` | Damping for oscillating runs |
| `Input\INIT_OPTION` | `STANDARD`, `CRUDE`, `CHEMICAL`, `AZEOTROPIC`, `CRYOGENIC` | Initialization |

## Estimates (rows labelled by stage)

| Path | Type | Purpose |
|---|---|---|
| `Input\TEMP_EST\{stage}` | TEMPERATURE | Temperature estimate |
| `Input\L_MOLE_FLOW\{stage}` | MOLE-FLOW | Liquid flow estimate |
| `Input\V_MOLE_FLOW\{stage}` | MOLE-FLOW | Vapor flow estimate |
| `Input\X_EST\{stage}\{comp}` | fraction | Liquid composition estimate (two labels) |
| `Input\Y_EST\{stage}\{comp}` | fraction | Vapor composition estimate (two labels) |
