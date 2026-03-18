# Pipeline — Advanced

See [common-advanced.md](common-advanced.md) for property method override, electrolyte, free-water, EO, utility, and CO2e tracking paths shared by all blocks.

## Block-Specific Advanced Inputs — Solids Conveying

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\CONVEY_METH` | string | Conveying method |
| `\Data\Blocks\{name}\Input\DILUTE_METH` | string | Dilute phase conveying method |
| `\Data\Blocks\{name}\Input\VOIDAGE` | float | Voidage |
| `\Data\Blocks\{name}\Input\SPHERICITY` | float | Particle sphericity |
| `\Data\Blocks\{name}\Input\DIA_PART` | float | Particle diameter |

## Advanced Outputs — Solids Conveying

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\SOLIDS_LOAD` | float | Solids loading |
| `\Data\Blocks\{name}\Output\CNVY_TDUTY` | float | Solids conveying heat duty |
| `\Data\Blocks\{name}\Output\CNVY_TPRES` | float | Total solids conveying pressure drop |
| `\Data\Blocks\{name}\Output\CNVY_TAPP` | float | Approach to saltation velocity |

> Note: Pipeline does not have utility assignment or utility cost outputs.
