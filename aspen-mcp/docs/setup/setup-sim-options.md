# Simulation options

Defaults that every block uses unless its own Block Options set them.

Root: `\Data\Setup`

## Calculations

| Path | Type | Purpose |
|---|---|---|
| `Sim-Options\Input\FLASH_METHOD` | `INSIDE-OUT`, `GIBBS` | Flash algorithm |
| `Sim-Options\Input\MAXIT` | int | Flash iterations allowed |
| `Sim-Options\Input\TOL` | real | Flash tolerance |
| `Sim-Options\Input\TLOWER` | TEMPERATURE | Lowest temperature a flash may try |
| `Sim-Options\Input\TUPPER` | TEMPERATURE | Highest temperature a flash may try |
| `Sim-Options\Input\PLOWER` | PRESSURE | Lowest pressure a flash may try |
| `Sim-Options\Input\PUPPER` | PRESSURE | Highest pressure a flash may try |
| `Sim-Options\Input\ENERGY_BAL` | `YES`, `NO` | `NO`: mass balances only, block duties stay empty |
| `Sim-Options\Input\RESTART` | `NO`, `YES` | Start blocks from the last run's results |

## Checks

| Path | Type | Purpose |
|---|---|---|
| `Sim-Options\Input\MASS_BAL_CHE` | `YES`, `NO` | Verify that each block conserves mass |
| `Sim-Options\Input\MASS_BAL_TOL` | real | Relative tolerance of that check |
| `Sim-Options\Input\STOIC_MB_CHE` | `ERROR`, `WARNING` | How a reaction whose stoichiometry is not mass-balanced is reported |
| `Sim-Options\Input\STOIC_MB_TOL` | real | Tolerance of the stoichiometry check |
