# REquil reaction extents and approach checks

Paths are under `\Data\Blocks\{name}\`. Each reaction row (see [requil.md](requil.md)) is held by a temperature approach or by a fixed extent.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_EXT_DELT\{n}` | `DELT`, `EXTENT` | Reaction n held by a temperature approach, or by a fixed extent |
| `Input\DELT\{n}` | DELTA-T | Temperature approach: the constant is taken at the outlet temperature plus this |

`DELT` -20 C at 70 C takes the constant at 50 C (`TKEQ` 50 C) while the outlet stays at 70 C; this exothermic reaction then forms more ester than at full equilibrium.

| Path | Type | Purpose |
|---|---|---|
| `Input\EXT_SPEC\{n}` | MOLE-FLOW | Fixed extent: kmol/hr of turnover, product formed over its coefficient |

`EXTENT` 20 kmol/hr forms exactly 20 kmol/hr of ester, and no constant is reported for that reaction.

| Path | Type | Purpose |
|---|---|---|
| `Input\EXT_EST\{n}` | MOLE-FLOW | Starting guess of the extent of an approach-held reaction |

A guess changes only the start: with 35 kmol/hr the outlet matches the run without it.

| Path | Type | Purpose |
|---|---|---|
| `Input\TAPP_CHK\{n}` | `NONE`, `INFORMATION`, `WARNING`, `ERROR` | How a doubtful temperature approach is reported |

Here `DELT` -20 C is flagged (block warning under `WARNING`, block error under `ERROR`) while +20 C passes.
