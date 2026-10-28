# Mixer

Joins any number of feeds into one outlet, flashed adiabatically at the summed feed enthalpy. Paths are under `\Data\Blocks\{name}\`. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `P(OUT)` outlet, `WD(OUT)` free-water decant, `HS`/`WS`/`PS` in and out for heat, work and pseudo streams.

`F(IN)` keeps every feed connected to it; `P(OUT)` holds a single stream, and Aspen refuses a second.

Port names are exact: connect the outlet to `P(OUT)`; a bare `P` is reported as no such port.

Nothing besides the ports is required: connected feeds and an outlet are enough to run.

When the Mixer is the only block, write at least one input (e.g. `PRES` 0); left untouched, the run returns no results.

## Input | Flash Options

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES` | PRESSURE | Outlet pressure when above zero; drop below the lowest feed pressure when zero or below (default 0: the lowest feed pressure) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases checked: one, vapor-liquid (default), or vapor-liquid-liquid |
| `Input\PHASE` | `V`, `L` | The single phase; writable once `NPHASE` is `1` |
| `Input\T_EST` | TEMPERATURE | Outlet temperature guess for the flash |
| `Input\MAXIT` | int | Flash iteration limit |
| `Input\TOL` | tolerance | Flash tolerance |
| `Input\BLKOPFREWAT` | `NO`, `YES`, `DIRTY` | Free water: YES gives a pure-water phase, DIRTY one that carries some dissolved organics; with `WD(OUT)` connected it leaves there |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\B_PRES` | PRESSURE | Outlet pressure |
| `Output\B_VFRAC` | fraction | Outlet vapor fraction |
| `Output\LIQ_RATIO` | fraction | First liquid as a share of all liquid |
| `Output\PDROP` | PRESSURE | Pressure drop (negative for a rise) |

Not covered: EO added input, EO options, EO variables, EO ports, EO model options, EO specs (equation-oriented settings, not checked); Dynamics (Aspen Dynamics only).
