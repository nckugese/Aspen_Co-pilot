# Dryer: mass and heat transfer

Gas-side transfer of the convective dryer. Paths are under `\Data\Blocks\{name}\`; basics in [dryer.md](dryer.md).

Halving `NTU` from its default 1 left 0.0133 kg/kg in the product instead of 0.005.

`MTC_FACTOR` and `HTC_FACTOR` at 0.5 left the product wetter (0.0065).

`USEINDHEAT` `YES` with 20 kW of `INDIRECTHEAT` left the product solids 19 °C hotter.

`QLOSS_IN` and `QLOSS_OUT` cool the gas: 1 kW each lowered the exhaust by 1.1 °C.

## Input | Mass/Heat Transfer

| Path | Type | Purpose |
|---|---|---|
| `Input\MASS_OPTION` | `SPNTU`, `SHNUMBER`, `SPBETAG`, `SPBETAGA` | Mass transfer given as NTU (default), Sherwood number, coefficient, or coefficient times area |
| `Input\NTU` | real | `SPNTU`: transfer units (default 1) |
| `Input\SH_NUMBER` | real | `SHNUMBER`: Sherwood number (default 2) |
| `Input\BETAG` | VELOCITY | `SPBETAG`: mass transfer coefficient |
| `Input\BETAGA` | VOLUME-FLOW | `SPBETAGA`: coefficient times transfer area |
| `Input\HEAT_OPTION` | `LEWIS`, `ALPHAG` | Heat transfer from the mass transfer by a Lewis relation (default), or a given coefficient |
| `Input\LEWIS_N` | real | `LEWIS`: exponent of the Lewis number (default 0.3333) |
| `Input\ALPHAG` | HEAT-TRANS-C | `ALPHAG`: heat transfer coefficient |
| `Input\MTC_FACTOR` | real | Multiplier on the mass transfer coefficient (default 1) |
| `Input\HTC_FACTOR` | real | Multiplier on the heat transfer coefficient (default 1) |
| `Input\QLOSS_IN` | ENTHALPY-FLO | Heat lost at the gas inlet |
| `Input\QLOSS_OUT` | ENTHALPY-FLO | Heat lost at the gas outlet |
| `Input\USEINDHEAT` | `NO`, `YES` | Add heat through a heated wall |
| `Input\INDIRECTHEAT` | ENTHALPY-FLO | `USEINDHEAT` `YES`: heat input through the wall |
