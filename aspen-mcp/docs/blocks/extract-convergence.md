# Extract convergence and estimates

Paths are under `\Data\Blocks\{name}\`.

## Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXOL` | int | Outside-loop iteration limit |
| `Input\TOLOL` | real | Outside-loop tolerance |
| `Input\OLMETH` | `BROYDEN`, `WEGSTEIN` | Outside-loop method |
| `Input\MAXIL` | int | Inside-loop iteration limit |
| `Input\ILMETH` | `BROYDEN`, `WEGSTEIN`, `COMBINED` | Inside-loop method |
| `Input\TOLIL0` | real | Tolerance the inside loop begins with |
| `Input\MAIN` | int | History detail of the convergence (diagnostics) |
| `Input\TERM` | int | Control-panel detail of the iterations (diagnostics) |

## Estimates

`X1_EST` and `X2_EST` share their rows: a stage or component row added to one is there in the other. Give both on the same stages.

| Path | Type | Purpose |
|---|---|---|
| `Input\X1_EST\{stage}\{comp}` | fraction | Initial guess of the 1st liquid composition; a stage row, then a component row |
| `Input\X2_EST\{stage}\{comp}` | fraction | Initial guess of the 2nd liquid composition |

Temperature estimates `TEMP_EST\{stage}`: [extract.md](extract.md).
