# Makeup: flash options

How the outlet is flashed once the makeup flows are set. Paths are under `\Data\Blocks\{name}\`; the targets are in [makeup.md](makeup.md).

Defaults: `SPEC_OPT` `DUTY` with `DUTY` 0 (an adiabatic mix), `NPHASE` 2, `MAXIT` 30.

## Input | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\SPEC_OPT` | `DUTY`, `TEMP` | Outlet fixed by a heat duty (default) or by a temperature |
| `Input\TEMP` | TEMPERATURE | Outlet temperature, used when `SPEC_OPT` is `TEMP` |
| `Input\DUTY` | ENTHALPY-FLO | Heat added to the outlet (negative removes it), used when `SPEC_OPT` is `DUTY` |
| `Input\PRES` | PRESSURE | Outlet pressure when above zero; a drop below the lowest feed pressure when zero or below (default 0: the lowest feed pressure) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases checked in the flash: one, vapor-liquid (default) or vapor-liquid-liquid |
| `Input\PHASE` | `V`, `L` | The single phase when `NPHASE` is `1` |
| `Input\T_EST` | TEMPERATURE | Starting guess for the outlet temperature |
| `Input\MAXIT` | int | Flash iteration limit |
| `Input\TOL` | tolerance | Flash tolerance (default 1e-4) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\<outlet>\Output\TEMP_OUT\MIXED` | TEMPERATURE | Outlet temperature (base: 46.8 C) |
| `\Data\Streams\<outlet>\Output\PRES_OUT\MIXED` | PRESSURE | Outlet pressure |
