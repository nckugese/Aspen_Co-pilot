# SCFrac

Shortcut model of a complex column such as a crude or vacuum tower: a stack of sections, each splitting what reaches it into two products, with the sharpness set by a fractionation index (FI). Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` the feed, `SF(IN)` optional stripping steam, `D(OUT)` distillate, `SP(OUT)` one or more side products, `B(OUT)` bottoms.

`WATER` must be in the component list even when no steam is used: without it the block stops at initialization.

Sections count from the top. Section 1 holds the distillate (`TYPE` `O`) and one more product with `TYPE` `B`; every other product gets a section of its own, and the bottoms default to the last section (n-1 for n products). Set `SECNO` before `TYPE`.

Exactly 2(n-1) specs: the Specs rows plus each fixed `FINDEX`. `FIEST`, `FIHEAVY` and `FIRATIO` do not count.

Each product needs `FLOW_EST` or `FEED_FRAC` (not both) unless a flow spec names it.

Every product needs `PROD_PRES`, and every product except the distillate a `STEAM:PROD` ratio (0 for no steam); until then the block counts as incomplete.

A flow spec on both section-1 products is refused.

## Input | Connect

| Path | Type | Purpose |
|---|---|---|
| `Input\SECNO\{stream}` | int | Section the product leaves, numbered from the top |
| `Input\TYPE\{stream}` | `O`, `B` | Section 1 only: top (`O`) or bottom (`B`) of the section |
| `Input\FLOW_EST\{stream}` | flow | Product flow estimate, on `FLOW_BASIS` |
| `Input\FLOW_BASIS\{stream}` | `MOLE`, `MASS`, `STDVOL` | Basis of `FLOW_EST` |
| `Input\FEED_FRAC\{stream}` | fraction | Estimate as a fraction of the feed, on `FRAC_BASIS` |
| `Input\FRAC_BASIS\{stream}` | `MOLE`, `MASS`, `STDVOL` | Basis of `FEED_FRAC` |
| `Input\PROD_PRES\{stream}` | PRESSURE | Product pressure |

## Input | Condenser

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES` | PRESSURE | Condenser pressure |
| `Input\OPT_COND` | `RDV`, `TEMP` | Second condenser spec: distillate vapor fraction or temperature |
| `Input\RDV` | fraction | Distillate vapor fraction: 1 (default) vapor, 0 liquid |
| `Input\TEMP` | TEMPERATURE | Distillate temperature (`OPT_COND` `TEMP`) |
| `Input\DEGSUB` | DELTA-T | Subcooling of a liquid distillate (`RDV` 0) |

## Input | Specs

1. `insert_row` on `Input\SPECTYPE` with a spec ID as the label; the spec's other fields get rows with the same ID.
2. For a purity or recovery, add unlabelled rows (`#0`, `#1`, ...) on `Input\COMPS\{spec}`, one component each.

| Path | Type | Purpose |
|---|---|---|
| `Input\SPECTYPE\{spec}` | `MOLE-FRAC`, `MASS-FRAC`, `STDVOL-FRAC`, `MOLE-RECOV`, `MASS-RECOV`, `STDVOL-RECOV`, `MOLE-FLOW`, `MASS-FLOW`, `STDVOL-FLOW`, `PROP`, `PROP-DIFF`, `PROP-RATIO` | Spec type: purity (`-FRAC`), recovery, flow, or a property |
| `Input\VALUE\{spec}` | real | Target, in the block's units for that type; purity and recovery as fractions |
| `Input\SPEC_STREAM\{spec}` | stream | Product the target applies to |
| `Input\COMPS\{spec}\{row}` | component | Components counted; a flow spec with none counts the whole product |

## Input | Frac Index

Rows are labelled with the section number (`insert_row` + label).

| Path | Type | Purpose |
|---|---|---|
| `Input\FINDEX\{section}` | real | Fixed FI of the section; counts as a spec |
| `Input\FIEST\{section}` | real | Starting FI for a section the specs solve |
| `Input\FIHEAVY\{section}` | real | Own FI for the heavy components (`FINDEX`/`FIEST` then cover the light ones) |
| `Input\FIRATIO\{section}` | real | Heavy-to-light FI ratio; one of `FIHEAVY`, `FIRATIO` per section |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Condenser temperature |
| `Output\VAP_FLOW` | MOLE-FLOW | Vapor distillate flow |
| `Output\LIQ_FLOW` | MOLE-FLOW | Liquid distillate flow |
| `Output\FINDEX_OUT\{section}` | real | FI of each section |
| `Output\ACT_STAGES\{section}` | real | Theoretical stages of each section |
| `Output\DUTY\{section}` | ENTHALPY-FLO | Heat removed in each section |
| `Output\B_TEMP2\{stream}` | TEMPERATURE | Product temperature |
| `Output\B_MOLEFLOW\{stream}` | MOLE-FLOW | Product flow |
| `Output\CALC\{spec}` | real | Value each spec reached |

More: [steam and free water](scfrac-steam.md), [property specs](scfrac-property-specs.md), [convergence](scfrac-convergence.md).

Not covered: Heating curves, Heating curves (2D), Utilities, List dialogs (no such objects in this block's tree); Dirty free water (`BLKOPFREWAT` `DIRTY`) (not checked).
