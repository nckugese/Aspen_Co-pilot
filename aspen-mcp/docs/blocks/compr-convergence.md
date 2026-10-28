# Compr convergence

Paths are under `\Data\Blocks\{name}\`.

## Setup | Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\NPHASE` | `1`, `2`, `3` | Phases allowed in the outlet flash: vapor only, vapor-liquid, vapor-liquid-liquid |
| `Input\MAXIT` | int | Iterations of the outlet flash |
| `Input\TOL` | real | Tolerance of the outlet flash |
| `Input\PS_FLASH` | `ITERATIVE`, `DIRECT` | How the constant-entropy flash is solved |
| `Input\SB_MAXIT` | int | Iterations of the outer loop (outlet spec) |
| `Input\SB_TOL` | real | Tolerance of that loop |
