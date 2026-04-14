# MultiFrac — Advanced

See [common-advanced.md](common-advanced.md) for property method override, electrolyte, free-water, EO, utility, and CO2e tracking paths shared by all blocks.

## Block-Specific Advanced Inputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\BLKOPFREWAT` | string | Free-water option |
| `\Data\Blocks\{name}\Input\COND_UTIL\{col}` | string | Condenser utility ID per column |
| `\Data\Blocks\{name}\Input\REB_UTIL\{col}` | string | Reboiler utility ID per column |

## Advanced Outputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\SCDUTY\{col}` | float | Subcooled duty per column |
| `\Data\Blocks\{name}\Output\MOLE_DW\{col}` | float | Free water distillate rate per column |
| `\Data\Blocks\{name}\Output\RW\{col}` | float | Free water reflux ratio per column |
| `\Data\Blocks\{name}\Output\COND_USAGE\{col}` | float | Condenser utility usage per column |
| `\Data\Blocks\{name}\Output\COND_COST\{col}` | float | Condenser utility cost per column |
| `\Data\Blocks\{name}\Output\REB_USAGE\{col}` | float | Reboiler utility usage per column |
| `\Data\Blocks\{name}\Output\REB_COST\{col}` | float | Reboiler utility cost per column |
