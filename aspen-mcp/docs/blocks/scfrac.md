# SCFrac (Short-Cut Fractionation)

Short-cut fractionation model for quick petroleum column estimates. Simpler than PetroFrac.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| D | OUT | Distillate |
| SP | OUT | Side products |
| B | OUT | Bottoms |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\PRES` | float | Specified condenser pressure |
| `\Data\Blocks\{name}\Input\TEMP` | float | Specified condenser temperature |
| `\Data\Blocks\{name}\Input\RDV` | float | Distillate vapor fraction |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\B_PRES` | float | Calculated condenser pressure |
| `\Data\Blocks\{name}\Output\B_TEMP` | float | Calculated condenser temperature |
| `\Data\Blocks\{name}\Output\LIQ_FLOW` | float | Condenser liquid flow |
| `\Data\Blocks\{name}\Output\VAP_FLOW` | float | Condenser vapor flow |
| `\Data\Blocks\{name}\Output\FWDECANT` | float | Condenser free water flow |

## Typical Setup

1. Place: `place_block(session, 'SC1', 'SCFrac')`
2. Condenser pressure: `set_value(session, aspen_path='\Data\Blocks\SC1\Input\PRES', value='1', unit='atm')`
3. Define side product cut points.

## Gotchas

- Shortcut model — use PetroFrac for rigorous petroleum fractionation.
- Does not have utility assignment or utility cost outputs.
