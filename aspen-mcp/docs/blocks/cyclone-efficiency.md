# Cyclone: efficiency table and solids loading

Paths are under `\Data\Blocks\{name}\`; basics in [cyclone.md](cyclone.md).

## Input | Efficiency (`METHOD` = `USER`)

1. Insert one row per particle size into `Input\DIAM_PART` (`insert_row`); `EFFIC` gets the same rows.
2. Write `DIAM_PART\{row}` (rising sizes) and `EFFIC\{row}`.

`METHOD` = `USER` needs the efficiencies filled in.

With several fits switched on the block keeps the best; `Output\BESTFIT` says which (1 Plitt, 2 Rogers, 4 Whiten, 8 Molerus).

| Path | Type | Purpose |
|---|---|---|
| `Input\DIAM_PART\{row}` | LENGTH | Particle size of the row |
| `Input\EFFIC\{row}` | fraction | Share of particles of that size collected |
| `Input\INTERPOLATE` | `LINEAR`, `LIN-SPLINE`, `LOG-SPLINE`, `FITTING` | Between the points: linear (default), spline on a linear or on an RRSB grid, or a fitted curve |
| `Input\OPT_ROGERS` | `YES`, `NO` | `FITTING`: try the Rogers curve |
| `Input\OPT_PLITT` | `YES`, `NO` | `FITTING`: try the Plitt curve |
| `Input\OPT_MOLERUS` | `YES`, `NO` | `FITTING`: try the Molerus curve |
| `Input\OPT_WHITEN` | `YES`, `NO` | `FITTING`: try the Whiten curve |

## Input | Solids Loading

Every method except `MUSCHELKNAUT` uses these: above the critical loading the efficiency and the drop are corrected.

`PRES_CON1` and `PRES_CON2` go together.

| Path | Type | Purpose |
|---|---|---|
| `Input\CR_SOL_LOAD` | MASS-CONC | Critical solids loading of the feed gas |
| `Input\EFF_CON1` | real | Exponent of the efficiency correction |
| `Input\PRES_CON1` | real | Factor of the pressure drop correction |
| `Input\PRES_CON2` | real | Exponent of the pressure drop correction |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\FIT_D50` | LENGTH | Cut size of the fitted curve |
| `Output\EFF_OUT` | fraction | Share of the feed solids collected |
