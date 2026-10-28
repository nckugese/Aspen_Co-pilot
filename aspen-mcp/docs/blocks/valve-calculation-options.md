# Valve calculation options

Choking and cavitation checks and the solver limits for `SET-PRESSURE` and `CALC-PRESSURE`. Paths are under `\Data\Blocks\{name}\`.

## Input | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\CHECK_CHOKE` | `YES`, `NO` | Test whether the flow chokes (default `YES`) |
| `Input\CALC_CAVIND` | `NO`, `YES` | Report the cavitation index (liquid) |
| `Input\CH_SET_PMIN` | `GLOBAL`, `SPECIFY`, `CHOKING` | Lowest outlet pressure `CALC-PRESSURE` may reach: the simulation's lower pressure limit, `MIN_POUT`, or the choked outlet pressure |
| `Input\MIN_POUT` | PRESSURE | That bound with `SPECIFY` |
| `Input\MAXIT` | int | Valve iteration limit (default 50) |
| `Input\TOL` | tolerance | Valve tolerance (default 1e-4) |

An outlet below `CHOKE_POUT` ends with a choked-flow warning; with `CHECK_CHOKE` `NO` the same case runs clean.

`Output\CHOK_STAT`: 1 not checked (`ADIAB-FLASH` or `CHECK_CHOKE` `NO`), 2 choked, 3 not choked.

When the outlet stays above the bound, `SPECIFY` and `CHOKING` give the same result as `GLOBAL`.

When the valve cannot pass the feed, the run ends in error and the outlet is left at the bound: near zero (`GLOBAL`), `MIN_POUT` or `CHOKE_POUT`.

`CAV_INDX` is reported only with `CALC_CAVIND` `YES`.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\CHOK_STAT` | code | Choking status |
| `Output\CHOKE_POUT` | PRESSURE | Outlet pressure at which the flow chokes |
| `Output\CAV_INDX` | number | Cavitation index |
