# PetroFrac (Petroleum Fractionation)

Rigorous petroleum fractionation column with side strippers, pumparounds, and furnace. Designed for crude distillation and similar petroleum refining operations.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed (multiple) |
| D | OUT | Distillate |
| B | OUT | Bottoms |
| SP | OUT | Side products |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\NSTAGE` | int | Number of stages |
| `\Data\Blocks\{name}\Input\BASIS_D` | float | Distillate rate |
| `\Data\Blocks\{name}\Input\BASIS_B` | float | Bottoms rate |
| `\Data\Blocks\{name}\Input\PRES1` | float | Stage 1 / condenser pressure |
| `\Data\Blocks\{name}\Input\PRES2` | float | Stage 2 pressure |
| `\Data\Blocks\{name}\Input\PRESN` | float | Bottom stage pressure |
| `\Data\Blocks\{name}\Input\FRN_DUTY` | float | Furnace duty |
| `\Data\Blocks\{name}\Input\BASIS_OVFL` | float | Fractional overflash |
| `\Data\Blocks\{name}\Input\FRN_TEMP` | float | Furnace temperature |
| `\Data\Blocks\{name}\Input\FRN_PRES` | float | Furnace pressure |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\TOP_TEMP` | float | Condenser / top stage temperature |
| `\Data\Blocks\{name}\Output\TOP_PRES` | float | Condenser / top stage pressure |
| `\Data\Blocks\{name}\Output\COND_DUTY` | float | Condenser heat duty |
| `\Data\Blocks\{name}\Output\MOLE_D` | float | Distillate rate |
| `\Data\Blocks\{name}\Output\MOLE_L1` | float | Reflux rate |
| `\Data\Blocks\{name}\Output\MOLE_RR` | float | Reflux ratio |

## Typical Setup

1. Place: `place_block(session, 'CDU1', 'PetroFrac')`
2. Stages: `set_value(session, aspen_path='\Data\Blocks\CDU1\Input\NSTAGE', value='30')`
3. Pressures, furnace conditions, and product specs.

## Gotchas

- Designed specifically for petroleum refining — has built-in furnace and pumparound support.
- More complex than RadFrac; use RadFrac for non-petroleum distillation.
- Side strippers and pumparounds must be configured separately.
