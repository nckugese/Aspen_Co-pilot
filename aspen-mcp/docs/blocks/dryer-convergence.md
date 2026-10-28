# Dryer: convergence

Solver settings of the dryer models. Paths are under `\Data\Blocks\{name}\`; basics in [dryer.md](dryer.md).

Each type passes only its own settings to the run (checked in the engine's input echo); the rest are dropped silently.

## Convective

| Path | Type | Purpose |
|---|---|---|
| `Input\MAXIT` | int | Iteration limit (default 30) |
| `Input\MOIST_TOL` | real | Tolerance on the gas moisture (default 1e-5) |
| `Input\TEMP_TOL` | DELTA-T | Temperature tolerance (default 1 K) |

## Spray and contact

| Path | Type | Purpose |
|---|---|---|
| `Input\TOL` | real | Solver tolerance (default 1e-4) |
| `Input\MAX_NSTEP` | int | Solver step limit (default 10000) |
| `Input\INIT_STEP` | LENGTH | First solver step |

## Convective, spray and contact

| Path | Type | Purpose |
|---|---|---|
| `Input\NPOINT` | int | Most intervals in the profile (default 100) |
| `Input\VAPPFACT` | real | A component counts as moisture only while this times its vapor pressure stays below the pressure (default 0.5) |

## All types

| Path | Type | Purpose |
|---|---|---|
| `Input\FLASH_MAXIT` | int | Flash iteration limit (default 30) |
| `Input\FLASH_TOL` | real | Flash tolerance (default 1e-4) |
