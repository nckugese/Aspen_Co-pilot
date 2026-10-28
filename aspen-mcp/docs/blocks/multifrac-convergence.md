# MultiFrac convergence and estimates

Paths are under `\Data\Blocks\{name}\`.

## Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\ALGORITHM` | `STANDARD`, `SUM-RATES`, `NEWTON` | Solution method |
| `Input\INIT_OPTION` | `STANDARD`, `CRUDE` | How the first profiles are built |
| `Input\DAMPING` | `NONE`, `MILD`, `MEDIUM`, `SEVERE` | Damping of the outer loop |
| `Input\MAXOL` | int | Outer-loop iteration limit (default 25) |
| `Input\TOLOL` | real | Outer-loop tolerance (default 1e-4) |
| `Input\MAXIL` | int | Inner-loop iteration limit |

## Estimates

| Path | Type | Purpose |
|---|---|---|
| `Input\X_EST\{col}\{stage}\{comp}` | fraction | Liquid mole fraction estimate (two labels on `X_EST\{col}`: the stage on index 0, the component on index 1) |
| `Input\Y_EST\{col}\{stage}\{comp}` | fraction | Estimate of the vapor composition, mole basis (same layout) |

`X_EST` and `Y_EST` share their rows: a row inserted on one appears on the other, and inserting it again is refused.

| Path | Type | Purpose |
|---|---|---|
| `Input\L_MOLE_FLOW\{col}\{stage}` | MOLE-FLOW | Liquid flow estimate (row labelled by the stage) |
| `Input\V_MOLE_FLOW\{col}\{stage}` | MOLE-FLOW | Vapor flow estimate (row labelled by the stage) |
