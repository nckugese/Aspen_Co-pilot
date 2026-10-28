# FluidBed: outlet PSD

How the size distribution of the outlet solids is set (PSD sheet); default `COPY`. Paths are under `\Data\Blocks\{name}\`; basics in [fluidbed.md](fluidbed.md).

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_PSD` | `COPY`, `CONSTANT`, `SPEC` | Keep the inlet PSD, apply a growth model, or give a PSD |
| `Input\CONST_METHOD` | `EQUI-MASS`, `EQUI-SURFACE`, `EQUI-NUMBER`, `DELTAD-NUM`, `DELTAV-MASS`, `DELTAV-NUM` | `CONSTANT`: how mass gained or lost is spread over the size classes (EQUI-: in proportion to mass, surface or number; DELTA-: every particle grows by the same diameter or volume) |

## Given PSD (`SPEC`)

1. Set `OPT_PSD` `SPEC`, `OPT_OVERALL` `DISTFUN`, and insert a row into `Input\OV_DISTFUN`; the other `OV_*` lists get the same row `#0`.
2. Write the row's function, its parameter pair (`SPEC_OVOPT`) and those parameters, and `OV_FRACTION` 1.

| Path | Type | Purpose |
|---|---|---|
| `Input\OV_DISTFUN\{row}` | `RRSB`, `GGS`, `NORMAL`, `LOG-NORMAL` | Distribution function |
| `Input\SPEC_OVOPT\{row}` | `D50RRSB`, `MGGS`, `D50SV`, `D50GMV` | Which two parameters define it (in order: D50 + RRSB n, max size + GGS n, D50 + std. deviation, D50 + geometric deviation) |
| `Input\OV_D50\{row}` | LENGTH | Median size D50 |
| `Input\OV_DIAM\{row}` | LENGTH | Largest particle size |
| `Input\OV_RRSBN\{row}` | real | RRSB dispersion exponent |
| `Input\OV_GGSN\{row}` | real | GGS dispersion exponent |
| `Input\OV_STDDEV\{row}` | LENGTH | Standard deviation (normal) |
| `Input\OV_GMDEV\{row}` | real | Geometric deviation (log-normal) |
| `Input\OV_FRACTION\{row}` | fraction | Weight of this function when there are several rows |
