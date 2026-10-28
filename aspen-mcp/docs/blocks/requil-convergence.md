# REquil convergence and entrainment

Paths are under `\Data\Blocks\{name}\`.

## Input | Convergence

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Most flash iterations |
| `Input\TOL` | real | Flash tolerance |
| `Input\CHEM_MAXIT` | int | Most iterations of the chemical equilibrium loop |
| `Input\CHEM_TOL` | real | Tolerance of the chemical equilibrium loop |
| `Input\MB_TOLFAC` | real | Factor on the tolerance of the mass balance check |
| `Input\T_EST` | TEMPERATURE | Temperature guess, when the spec leaves the temperature to be found |
| `Input\P_EST` | PRESSURE | Pressure guess, when the spec leaves the pressure to be found |

## Input | Entrainment

| Path | Type | Purpose |
|---|---|---|
| `Input\ENTRN` | fraction | Share of the liquid carried out with the vapor in `V(OUT)` |

`ENTRN` 0.1 adds a tenth of each liquid flow to the vapor outlet.
