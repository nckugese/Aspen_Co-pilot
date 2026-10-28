# Valve

Control valve: an adiabatic pressure letdown of one feed, optionally sized or rated against valve data. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `P(OUT)` product (free water and every phase leave here).

To run it needs the outlet spec: a fresh block has `MODE` `ADIAB-FLASH` and `OPT_DESIGN` `P-OUT` and is incomplete until `P_OUT` is written.

`SET-PRESSURE` and `CALC-PRESSURE` also need valve data ([valve-parameters.md](valve-parameters.md)); without it the block stays incomplete.

Writing `P_DROP` or `FLO_COEF` does not change `OPT_DESIGN` / `OPT_RATING`; set the option yourself.

## Input | Operation

| Path | Type | Purpose |
|---|---|---|
| `Input\MODE` | `ADIAB-FLASH`, `SET-PRESSURE`, `CALC-PRESSURE` | `ADIAB-FLASH`: let down to the given pressure, no valve sizing; `SET-PRESSURE`: outlet given, opening and Cv found (design); `CALC-PRESSURE`: opening or Cv given, outlet found (rating) |
| `Input\OPT_DESIGN` | `P-OUT`, `P-DROP` | Outlet spec for `ADIAB-FLASH` and `SET-PRESSURE` |
| `Input\P_OUT` | PRESSURE | Outlet pressure |
| `Input\P_DROP` | PDROP | Drop from feed to outlet |
| `Input\OPT_RATING` | `VAL-POSN`, `FLOW-COEF` | What `CALC-PRESSURE` is given: opening or Cv |
| `Input\VAL_POSN` | percent | Valve opening, 0-100 % |
| `Input\FLO_COEF` | number | Flow coefficient Cv at the operating opening |

`P_DROP` 4 atm on a 5 atm feed gives a 1 atm outlet.

The letdown is adiabatic: a 120 C liquid at 5 atm taken to 1 atm leaves near 93 C, partly vapor.

Design finds the opening (13 %) and Cv (6.28) for 2 atm out; `P-DROP` 3 atm gives the same.

Rating with that Cv gives back the 2 atm outlet.

Rating at 15 % gives an outlet between 1 atm and the feed pressure.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\P_OUT_OUT` | PRESSURE | Outlet pressure |
| `Output\VALVE_DP` | PDROP | Pressure drop |
| `Output\VALVE_POSN` | percent | Opening (given or found) |
| `Output\FLOW_COEF` | number | Cv at that opening |
| `Output\CHOKE_POUT` | PRESSURE | Outlet pressure at which the flow chokes |
| `Output\TCALC` | TEMPERATURE | Outlet temperature |
| `Output\VCALC` | fraction | Outlet vapor fraction |

More: [valve parameters](valve-parameters.md), [calculation options](valve-calculation-options.md), [pipe fittings](valve-pipe-fittings.md), [valid phases and flash](valve-phases.md).

Not covered: Dynamics (Aspen Dynamics only).
