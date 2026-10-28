# Sep2

Splits its feed into two outlets by component specs (no equipment model). Paths are under `\Data\Blocks\{name}\`; `{stream}` below is an outlet stream. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `O(OUT)` and `B(OUT)` one outlet each, `HS(OUT)` heat stream carrying the duty.

Each outlet gets a row in every spec table below once it is connected.

Specs go on either outlet; the other one takes the rest. To run it needs one spec per component, or a stream spec (`FRAC` or `FLOW`) plus one fewer component spec.

One spec per component over both outlets, and one stream spec: a second one is refused. Clear the first (write `""`) before setting another.

Mole plus mass fraction specs on an outlet must be fewer than the components.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\FRAC\MIXED\{stream}` | fraction | Stream split: share of the whole feed sent to the outlet |
| `Input\FLOW\MIXED\{stream}` | MOLE-FLOW | Total flow of the outlet |
| `Input\FRACS\MIXED\{stream}\{comp}` | fraction | Component split: share of that component's feed |
| `Input\FLOWS\MIXED\{stream}\{comp}` | MOLE-FLOW | Component flow in the outlet |
| `Input\MFFRAC\MIXED\{stream}\{comp}` | fraction | Outlet composition spec, mole basis |
| `Input\MAFRAC\MIXED\{stream}\{comp}` | fraction | Outlet composition spec, mass basis |
| `Input\FLOW_BASIS\MIXED\{stream}` | `MOLE`, `MASS`, `STDVOL` | Basis of `FLOW` |

`FLOWS` on a mass basis: `set_value` with `basis='MASS'` and a mass unit.

`FLOW` on a mass or standard-volume basis: one `set_value` with the unit and `basis` (`kg/hr` with `MASS`, `cum/hr` with `STDVOL`); it writes `FLOW_BASIS` too.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Heat duty of the block |
| `Output\STREAM_TEMP\{stream}` | TEMPERATURE | Outlet temperature |
| `Output\STREAM_PRES\{stream}` | PRESSURE | Outlet pressure |
| `Output\STREAM_VFRAC\{stream}` | fraction | Outlet vapor fraction |
| `Output\COMPFRAC\MIXED\{comp}\{stream}` | fraction | Share of the component's feed that went to the outlet |

More: [feed flash](sep2-feed-flash.md), [outlet flash](sep2-outlet-flash.md).

Not covered: none.
