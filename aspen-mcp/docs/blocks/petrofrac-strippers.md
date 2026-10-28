# PetroFrac side strippers

Paths are under `\Data\Blocks\{name}\`. A side stripper takes liquid from a main-column stage, strips it with steam or a reboiler and sends its vapor back to the column; its bottoms leave on `SB(OUT)`.

1. `add_element` on `Subobjects\Strippers` with an ID, e.g. `S-1`; its fields are keyed by that ID.
2. Set the stage count, the draw and return stages, the bottoms stream, the stripping medium and one flow spec.

## Strippers | Setup

| Path | Type | Purpose |
|---|---|---|
| `Input\ST_NSTAGE\{stripper}` | int | Stripper stages |
| `Input\LDRAW\{stripper}` | int | Draw stage on the main column (the stripper feed) |
| `Input\VRETURN\{stripper}` | int | Main-column stage the stripper vapor returns to |
| `Input\PRODUCT\{stripper}` | stream ID | Stripper bottoms stream (on `SB(OUT)`) |
| `Input\OPT_SMEDIUM\{stripper}` | `STEAM`, `DUTY` | Stripping by a steam feed or by a reboiler |
| `Input\STEAM\{stripper}` | stream ID | Steam feed (on `SF(IN)`), with `STEAM` |
| `Input\ST_Q_REB\{stripper}` | ENTHALPY-FLO | Reboiler duty, with `DUTY` |

Flow spec (one):

| Path | Type | Purpose |
|---|---|---|
| `Input\BASIS_ST_B\{stripper}` | MOLE-FLOW | Stripper bottoms rate |
| `Input\BASIS_STDRW\{stripper}` | MOLE-FLOW | Liquid draw rate from the main column |

One flow spec only: once one is set the other is locked.

## Strippers | Liquid Return

| Path | Type | Purpose |
|---|---|---|
| `Input\LRETURN\{stripper}` | int | Main-column stage that receives liquid back from the stripper |
| `Input\BASIS_LFLOW\{stripper}` | MOLE-FLOW | Rate returned |
| `Input\LR_DELT\{stripper}` | DELTA-T | Temperature change of the returned liquid (or `LR_TEMP`, `LR_DUTY`) |

## Strippers | Pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\ST_PRES1\{stripper}` | PRESSURE | Stripper pressure at its stage 1 |
| `Input\OPT_SDP\{stripper}` | `P-BOTTOM`, `DP-STAGE`, `DP-COL` | Rest of the profile: bottom pressure, drop per stage or drop over the stripper |
| `Input\ST_PRESN\{stripper}` | PRESSURE | Bottom stage pressure |
| `Input\ST_DP_STAGE\{stripper}` | PDROP | Drop per stage |
| `Input\ST_DP_COL\{stripper}` | PDROP | Drop over the stripper |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\ST_MOLE_B\{stripper}` | MOLE-FLOW | Stripper bottoms rate |
| `Output\ST_MOLE_D\{stripper}` | MOLE-FLOW | Vapor returned to the main column |
| `Output\ST_MOLE_L1\{stripper}` | MOLE-FLOW | Liquid drawn from the main column |
| `Output\B_TEMP3\{stripper}\{stage}` | TEMPERATURE | Stripper stage temperature |
| `Output\REB_DUTY2\{stripper}` | ENTHALPY-FLO | Stripper reboiler duty (`DUTY`) |
