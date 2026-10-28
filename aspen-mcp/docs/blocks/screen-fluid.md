# Screen: fluid split

Where the liquid or gas of the feed goes, set per deck on the Specifications sheet. Paths are under `\Data\Blocks\{name}\`; basics in [screen.md](screen.md).

Without `ENTRN_SPEC` all the fluid leaves with the fines on `U(OUT)`.

The block-level `ENTRN` does not take effect: use `ENTRN_SPEC` with `DECK_ENTRN` or `ENTRN_LOAD`.

## Fields

| Path | Type | Purpose |
|---|---|---|
| `Input\ENTRN_SPEC\1` | `EQUAL-SPLIT`, `COARSE-FRAC`, `FINES-FRAC`, `COARSE-SPLIT`, `FINES-SPLIT`, `COARSE-LOAD`, `FINES-LOAD` | How the fluid is split: like the solids, as the fluid share of the coarse or fines outlet, as the share of the feed fluid sent there, or as kg fluid per kg solids there |
| `Input\DECK_ENTRN\1` | fraction | `*-FRAC` and `*-SPLIT`: the fraction |
| `Input\ENTRN_LOAD\1` | mass ratio | `*-LOAD`: kg of fluid per kg of solids in that outlet |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\OVER_FLMASS\1` | MASS-FLOW | Fluid mass flow leaving with the coarse of deck 1 |
| `Output\UNDER_FLMASS\1` | MASS-FLOW | Fluid mass flow leaving with the fines of deck 1 |
