# FluidBed (fluidized bed)

Bubbling fluidized bed with a dense bottom zone and a dilute freeboard: bed hydrodynamics, gas distributor, elutriation of fines, optional immersed tube bundle. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` solids feed and `G(IN)` fluidizing gas (both required), `G2(IN)` secondary gas, `H(IN)` / `H(OUT)` tube-bundle medium, `P(OUT)` solids product, `G(OUT)` gas with the elutriated fines.

The solids need a size distribution: a working setup feeds calcite in a `CIPSD` substream (stream class `MIXCIPSD`, mesh 0-500 um) and nitrogen as gas, at 1.5 bar.

To run it needs `HEIGHT`, `DIAM`, `SOL_OUT_LOC`, the bed inventory (for example `BED_MASS`) and the distributor (`NUM_ORIFICE`, `DIAM_ORIFICE` for the default perforated plate).

`MINFVEL` defaults to `VEL`, which needs `MF_VEL`; `CORRE` computes it instead.

Locations (`SOL_OUT_LOC`, `FEED_LOC`, `DIA_LOC`, `HX_START_LOC`...) are fractions of `HEIGHT`, 0 bottom to 1 top: 1.5 is refused.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\BEDINV` | `BEDMASS`, `BEDPRES` | Bed inventory given as solids mass or as bed pressure drop |
| `Input\BED_MASS` | MASS | Solids held in the bed |
| `Input\BED_PDROP` | PDROP | Bed pressure drop, distributor excluded (`BEDPRES`) |
| `Input\MF_VOIDAGE` | fraction | Void fraction of the bed as it just starts to fluidize (default 0.5) |
| `Input\GELDART_TYPE` | `GELDART-A`, `GELDART-B`, `GELDART-D` | Powder class of the solids (default A) |
| `Input\MINFVEL` | `VEL`, `CORRE` | Minimum fluidization velocity given, or from a correlation |
| `Input\MF_VEL` | VELOCITY | Minimum fluidization velocity (`VEL`) |
| `Input\MF_VEL_CORR` | `WEN-YU`, `ERGUN` | Correlation for it (`CORRE`) |

## Input | Geometry

| Path | Type | Purpose |
|---|---|---|
| `Input\HEIGHT` | LENGTH | Vessel height, distributor to outlet |
| `Input\CROSS_SECT` | `CIRCULAR`, `RECTANGULAR` | Vessel cross-section ([geometry](fluidbed-geometry.md)) |
| `Input\DIAM` | LENGTH | Vessel diameter (circular, `DIAM_OPT` `CONSTANT`) |
| `Input\SOL_OUT_LOC` | fraction | Height of the solids discharge, as a fraction of `HEIGHT` |

## Input | Gas Distributor

| Path | Type | Purpose |
|---|---|---|
| `Input\NUM_ORIFICE` | int | Number of holes in the distributor plate |
| `Input\DIAM_ORIFICE` | LENGTH | Orifice diameter |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\VELOCITY` | VELOCITY | Minimum fluidization velocity |
| `Output\SOL_HOLDUP` | MASS | Solids held in the bed |
| `Output\H_BOTTOMZONE` | LENGTH | Height of the dense bottom zone |
| `Output\H_FREEBOARD` | LENGTH | Height of the freeboard above it |
| `Output\BED_DPCALC` | PDROP | Pressure drop over the bed |
| `Output\DISTR_DPCALC` | PDROP | Pressure drop over the distributor |
| `Output\TOT_DPCALC` | PDROP | Overall pressure drop |
| `Output\TEMP` | TEMPERATURE | Bed temperature |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |

More: [geometry](fluidbed-geometry.md), [gas distributor](fluidbed-distributor.md), [operation](fluidbed-operation.md), [heat exchanger](fluidbed-heat-exchanger.md), [elutriation and TDH](fluidbed-elutriation.md), [outlet PSD](fluidbed-psd.md), [convergence](fluidbed-convergence.md).

Not covered: Temperature profile (TYPE TEMP-PROF) (the V15 engine stops: only isothermal beds are supported); Outlet PSD per substream (OPT_SUBPSD SUBSID), tabular outlet PSD (OPT_OVERALL TABULAR), Reactions (RXN_ID) (not checked); Heating curves, Utility, List views (shared forms that this block's tree does not carry).
