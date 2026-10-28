# PetroFrac convergence and estimates

Paths are under `\Data\Blocks\{name}\`.

## Convergence | Basic

| Path | Type | Purpose |
|---|---|---|
| `Input\ALGORITHM` | `STANDARD`, `SUM-RATES` | Solution algorithm |
| `Input\INIT_OPTION` | `STANDARD`, `CRUDE` | How the starting profile is made |
| `Input\MAXIT` | int | Outer-loop iteration limit |
| `Input\TOL` | real | Outer-loop tolerance |
| `Input\DAMPING` | `NONE`, `MILD`, `MEDIUM`, `SEVERE` | Damping of the outer loop |

## Estimates (rows labelled by stage)

| Path | Type | Purpose |
|---|---|---|
| `Input\TEMP_EST\{stage}` | TEMPERATURE | Temperature estimate |
| `Input\L_MOLE_FLOW\{stage}` | MOLE-FLOW | Liquid flow estimate |
| `Input\V_MOLE_FLOW\{stage}` | MOLE-FLOW | Vapor flow estimate |
| `Input\ST_TEMP_EST\{stripper}\{stage}` | TEMPERATURE | Stripper stage temperature estimate |
