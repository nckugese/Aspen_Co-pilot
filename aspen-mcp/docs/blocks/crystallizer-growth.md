# Crystallizer: growth kinetics

`OPT_PSD` = `GROWTH`: the size distribution from nucleation and growth in a well-mixed vessel of volume `VOL`. Needs the `CIPSD` substream. Paths are under `\Data\Blocks\{name}\`; basics in [crystallizer-psd.md](crystallizer-psd.md).

It needs `VOL` and `KBO`.

Nucleation rate = `KBO` G^`BNI` M^`BNJ` N^`BNK`, with G the growth rate, M the magma density in kg/l and N the agitator speed `RATE` in rev/s: both runs matched it.

## Setup | Crystal Growth

| Path | Type | Purpose |
|---|---|---|
| `Input\VOL` | VOLUME | Crystallizer volume; sets the residence time |
| `Input\KBO` | real | Nucleation rate constant |
| `Input\BNI` | real | Exponent on the growth rate (default 1) |
| `Input\BNJ` | real | Exponent on the magma density (default 1) |
| `Input\BNK` | real | Exponent on the agitator speed (default 0) |
| `Input\RATE` | FREQUENCY | Agitator speed |
| `Input\GAMMA` | real | Size-dependent growth: size coefficient (default 0, no size effect) |
| `Input\ALPHA` | real | Power on the size term of growth (default 0) |
| `Input\VOLUME_SHAPE` | real | Crystal volume over its size cubed (default 1) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\VOLUME` | VOLUME | Crystallizer volume |
| `Output\RES_TIME` | TIME | Residence time |
| `Output\FLUID_VEL` | VELOCITY | Growth rate |
| `Output\SEC_NUC` | real | Nucleation rate |
| `Output\MOMENT0` | real | Zeroth moment of the distribution (crystal count) |
| `Output\STAND_DEV` | LENGTH | Spread of crystal sizes (one sigma) |
| `Output\COEFF_VAR` | percent | Coefficient of variation |
| `Output\SKEWNESS` | real | Skewness |
