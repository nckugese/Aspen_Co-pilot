# Granulator: agglomeration

`METHOD` = `AGGLOMERATIO`: particles stick together; a kernel sets how the rate depends on particle size, a prefactor how fast it is. Paths are under `\Data\Blocks\{name}\`; basics in [granulator.md](granulator.md).

A prefactor is required: `PREFACTOR` with `SPEKNLPREF` (default), or with `DETPREF` `GAS_VEL` when no gas inlet is connected.

The prefactor sets the growth: with 1e-10 the product D50 stayed at the seeds' 250 µm, with 1e-6 (`CONSTANT`) it rose to about 320 µm.

The same `PREFACTOR` grows the particles very differently per kernel: at 1e-6 `BROWNIAN` reached a D50 of 438 µm while `SUM` left the seeds unchanged. Tune it per kernel.

`DETPREF` reports the prefactor it found in `PRE_FACTOR`; a lower `GAS_VEL` or a larger `PREFACTOR_A` gave a larger one.

## Kernel and prefactor

| Path | Type | Purpose |
|---|---|---|
| `Input\KERNEL` | `CONSTANT`, `SUM`, `PRODUCT`, `COAGULATION`, `BROWNIAN`, `GRAVITATIONA`, `EKE`, `THOMPSON` | Size dependence of the rate: constant, sum, product, coagulation, Brownian, gravitational, kinetic-energy (EKE), Thompson |
| `Input\OPT_PREFAC` | `SPEKNLPREF`, `DETPREF` | Prefactor given, or found from the flux number |
| `Input\PREFACTOR` | INVERSE-TIME | `SPEKNLPREF`: the kernel prefactor |
| `Input\GAS_VEL` | VELOCITY | `DETPREF` with no gas stream: gas velocity over the empty bed |
| `Input\PREFACTOR_A` | real | `DETPREF`: correlation coefficient a (default 6e-5) |
| `Input\PREFACTOR_B` | real | `DETPREF`: correlation coefficient b (default 1.2411) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\AVERAGE` | LENGTH | Product D50 |
| `Output\DC_WIDTH1` | LENGTH | Sauter mean size (d32) of the product |
| `Output\PRE_FACTOR` | real | `DETPREF`: prefactor used |
| `Output\FLUX_AKK` | real | `DETPREF`: flux number after Akkermans |
| `Output\RES_TIME` | TIME | Mean residence time of the solids in the bed |
