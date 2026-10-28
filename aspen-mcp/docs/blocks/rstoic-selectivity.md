# RStoic selectivity

Paths are under `\Data\Blocks\{name}\`. Reports how much of a product is made per reactant used, after all reactions ([rstoic.md](rstoic.md)); it does not change the result.

1. `insert_row` on `Input\SEL_CID` and `set_label` it with an ID (`1`, `2`, ...); `REF_CID`, `SEL_SSID` and `REF_SSID` get the same entry.
2. `set_value` the product on `SEL_CID\{id}` and the reactant on `REF_CID\{id}`.

`SEL_SSID` and `REF_SSID` (substreams) can stay empty: `MIXED` is used.

The value is moles of product made per mole of reactant used, times the moles of reactant one mole of product takes in its own reaction: 1 means all the reactant went to that product.

## Setup | Selectivity

| Path | Type | Purpose |
|---|---|---|
| `Input\SEL_CID\{id}` | component ID | Product |
| `Input\REF_CID\{id}` | component ID | Reference reactant |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\SELECT\{id}` | ratio | Selectivity |
| `Output\COMPID\{id}` | component ID | Its product |
