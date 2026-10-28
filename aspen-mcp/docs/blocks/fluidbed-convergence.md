# FluidBed: convergence

Solver settings and cell counts. Paths are under `\Data\Blocks\{name}\`; basics in [fluidbed.md](fluidbed.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\ALGORITHM` | `SOLVER`, `INTEGRATOR`, `MIXED` | Equation solver only (default), integrator start then solver, or integrator on the first pass only |
| `Input\SOLVER` | `BROYDEN`, `NEWTON` | Nonlinear method used on the mass balances |
| `Input\MAX_IT` | int | Iteration limit (default 100) |
| `Input\TOLERANCE` | real | Tolerance (default 1e-4) |
| `Input\NCELL_BOTTOM` | int | Balance cells over the bottom zone (default 100) |
| `Input\NCELL_DILUTE` | int | Balance cells over the dilute zone (default 100) |
| `Input\HOLDUP_CONV` | `ROOTN1`, `BRENT` | Root finder for the bed holdup |
| `Input\PRES_CONV` | `ROOTN1`, `BRENT` | Root-search method on the bed pressure |
| `Input\MASS_TH` | real | Bed mass tolerance, kg (`BEDMASS`) |
| `Input\PDROP_TH` | real | Allowed miss on the bed pressure drop, Pa (`BEDPRES`) |
| `Input\TINIT` | TEMPERATURE | Temperature estimate |
| `Input\MAX_TSTEP` | DELTA-T | Largest temperature step of the integrator (default 50) |
| `Input\MB_MAXIT` | int | Iteration limit of the mass balance (default 50) |
| `Input\REAC_MAXIT` | int | Iteration limit of the reaction loop (default 1000) |
| `Input\FLASH_MAXIT` | int | Flash iteration limit (default 30) |
| `Input\FLASH_TOL` | real | Flash tolerance (default 1e-4) |
