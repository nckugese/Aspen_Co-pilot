# Sep (Component Separator)

Separates feed into multiple outlet streams based on specified component splits. Not a physical model — useful for conceptual design.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| P | OUT | Product (multiple outlets) |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\PRES1` | float | Inlet flash pressure |
| `\Data\Blocks\{name}\Input\TEMP\{stream}` | float | Outlet flash temperature per stream |
| `\Data\Blocks\{name}\Input\PRES\{stream}` | float | Outlet flash pressure per stream |
| `\Data\Blocks\{name}\Input\DELT\{stream}` | float | Outlet flash temperature change per stream |
| `\Data\Blocks\{name}\Input\VFRAC\{stream}` | float | Outlet flash vapor fraction per stream |

> Component split fractions are specified on the Sep form (split fraction of each component going to each outlet).

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\QCALC` | float | Heat duty |

## Typical Setup

1. Place: `place_block(session, 'SEP1', 'Sep')`
2. Connect multiple outlet streams.
3. Specify component split fractions to each outlet.
4. Optionally set outlet flash conditions (temperature, pressure).

## Gotchas

- Not a physical model — it splits by user-specified fractions, not by thermodynamic equilibrium.
- Use for conceptual flowsheets or when separation details are not important.
- For physical separation, use Flash2, Decanter, or RadFrac.
