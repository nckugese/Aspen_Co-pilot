# RadFrac (Rigorous Distillation)

Rigorous multi-stage vapor-liquid fractionation column with condenser and reboiler.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed (multiple feeds allowed) |
| HS | IN | Heat stream |
| VD | OUT | Vapor distillate |
| LD | OUT | Liquid distillate |
| B | OUT | Bottoms |
| SP | OUT | Side product |
| WD | OUT | Water decant |
| CHS | OUT | Condenser heat stream |
| RHS | OUT | Reboiler heat stream |
| PS | OUT | Pseudo stream |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\NSTAGE` | int | Number of stages |
| `\Data\Blocks\{name}\Input\CONDENSER` | string | `TOTAL`, `PARTIAL-V`, `PARTIAL-V-L`, `NONE` |
| `\Data\Blocks\{name}\Input\REBOILER` | string | `KETTLE`, `THERMOSIPHON`, `NONE` |
| `\Data\Blocks\{name}\Input\NO_PHASE` | int | Number of phases |
| `\Data\Blocks\{name}\Input\BASIS_RR` | float | Specified reflux ratio |
| `\Data\Blocks\{name}\Input\BASIS_BR` | float | Specified boilup ratio |
| `\Data\Blocks\{name}\Input\BASIS_D` | float | Specified distillate rate |
| `\Data\Blocks\{name}\Input\BASIS_B` | float | Specified bottoms rate |
| `\Data\Blocks\{name}\Input\BASIS_VN` | float | Specified boilup rate |
| `\Data\Blocks\{name}\Input\D:F` | float | Distillate-to-feed ratio |
| `\Data\Blocks\{name}\Input\B:F` | float | Bottoms-to-feed ratio |
| `\Data\Blocks\{name}\Input\QN` | float | Reboiler duty |
| `\Data\Blocks\{name}\Input\QC` | float | Condenser duty |
| `\Data\Blocks\{name}\Input\FEED_STAGE\{stream}` | int | Feed stage for a stream |
| `\Data\Blocks\{name}\Input\FEED_CONVEN\{stream}` | string | Feed convention: `ABOVE-STAGE`, `ON-STAGE` |
| `\Data\Blocks\{name}\Input\PRES1` | float | Top stage pressure |
| `\Data\Blocks\{name}\Input\STAGE_PRES\1` | float | Top stage pressure (alternative path) |
| `\Data\Blocks\{name}\Input\DP_STAGE` | float | Pressure drop per stage |

> RadFrac requires exactly **2 operating specs**. Common combinations:
> - Reflux ratio (`BASIS_RR`) + Boilup ratio (`BASIS_BR`)
> - Reflux ratio (`BASIS_RR`) + Distillate rate (`BASIS_D`)
> - Reflux ratio (`BASIS_RR`) + Bottoms rate (`BASIS_B`)

> **You must clear one spec before setting another.** For example, to switch from boilup ratio to reboiler duty, first clear `BASIS_BR`, then set `QN`.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\MOLE_RR` | float | Calculated molar reflux ratio |
| `\Data\Blocks\{name}\Output\MOLE_D` | float | Calculated distillate rate |
| `\Data\Blocks\{name}\Output\MOLE_B` | float | Calculated bottoms rate |
| `\Data\Blocks\{name}\Output\MOLE_VN` | float | Calculated boilup rate |
| `\Data\Blocks\{name}\Output\BU_RATIO` | float | Calculated molar boilup ratio |
| `\Data\Blocks\{name}\Output\MASS_BR` | float | Calculated mass boilup ratio |
| `\Data\Blocks\{name}\Output\TOP_TEMP` | float | Condenser / top stage temperature |
| `\Data\Blocks\{name}\Output\PRES1` | float | Condenser / top stage pressure |
| `\Data\Blocks\{name}\Output\COND_DUTY` | float | Condenser heat duty |
| `\Data\Blocks\{name}\Output\SCDUTY` | float | Condenser subcooled duty |
| `\Data\Blocks\{name}\Output\MOLE_L1` | float | Condenser reflux rate |
| `\Data\Blocks\{name}\Output\RW` | float | Free water reflux ratio |
| `\Data\Blocks\{name}\Output\REB_POUT` | float | Reboiler pressure |
| `\Data\Blocks\{name}\Output\REB_TOUT` | float | Reboiler temperature |
| `\Data\Blocks\{name}\Output\REB_DUTY` | float | Reboiler heat duty |

## Side Duties

Use `add_side_duty` tool or manual path:
```
\Data\Blocks\{name}\Input\HEATER_DUTY\{stage}
```
Side duties are rejected on condenser (stage 1) and reboiler (last stage).

## Typical Setup

1. Place: `place_block(session, 'COL1', 'RadFrac')`
2. Stages: `set_value(session, aspen_path='\Data\Blocks\COL1\Input\NSTAGE', value='30')`
3. Condenser: `set_value(session, aspen_path='\Data\Blocks\COL1\Input\CONDENSER', value='TOTAL')`
4. Spec 1: `set_value(session, aspen_path='\Data\Blocks\COL1\Input\BASIS_RR', value='2')`
5. Spec 2: `set_value(session, aspen_path='\Data\Blocks\COL1\Input\BASIS_BR', value='3')`
6. Feed stage: `set_value(session, aspen_path='\Data\Blocks\COL1\Input\FEED_STAGE\FEED', value='15')`
7. Pressure: `set_value(session, aspen_path='\Data\Blocks\COL1\Input\PRES1', value='1', unit='atm')`

## Gotchas

- Max 2 operating specs — setting a 3rd will cause errors.
- `PARTIAL-V` condenser: top product exits from VD(OUT) port (vapor distillate).
- `TOTAL` condenser: top product exits from LD(OUT) port (liquid distillate).
- Feed stage numbered from top (condenser = stage 1).
- For column with `REBOILER=NONE` and N stages, bottom feed goes to stage N+1.
- "COLUMN DRIES UP" error = wrong feed conditions or impossible specs.
