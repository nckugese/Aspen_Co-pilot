# MCompr — Advanced

See [common-advanced.md](common-advanced.md) for property method override, electrolyte, free-water, EO, utility, and CO2e tracking paths shared by all blocks.

## Block-Specific Advanced Inputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\NMAP` | int | Number of performance maps |
| `\Data\Blocks\{name}\Input\NCURVES` | int | Number of performance curves |

> Note: MCompr does not expose individual utility cost outputs in the sgxml summary. Use the common CO2e tracking outputs.
