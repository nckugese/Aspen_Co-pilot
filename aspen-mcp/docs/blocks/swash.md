# SWASH (one-stage solids wash)

One ideal washing stage: the slurry is mixed with wash liquid and settles into washed solids carrying a set amount of liquid, and the wash liquor. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `S(IN)` slurry, `L(IN)` wash liquid, `S(OUT)` washed solids with their retained liquid, `L(OUT)` wash liquor; `HS(IN)`/`HS(OUT)` heat streams ([calculation](swash-calculation.md)).

The slurry needs a solid substream; a working setup is calcite in `CISOLID` (stream class `MIXCISLD`), with a solute such as methanol dissolved in the water to wash out.

To run it needs only `LS_RATIO`.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\LS_RATIO` | mass ratio, >= 0 | Liquid carried per mass of solids in `S(OUT)` |
| `Input\MIX_EFF` | fraction 0-1 | Mixing efficiency (default 1) |

`LS_RATIO` 0.5 gave 0.5 kg liquid per kg solids in `S(OUT)` and no solids in `L(OUT)`.

With `MIX_EFF` below 1 a share `1 - MIX_EFF` of the liquid leaving with the solids is unwashed slurry liquid: at 0.7 more methanol stayed with the solids, and `BYPASS` reported that liquid as a fraction of the slurry liquid.

## Input | Flash Options

Without `PRES`, `TEMP` or `DUTY` the stage is adiabatic at the feed pressure.

Give `TEMP` or `DUTY`, not both; `T_EST` is refused once `TEMP` is set.

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES` | PRESSURE | Outlet pressure; 0 or less is a drop from the lowest feed pressure |
| `Input\TEMP` | TEMPERATURE | Outlet temperature; the block computes the duty |
| `Input\DUTY` | ENTHALPY-FLO | Heat added; the block computes the temperature |
| `Input\T_EST` | TEMPERATURE | Starting guess for the outlet temperature |

`PRES` -0.1 bar gave outlets 0.1 bar below the feeds; `TEMP` 50 C held 50 C and `DUTY` 50 kW gave `QCALC` 50 kW.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
| `Output\QNET` | ENTHALPY-FLO | Net duty: `QCALC` less the inlet heat streams |
| `Output\BYPASS` | fraction | Slurry liquid that bypassed mixing |

More: [calculation options and heat streams](swash-calculation.md).

Not covered: Heating curves, Utility (shared forms that this block's tree does not carry).
