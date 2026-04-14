# PetroFrac — Advanced

See [common-advanced.md](common-advanced.md) for property method override, electrolyte, free-water, EO, utility, and CO2e tracking paths shared by all blocks.

## Block-Specific Advanced Inputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\COND_UTIL` | string | Condenser utility ID |
| `\Data\Blocks\{name}\Input\REB_UTIL` | string | Reboiler utility ID |

## Advanced Outputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\SCDUTY` | float | Condenser subcooled duty |
| `\Data\Blocks\{name}\Output\MOLE_DW` | float | Free water distillate rate |
| `\Data\Blocks\{name}\Output\RW` | float | Free water reflux ratio |
| `\Data\Blocks\{name}\Output\COND_USAGE` | float | Condenser utility usage |
| `\Data\Blocks\{name}\Output\COND_COST` | float | Condenser utility cost |
| `\Data\Blocks\{name}\Output\REB_USAGE` | float | Reboiler utility usage |
| `\Data\Blocks\{name}\Output\REB_COST` | float | Reboiler utility cost |
