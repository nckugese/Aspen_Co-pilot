# Sep2 (Two-Outlet Component Separator)

Simplified version of Sep with exactly two outlet streams. Separates feed based on component split fractions.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| P1 | OUT | First product |
| P2 | OUT | Second product |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\PRES1` | float | Inlet flash pressure |
| `\Data\Blocks\{name}\Input\TEMP\{stream}` | float | Outlet flash temperature per stream |
| `\Data\Blocks\{name}\Input\PRES\{stream}` | float | Outlet flash pressure per stream |
| `\Data\Blocks\{name}\Input\DELT\{stream}` | float | Outlet flash temperature change per stream |
| `\Data\Blocks\{name}\Input\VFRAC\{stream}` | float | Outlet flash vapor fraction per stream |

> Component split fractions are specified on the Sep2 form.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\QCALC` | float | Heat duty |

## Typical Setup

1. Place: `place_block(session, 'SEP1', 'Sep2')`
2. Specify component split fractions for the first outlet (balance goes to second).
3. Optionally set outlet flash conditions.

## Gotchas

- Same as Sep but limited to exactly 2 outlets — simpler to configure.
- Not a physical model — use for conceptual design.
