# Valve — Advanced

See [common-advanced.md](common-advanced.md) for property method override, electrolyte, free-water, EO, utility, and CO2e tracking paths shared by all blocks.

## Block-Specific Advanced Inputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\MAX_FLO_COEF` | float | Cv at 100% opening |
| `\Data\Blocks\{name}\Input\PDRP_FAC` | float | Pressure drop ratio factor (xT) |
| `\Data\Blocks\{name}\Input\PREC_FAC` | float | Pressure recovery factor (FL) |
| `\Data\Blocks\{name}\Input\VALVE_DIA` | float | Valve inlet diameter |

## Advanced Outputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\PDROP_FAC2` | float | Calculated pressure drop ratio factor |
| `\Data\Blocks\{name}\Output\PRREC_FAC2` | float | Calculated pressure recovery factor |
| `\Data\Blocks\{name}\Output\PIPE_FIT_FAC2` | float | Piping geometry factor |

> Note: The Valve block does not have utility assignment or utility cost outputs.
