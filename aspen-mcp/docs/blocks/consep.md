# ConSep

Conceptual column design for three components: from three product specs and a reflux (or boilup) ratio it finds the stages, feed stage and duties, and checks that the split is feasible. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `D(OUT)` distillate, `B(OUT)` bottoms; `HS` and `WS` (IN and OUT) take heat and work streams, but a heat stream on `HS(OUT)` gets no duty (0).

To run it needs `SELCOMP1`-`SELCOMP3`, `P_SPEC`, three product specs and the ratio `OPT_RB` selects.

The three selected components must differ; a repeat is refused. With more than three components in the feed, map the others: [consep-component-map.md](consep-component-map.md).

Product specs: exactly three, mixed freely from the recoveries and compositions of both products. A fourth is refused; clear one (write `""`) first.

Index `<n>` (1-3) in a spec name is the selected component `SELCOMP<n>`. A recovery is the share of its feed leaving in that product; a composition is its fraction there, strictly between 0 and 1 (up to 0.999998).

## Input | Setup

| Path | Type | Purpose |
|---|---|---|
| `Input\SELCOMP1` | component | First selected component (`SELCOMP2`, `SELCOMP3` the same) |
| `Input\P_SPEC` | PRESSURE | Column pressure |
| `Input\IMODE` | `DESIGN` | Calculation mode; `DESIGN` sizes the column |
| `Input\IPHASE` | `VL`, `VLL` | Phases checked: vapor-liquid, or with a second liquid |
| `Input\ICONFIG` | `NO-DECANTER`, `DECANTER` | Column alone, or with a decanter on the condensed top vapor ([consep-decanter.md](consep-decanter.md)) |
| `Input\IBASIS` | `MOLE`, `MASS` | Basis of the compositions and of the reflux / boilup ratio |

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\DISTRECO1` | fraction | Recovery of component 1 in the distillate |
| `Input\BOTRECO1` | fraction | Recovery of component 1 in the bottoms |
| `Input\DISTC1MO` | fraction | Distillate content of component 1, mole basis |
| `Input\BOTC1MO` | fraction | Bottoms content of component 1, mole basis |
| `Input\DISTC1MA` | fraction | Mass fraction (`IBASIS` `MASS`); `BOTC1MA` for the bottoms |
| `Input\OPT_RB` | `RR`, `BR` | Which ratio is given: reflux or boilup |
| `Input\MOLE_RR` | ratio | Reflux ratio, mole basis |
| `Input\MOLE_BR` | ratio | Boilup ratio, mole basis (`OPT_RB` `BR`) |
| `Input\MASS_RR` | ratio | Reflux ratio, mass basis (`IBASIS` `MASS`) |
| `Input\MASS_BR` | ratio | Boilup ratio, mass basis |

## Results (after a run)

Stage counts are not rounded: `ACT_STAGES2` = `RECT_STAGES2` (rectifying) + `STAGE_NO1` (stripping), the feed stage is `RECT_STAGES2` + 1, and the profiles list `ACT_STAGES2` rounded up.

`RR2` and `BR2` are both filled whichever ratio was given.

| Path | Type | Purpose |
|---|---|---|
| `Output\ACT_STAGES2` | real | Stages, condenser and reboiler included |
| `Output\FEED_LOCATN2` | real | Feed stage |
| `Output\RR2` | ratio | Reflux ratio |
| `Output\BR2` | ratio | Boilup ratio |
| `Output\COND_DUTY2` | ENTHALPY-FLO | Condenser duty, negative |
| `Output\REB_DUTY2` | ENTHALPY-FLO | Reboiler duty |
| `Output\DISTIL_TEMP2` | TEMPERATURE | Distillate temperature |
| `Output\BOTTOM_TEMP2` | TEMPERATURE | Bottoms temperature |
| `Output\F2` | MOLE-FLOW | Distillate rate (`F3` bottoms, `F1` feed) |
| `Output\X2\{i}` | fraction | Distillate composition per selected component (`X3` bottoms, `X1` feed) |
| `Output\B_TEMP4\{stage}` | TEMPERATURE | Temperature profile |
| `Output\X10\{stage}\{i}` | fraction | Liquid profile per stage and selected component (`Y` vapor) |

More: [decanter](consep-decanter.md), [component map](consep-component-map.md), [advanced options](consep-advanced-options.md).

Not covered: Interactive design (`INTERACT` `YES` opens a GUI design window, not checked); Ternary plot options (curve and envelope choices of the GUI plot, not stored in the tree); Material-balance mode (did not converge).
