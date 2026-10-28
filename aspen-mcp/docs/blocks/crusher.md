# Crusher

Breaks solid particles into smaller ones. The outlet size distribution (PSD) comes from an equipment model, from the grinding power, or is given. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `P(OUT)` product, `WS(IN)` and `WS(OUT)` optional work streams.

The feed needs a solid substream with a size distribution; a working setup is calcite in `CIPSD` (stream class `MIXCIPSD`) on a mesh from 0 to 100 mm.

`PSD_CALC_MET` `EQUIPMENT` (default) needs `TYPE`. The four BOM types (gyratory, single and multiple roll, cage mill) then need only `DIAM`.

Give `BWI` (or `HGI`, see [grindability](crusher-grindability.md)): without either the run still converges but reports zero power.

`JAW` and `CONE`: [jaw and cone](crusher-jaw-cone.md). `IMPACT-MILL` and `HAMMER-MILL`: [impact mills](crusher-impact-mills.md). `BALL-MILL` and `ROD-MILL`: [power method](crusher-power.md).

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\PSD_CALC_MET` | `EQUIPMENT`, `POWER`, `USER-SPEC` | Outlet PSD from an equipment model, from the power and a distribution function ([power method](crusher-power.md)), or given ([outlet PSD](crusher-outlet-psd.md)) |
| `Input\TYPE` | `GYRATORY`, `SINGLE-ROLL`, `MULTIPLE-ROL`, `CAGE-MILL`, `JAW`, `CONE`, `IMPACT-MILL`, `HAMMER-MILL`, `BALL-MILL`, `ROD-MILL` | Equipment (`EQUIPMENT` only) |
| `Input\DIAM` | LENGTH | BOM types: largest particle size in the product |
| `Input\BREAKFN_OPT1` | `DIAM`, `SPEC`, `POWER` | BOM types: product set by `DIAM`, by `POWER_SPEC` or by `MASS_POWER` |
| `Input\POWER_SPEC` | POWER | Grinding power |
| `Input\MASS_POWER` | BOND-WORK-IN | Grinding energy per mass of solids |
| `Input\MODE` | `PRIMARY`, `SECONDARY` | BOM selection curve: first crusher on raw feed, or a later stage |
| `Input\BWI\{substream}` | BOND-WORK-IN | Bond work index of the solid substream (Grindability sheet) |
| `Input\NPHASE` | `1`, `2`, `3` | Phases in the outlet flash |
| `Input\PHASE` | `V`, `L`, `S` | The phase when `NPHASE` is 1 |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\POWER` | POWER | Grinding power |
| `Output\INLET_D80` | LENGTH | Size that 80 % of the feed solids (by mass) pass |
| `Output\OUTLET_D80` | LENGTH | Size that 80 % of the product solids pass |
| `Output\INLET_D50` | LENGTH | Median size of the feed solids |
| `Output\OUTLET_D50` | LENGTH | Median size of the product solids |
| `Output\FP_D80` | ratio | Reduction ratio, feed D80 over product D80 |
| `Output\FP_D50` | ratio | Reduction ratio, feed D50 over product D50 |
| `Output\SAUTER_IN` | LENGTH | Surface-weighted mean size (d32) of the feed |
| `Output\SAUTER_OUT` | LENGTH | Surface-weighted mean size (d32) of the product |

More: [grindability](crusher-grindability.md), [jaw and cone](crusher-jaw-cone.md), [impact mills](crusher-impact-mills.md), [BOM tables](crusher-bom-tables.md), [power method](crusher-power.md), [outlet PSD](crusher-outlet-psd.md).

Not covered: Per-substream distribution functions (`S_DISTFUN`) (writes are refused); Heating curves (a shared form that this block's tree does not carry); Utility (not checked).
