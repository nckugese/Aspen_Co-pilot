# HXFlux — Advanced

See [common-advanced.md](common-advanced.md) for property method override, electrolyte, free-water, EO, utility, and CO2e tracking paths shared by all blocks.

## Advanced Inputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\MAX_AREA` | float | Maximum heat transfer area |
| `\Data\Blocks\{name}\Input\SPAN` | float | Level span |
| `\Data\Blocks\{name}\Input\LEVEL_TOP` | float | Level at complete immersion |
| `\Data\Blocks\{name}\Input\LEVEL_BOT` | float | Level at zero immersion |
| `\Data\Blocks\{name}\Input\AER_PARM` | float | Aeration parameter |

## Advanced Outputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\U-LMTD-CORR` | float | LMTD correction factor |
| `\Data\Blocks\{name}\Output\RAD_TAVG` | float | Average process temperature |
| `\Data\Blocks\{name}\Output\RAD_TAVGWT` | float | Weighted average temperature |
| `\Data\Blocks\{name}\Output\RAD_TFF` | float | Front face temperature |
| `\Data\Blocks\{name}\Output\RAD_HCONV` | float | Calculated heat transfer coefficient |

> Note: HXFlux does not use the standard OPSETNAME path and does not have utility or CO2e tracking outputs.
