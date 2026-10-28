# Charge Balance (ChgBal)

Rescales the ions of one electrolyte stream so its positive and negative charge flows agree. Paths are under `\Data\Blocks\{name}\`. Rules shared by all blocks: [common.md](common.md).

Place it with record type `CHARGEBAL`; `CHGBAL` is refused as an unknown model.

Ports: `F(IN)` inlet, `P(OUT)` outlet.

No field is required: a block left untouched runs with every field at its default.

The cation flows are scaled by one factor and the anion flows by another so that both charge flows end at their average; water and other neutral species pass unchanged (inlet NA+ 1.0 / CL- 0.9 leaves as 0.95 / 0.95).

Aspen already balances the charge of a feed stream it is given, so the block has work to do only after a unit that splits ions unevenly, such as a `SEP` with component fractions.

Rescaling changes the mass flow, so with the global mass-balance check on (the default) the block ends with an error and a mass-imbalance message. Set `\Data\Setup\Sim-Options\Input\MASS_BAL_CHE` to `NO` to run it clean.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\MESSAGE` | `NONE`, `INFORMATION`, `WARNING`, `ERROR` | What to report when the inlet imbalance exceeds `TOL`; default NONE |
| `Input\TOL` | number | Imbalance allowed before the message is raised (default 1e-4) |
| `Input\CUTOFF` | number | Charge flow, in kmol/s, under which the imbalance is judged in absolute terms rather than relative ones (default 1e-10) |

An inlet out of tolerance with `WARNING` leaves the block at status 2, with `ERROR` at 1, though the outlet is balanced either way; `NONE` and `INFORMATION` keep it at 0.

Example: NA+ 1.0 and CL- 0.9 kmol/hr with `TOL` 0.05 raises the message; with `CUTOFF` 0.001 the same inlet is judged on its absolute error (about 3e-5 kmol/s) and passes.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\POS_FLOW` | MOLE-FLOW | Charge carried in by the cations |
| `Output\NEG_FLOW` | MOLE-FLOW | Charge carried in by the anions |
| `Output\POS_FACTOR` | factor | Multiplier applied to the cation flows |
| `Output\NEG_FACTOR` | factor | Multiplier applied to the anion flows |

Not covered: none.
