# MHeatX (Multi-Stream Heat Exchanger)

Multi-stream heat exchanger that can exchange heat between any number of hot and cold streams simultaneously.

## Ports

MHeatX has dynamic port assignments — one pair (IN/OUT) per stream. Streams are numbered (1, 2, 3, ...).

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\VALUE\{stream}` | float | Specification value (hot/cold) per stream |
| `\Data\Blocks\{name}\Input\PRES\{stream}` | float | Outlet pressure per stream |
| `\Data\Blocks\{name}\Input\Q_EST\{stream}` | float | Duty estimate per stream |
| `\Data\Blocks\{name}\Input\QLEAK_FRAC` | float | Fraction of total duty lost to heat leak |
| `\Data\Blocks\{name}\Input\QLEAK` | float | Heat leak amount |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\IN_TEMP\{stream}` | float | Inlet temperature per stream |
| `\Data\Blocks\{name}\Output\IN_PRES\{stream}` | float | Inlet pressure per stream |
| `\Data\Blocks\{name}\Output\IN_VF\{stream}` | float | Inlet vapor fraction per stream |
| `\Data\Blocks\{name}\Output\B_TEMP\{stream}` | float | Outlet temperature per stream |
| `\Data\Blocks\{name}\Output\B_PRES\{stream}` | float | Outlet pressure per stream |
| `\Data\Blocks\{name}\Output\B_VFRAC\{stream}` | float | Outlet vapor fraction per stream |
| `\Data\Blocks\{name}\Output\QCALC\{stream}` | float | Duty per stream |
| `\Data\Blocks\{name}\Output\QCALC2` | float | Total duty |
| `\Data\Blocks\{name}\Output\UA` | float | UA value |
| `\Data\Blocks\{name}\Output\LMTD` | float | Log-mean temperature difference |
| `\Data\Blocks\{name}\Output\MITA` | float | Minimum temperature approach |

## Typical Setup

1. Place: `place_block(session, 'MHX1', 'MHeatX')`
2. Connect multiple hot and cold streams.
3. Specify outlet temperatures or duties per stream.

## Gotchas

- **Cannot be placed via COM** — must be created in the GUI first, then configured via COM.
- Useful for heat integration studies and pinch analysis.
- Minimum temperature approach (MITA) output helps evaluate heat recovery feasibility.
