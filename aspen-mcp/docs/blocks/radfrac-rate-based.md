# RadFrac rate-based

Paths are under `\Data\Blocks\{name}\`. Rate-based stages need internals: [radfrac-internals.md](radfrac-internals.md).

1. Add internals and a section and run once in `INTER-SIZING` to get a diameter.
2. Copy the diameter into `CA_DIAM`, set `CA_SIZING=RATING` and `CA_RATE_BASE=YES` on the section, then `CALC_MODE=RIG-RATE` and run.

Without a diameter, `RATING` does not run.

| Path | Type | Purpose |
|---|---|---|
| `Input\CALC_MODE` | `RIG-RATE`, `EQUILIBRIUM` | Rate-based for the column |
| `Input\CA_RATE_BASE\{int}\{sec}` | `YES`, `NO` | Section is rate-based |
| `Input\RS_MAXIT` | int | Rate-based iteration limit (default 25); raise it when the run stops at the limit |
| `Input\CA_LIQ_FILM\{int}\{sec}` | `NOFILM`, `FILM`, `FILMRXN`, `DISCRXN` | Liquid film model (default `FILMRXN`); `CA_VAP_FILM` for the vapor |
| `Input\CA_NLPOINTS\{int}\{sec}` | int | Points in the discretized liquid film (`DISCRXN`); `CA_NVPOINTS` for the vapor |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP\{stage}` | TEMPERATURE | Stage temperature (rate-based run) |
