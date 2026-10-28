# Compr curve scaling and fitting

Paths are under `\Data\Blocks\{name}\`. Adjusts curves given as in [compr-curves.md](compr-curves.md).

Each curve variable has a factor `<VAR>_FACTOR` (multiplies the curve) and an offset `<VAR>_OFFSET` (added, in the curve's own unit): `HEAD`, `HEADC`, `POWER`, `PRES`, `PRAT`, `DELP`, `EFF`.

The factors open once the Curve Setup fields (`OPT_CTYPE`, `NCURVES`, `INDEP_VAR`) are written.

The speed-ratio exponents (`FANEXPH` head, `FANEXPE` efficiency, `FANEXPP` power) move a `SINGLE-REFE` curve from `REF_SH_SPEED` to `ACT_SH_SPEED`.

## Performance Curves | Operating Specs

| Path | Type | Purpose |
|---|---|---|
| `Input\HEAD_FACTOR` | real | Factor on the head curve |
| `Input\EFF_FACTOR` | real | Factor on the efficiency curve |
| `Input\FANEXPH` | real | Speed-ratio exponent, head |
| `Input\FANEXPE` | real | Speed-ratio exponent, efficiency |
| `Input\FANEXPP` | real | Speed-ratio exponent, power |

## Performance Curves | Offsets

| Path | Type | Purpose |
|---|---|---|
| `Input\HEAD_OFFSET` | real | Added to the head |
| `Input\EFF_OFFSET` | real | Added to the efficiency |

## Performance Curves | Curve Setup (fitting)

| Path | Type | Purpose |
|---|---|---|
| `Input\SPLINE_FIT` | `HERMITE`, `HARWELL`, `LINEAR` | How table points are joined |
| `Input\EXTRAPOLATE` | `YES`, `NO` | Allow flows outside the table (past surge or stonewall) |
| `Input\EXTRAP_METH` | `DEFAULT`, `ENDPOINT` | How to extrapolate |
| `Input\CURVE_REG` | `NONE`, `POLY` | Fit a polynomial through the table points |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\HEAD_FAC` | real | Head factor used |
| `Output\EFF_FAC` | real | Efficiency factor used |
