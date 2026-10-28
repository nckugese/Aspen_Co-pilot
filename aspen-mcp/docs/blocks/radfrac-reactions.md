# RadFrac reactions

Paths are under `\Data\Blocks\{name}\`. Reactions on a range of stages (reactive distillation).

The set must be of type `REAC-DIST` ([reactions-reac-dist.md](../reactions/reactions-reac-dist.md)); a `POWERLAW` set is refused on `REACID`.

`add_reaction` writes the reaction as `KINETIC`, and its tables have no substream level: `COEF\{rxn}\{comp}`, `COEF1\{rxn}\{comp}`, `EXPONENT\{rxn}\{comp}`.

Each reaction type of the set (`REACTYPE\{rxn}` `KINETIC`, `EQUIL`, `CONV`) solves on the column.

Raise `MAXOL` (for example to 200) for a kinetic set and use `CONV_METH` `NONIDEAL` for an equilibrium set; with the defaults such a column can end unsolved ([radfrac-convergence.md](radfrac-convergence.md)).

A Chemistry object has no rate law (no `PRE_EXP` or `ACT_ENERGY`): it holds equilibria only. Kinetic stage reactions go in a `REAC-DIST` set on `REACID`.

1. `insert_row` on `Input\REACID`: row `#0` appears in `REACID`, `REAC_STAGE1` and `REAC_STAGE2` together.
2. Set the row's stage range and reaction set.
3. Kinetic reactions need a holdup: once step 2 is done, `insert_row` on `Input\LHLDP`: row `#0` appears in `HOLD_STAGE1`, `HOLD_STAGE2` and `LHLDP`; set its range and holdup. Without it the block stays incomplete.

| Path | Type | Purpose |
|---|---|---|
| `Input\REAC_STAGE1\{row}` | int | First reacting stage |
| `Input\REAC_STAGE2\{row}` | int | Last reacting stage |
| `Input\REACID\{row}` | ID | `REAC-DIST` set on those stages |
| `Input\HOLD_STAGE1\{row}` | int | First stage of a holdup range |
| `Input\HOLD_STAGE2\{row}` | int | Last stage of a holdup range |
| `Input\LHLDP\{row}` | MOLES | Liquid holdup per stage |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\RXN_GEN\{stage}\{comp}` | MOLE-FLOW | Net amount of a component made on a stage by the reactions (negative: used up) |
