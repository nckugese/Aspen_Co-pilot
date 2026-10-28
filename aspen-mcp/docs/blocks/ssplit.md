# SSplit

Divides its feed among several outlets with a separate split for each substream, e.g. the liquid (`MIXED`) one way and the solid (`CISOLID`) another; within a substream every outlet has the feed's composition. Paths are under `\Data\Blocks\{name}\`; `{stream}` is an outlet stream, `{substream}` a substream of the stream class. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed and `P(OUT)` outlets; there are no heat or work ports.

`P(OUT)` takes any number of streams. Each outlet gets one row per substream in each spec table, e.g. `Input\FRAC\{stream}\MIXED` and `...\CISOLID`.

To run it needs, for every substream, one spec on every outlet but one; the free outlet takes what is left of that substream.

Leave that outlet free: a spec on every outlet of a substream makes the block incomplete again, even when the fractions add up to 1.

One spec per outlet and substream: a flow on a cell that has a fraction is refused. Clear the fraction (write `""`) first.

## Input | Specifications (one per outlet and substream)

| Path | Type | Purpose |
|---|---|---|
| `Input\FRAC\{stream}\{substream}` | fraction | Split fraction: share of the feed's substream sent to this outlet |
| `Input\BASIS_FLOW\{stream}\{substream}` | MOLE-FLOW | Flow of the substream to this outlet (molar unless a basis is given) |

For a mass or standard-volume flow call `set_value` with `basis='MASS'` (or `'STDVOL'`) and a unit of that basis.

Writing `Input\FLOW_BASIS\{stream}\{substream}` on its own does not do this: the number is still taken in kmol/hr.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\STREAMFRAC\{stream}\{substream}` | fraction | Fraction of the substream each outlet got |
| `\Data\Streams\{stream}\Output\MASSFLMX\{substream}` | MASS-FLOW | Mass flow of the substream in an outlet stream |

More: [key components](ssplit-key-components.md), [flash options](ssplit-flash-options.md).

Not covered: none.
