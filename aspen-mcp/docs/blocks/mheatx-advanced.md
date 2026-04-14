# MHeatX — Advanced

See [common-advanced.md](common-advanced.md) for property method override, electrolyte, free-water, EO, utility, and CO2e tracking paths shared by all blocks.

## Advanced Outputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\HSTA` | float | Hot end temperature approach |
| `\Data\Blocks\{name}\Output\CSTA` | float | Cold end temperature approach |
| `\Data\Blocks\{name}\Output\HSNTU` | float | Hot NTU |
| `\Data\Blocks\{name}\Output\CSNTU` | float | Cold NTU |
| `\Data\Blocks\{name}\Output\QLEAK_OUT` | float | Heat leak |

> Note: MHeatX does not have utility assignment or utility cost outputs. It also does not use the standard OPSETNAME path — property methods are inherited from the global setting.
