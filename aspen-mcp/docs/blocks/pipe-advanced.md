# Pipe — Advanced

See [common-advanced.md](common-advanced.md) for property method override, electrolyte, free-water, EO, utility, and CO2e tracking paths shared by all blocks.

## Block-Specific Advanced Inputs — Fittings

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\E_DIAM` | float | Enlargement diameter |
| `\Data\Blocks\{name}\Input\E_ANGLE` | float | Enlargement angle |
| `\Data\Blocks\{name}\Input\C_DIAM` | float | Contraction diameter |
| `\Data\Blocks\{name}\Input\C_ANGLE` | float | Contraction angle |
| `\Data\Blocks\{name}\Input\ORIFICE_DIAM` | float | Orifice diameter |
| `\Data\Blocks\{name}\Input\ORIFICE_THIC` | float | Orifice thickness |
| `\Data\Blocks\{name}\Input\C_EROSION` | float | Erosional velocity coefficient |

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
| `\Data\Blocks\{name}\Output\S_LOADING` | float | Solids loading |
| `\Data\Blocks\{name}\Output\S_DUTY` | float | Solids conveying heat duty |
| `\Data\Blocks\{name}\Output\S_DPTOT` | float | Total solids conveying pressure drop |
| `\Data\Blocks\{name}\Output\S_APPSV` | float | Approach to saltation velocity |

> Note: Pipe does not have utility assignment or utility cost outputs.
