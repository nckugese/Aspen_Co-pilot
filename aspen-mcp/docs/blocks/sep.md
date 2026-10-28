# Sep

Splits its feed into any number of outlets by component specs (no equipment model). Paths are under `\Data\Blocks\{name}\`; `{stream}` below is an outlet stream. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `P(OUT)` takes every outlet stream, `HS(OUT)` heat stream carrying the duty.

Each outlet gets a row (outlet, substream, component) in `FRACS` and `FLOWS` once it is connected.

Exactly one outlet per substream stays blank and takes what is left; to run, every other outlet needs at least one spec. A spec on the last blank outlet is refused.

A component left blank on a specified outlet sends none of it there.

One of `FRACS` or `FLOWS` per component and outlet: the second is refused until the first is cleared (write `""`).

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\FRACS\{stream}\MIXED\{comp}` | fraction | Share of that component's feed sent to the outlet |
| `Input\FLOWS\{stream}\MIXED\{comp}` | MOLE-FLOW | Amount of that component the outlet receives |
| `Input\FLOWBASIS\{stream}\MIXED\{comp}` | `MOLE`, `MASS`, `STDVOL` | Basis of that `FLOWS` entry |

A mass or standard-volume `FLOWS`: set `FLOWBASIS`, then `set_value` on `FLOWS` with the same `basis` and a unit of it (`kg/hr`, `cum/hr`). `FLOWBASIS` alone leaves a value already written in kmol/hr molar.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Heat duty of the block |
| `Output\STREAM_TEMP\{stream}` | TEMPERATURE | Outlet temperature |
| `Output\STREAM_PRES\{stream}` | PRESSURE | Outlet pressure |
| `Output\STREAM_VFRAC\{stream}` | fraction | Outlet vapor fraction |
| `Output\COMPFRAC\MIXED\{comp}\{stream}` | fraction | Share of the component's feed that went to the outlet |

More: [feed flash](sep-feed-flash.md), [outlet flash](sep-outlet-flash.md).

Not covered: EO Options (equation-oriented options, not checked).
