# FSplit

Divides its feed into several outlets of the same composition, temperature and phase. Paths are under `\Data\Blocks\{name}\`; `{stream}` below is an outlet stream. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `P(OUT)` outlets, `HS`/`WS`/`PS` in and out for heat, work and pseudo streams.

`P(OUT)` takes any number of streams: connect each one to it. Every outlet then gets a row in each spec table below.

To run it needs one spec on every outlet but one; that last outlet takes whatever is left.

One spec per outlet: a second spec on the same outlet is refused. Clear the first one (write `""`) before setting another.

Once every other outlet has a spec, the free outlet's rows can no longer be written.

## Input | Specifications (one per outlet)

| Path | Type | Purpose |
|---|---|---|
| `Input\FRAC\{stream}` | fraction | Split fraction: share of the total feed |
| `Input\BASIS_FLOW\{stream}` | MOLE-FLOW | Outlet rate (molar unless a basis is given) |
| `Input\VOL_FLOW\{stream}` | VOLUME-FLOW | Actual volume flow of the outlet |
| `Input\BASIS_LIMIT\{stream}` | MOLE-FLOW | Limit flow: the outlet gets this flow, or less when less is left |
| `Input\VOL_LIMIT\{stream}` | VOLUME-FLOW | Limit on the actual volume flow |
| `Input\R_FRAC\{stream}` | fraction | Residual fraction: share of what earlier outlets left |
| `Input\ORDER\{stream}` | int | Calculation order of the outlet (for limits and residual fractions) |
| `Input\BASIS_C_LIM\{stream}` | MOLE-FLOW | Cumulative limit: this outlet plus the outlets computed before it |
| `Input\VOL_C_LIM\{stream}` | VOLUME-FLOW | Cumulative limit on actual volume flow |

`BASIS_FLOW` on a mass or standard-volume basis: `set_value` with `basis='MASS'` (or `'STDVOL'`) and a unit of that basis.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STREAMFRAC\{stream}` | fraction | Split fraction each outlet got |
| `Output\STREAM_ORDER\{stream}` | int | Order the outlets were computed in |
| `Output\B_PRES` | PRESSURE | Outlet pressure |

More: [key components](fsplit-key-components.md), [flash options](fsplit-flash-options.md).

Not covered: EO Options (equation-oriented options, not checked); EO specs (equation-oriented variable specs, not checked).
