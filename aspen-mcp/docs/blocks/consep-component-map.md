# ConSep component map

Paths are under `\Data\Blocks\{name}\`. ConSep works on three selected components; every other component is counted as a mix of them.

A component left unmapped is shared equally among the three, with a warning (BLKSTAT 2).

1. `insert_row` on `Input\COMP1MAP` with the component as label; the row appears in `COMP2MAP` and `COMP3MAP` too.
2. Write its share of each selected component to `COMP1MAP\<comp>`, `COMP2MAP\<comp>`, `COMP3MAP\<comp>` (summing to 1).

| Path | Type | Purpose |
|---|---|---|
| `Input\COMP1MAP\{comp}` | fraction | Share counted as `SELCOMP1` |
| `Input\COMP2MAP\{comp}` | fraction | Share counted as `SELCOMP2` |
| `Input\COMP3MAP\{comp}` | fraction | Share counted as `SELCOMP3` |

A mapped component then follows the recovery of the component it is counted as.
