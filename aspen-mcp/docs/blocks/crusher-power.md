# Crusher: power method

`PSD_CALC_MET` `POWER`, and `TYPE` `BALL-MILL` or `ROD-MILL`: the grinding power sets the product size through the comminution law ([grindability](crusher-grindability.md)); a distribution function gives its shape. `POWER_SPEC`, `MASS_POWER` and `BWI` are in [crusher.md](crusher.md). Paths are under `\Data\Blocks\{name}\`.

Needs `BWI` and the power: `POWER_SPEC` (`DISTFUN_OPT` `SPEC`, default), `MASS_POWER` (`MASS`), or a work stream on `WS(IN)` that carries it.

`BALL-MILL` and `ROD-MILL` need `MILL_DIAM`, `POWER_SPEC` and `BWI`.

`MASS_POWER` in its default unit `kWhr/ton` counts per short ton (907 kg): 0.8 on 1001 kg/hr of solids gave 0.88 kW.

`GGS` needs `GGS_N` (or another `PW_GGSINP` input): its default value stops the run with an error.

## Power and distribution

| Path | Type | Purpose |
|---|---|---|
| `Input\DISTFUN_OPT` | `SPEC`, `MASS` | Power given as `POWER_SPEC` or as `MASS_POWER` |
| `Input\MILL_DIAM` | LENGTH | Ball and rod mills: mill diameter |
| `Input\DISTR_FUN` | `RRSB`, `GGS`, `NORMAL`, `LOG-NORMAL` | Shape of the product PSD |
| `Input\PW_RRSBINP` | `ADRRSBN`, `ADEDER`, `RADD50`, `RADD63` | RRSB: the second input is `RRSB_N`, `STEEPNESS`, `D50` or `D63` |
| `Input\RRSB_N` | real | Spread exponent n of the RRSB curve (default 1) |
| `Input\STEEPNESS` | real | Steepness D25/D75, below 1 |
| `Input\PW_GGSINP` | `ADGGSN`, `ADDIAM`, `ADD50`, `ADD63` | GGS: the second input is `GGS_N`, `DIAM`, `D50` or `D63` |
| `Input\GGS_N` | real | Spread exponent n of the GGS curve |
| `Input\D50` | LENGTH | Product median size |
| `Input\D63` | LENGTH | Product size that 63.2 % of the mass passes |
| `Input\STDDEV` | LENGTH | `NORMAL`: standard deviation |
| `Input\GMDEV` | real | `LOG-NORMAL`: geometric mean deviation |
| `Input\INTERPOLATE` | `LINEAR`, `LIN-SPLINE`, `LOG-SPLINE` | Interpolation grid for the PSD |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\POWER` | POWER | Grinding power used |
| `Output\OUTLET_D80` | LENGTH | Size that 80 % of the product solids pass |
| `Output\MILL_DIAM` | LENGTH | Ball and rod mills: mill diameter |
