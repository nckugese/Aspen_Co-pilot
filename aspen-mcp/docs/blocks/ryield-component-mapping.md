# RYield component mapping (lump / de-lump)

Paths are under `\Data\Blocks\{name}\`. `USER_YIELD` = `NO2` replaces the yield table by rules that merge components into one (lump) or split one into several (de-lump); everything else passes through.

1. Write `NO2` to `Input\USER_YIELD`.
2. `insert_row` on `Input\TYPE`, `set_label` index *i* with the lumped or split component, then `set_value` `LUMP` or `DE-LUMP` on `Input\TYPE\{comp}`.
3. `insert_row` on `Input\FRAC\{comp}` and `set_label` each member component, then `set_value` its fraction on `Input\FRAC\{comp}\{member}`.

`LUMP`: the given fraction of each member's feed flow is added to the lumped component.

`DE-LUMP`: the component's feed flow is shared among the members by the fractions.

De-lump fractions must add up to 1, or the input is refused and the block is not solved.

## Setup | Comp. Mapping

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE\{comp}` | `LUMP`, `DE-LUMP` | Rule for that component (one row per rule) |
| `Input\FRAC\{comp}\{member}` | fraction | Share of a member taken into the lump, or given to it by the de-lump |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Heat duty (the mapping's heat of change at the outlet specs) |
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature |
