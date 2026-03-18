# MultiFrac (Multi-Column Distillation)

Rigorous multi-column distillation system with interconnecting streams. Models coupled columns like absorber-stripper, crude unit main column with side strippers, etc.

## Ports

MultiFrac has dynamic port assignments depending on column configuration. Each column has its own feed, distillate, and bottoms ports.

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\NCOL` | int | Number of columns (read-only after creation) |
| `\Data\Blocks\{name}\Input\INIT_OPTION` | string | Initialization method |
| `\Data\Blocks\{name}\Input\CONDENSE2\{col}` | string | Condenser type for column (e.g. `TOTAL`, `PARTIAL-V`, `NONE`) |
| `\Data\Blocks\{name}\Input\REBOILER\{col}` | string | Reboiler type for column |
| `\Data\Blocks\{name}\Input\BASIS_RR\{col}` | float | Reflux ratio for column |
| `\Data\Blocks\{name}\Input\BASIS_D\{col}` | float | Distillate rate for column |
| `\Data\Blocks\{name}\Input\BASIS_B\{col}` | float | Bottoms rate for column |
| `\Data\Blocks\{name}\Input\PRES1\{col}` | float | Stage 1 / condenser pressure for column |
| `\Data\Blocks\{name}\Input\DP_STAGE\{col}` | float | Stage pressure drop for column |
| `\Data\Blocks\{name}\Input\DP_COL\{col}` | float | Column pressure drop for column |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\TOP_TEMP\{col}` | float | Condenser / top stage temperature for column |
| `\Data\Blocks\{name}\Output\COND_Q_NSC\{col}` | float | Condenser heat duty for column |
| `\Data\Blocks\{name}\Output\MOLE_D\{col}` | float | Distillate rate for column |
| `\Data\Blocks\{name}\Output\MOLE_L1\{col}` | float | Reflux rate for column |
| `\Data\Blocks\{name}\Output\MOLE_RR\{col}` | float | Reflux ratio for column |

## Typical Setup

1. Place: `place_block(session, 'MF1', 'MultiFrac')`
2. Configure number of columns and interconnecting streams via the GUI or node structure.
3. Set specs per column (reflux ratio, distillate rate, pressures).

## Gotchas

- Complex setup — each column needs its own specs and pressure profile.
- Interconnecting streams must be properly defined between columns.
- Use RadFrac for single-column simulations; MultiFrac is for coupled column systems.
