# Optimization

Moves the varied inputs, within their limits, to maximize or minimize an objective while keeping the constraints; Aspen's built-in optimizer.

Root: `\Data\Model Analysis Tools\Optimization\{id}`

## Setup

1. Create it with `add_element` on `\Data\Model Analysis Tools\Optimization` and an ID; each constraint is its own object, created the same way on `\Data\Model Analysis Tools\Constraint`.
2. Define the variables the objective and each constraint read, on each object, as in [flowsheeting.md](../flowsheeting/flowsheeting.md) (Define a variable).
3. Write the objective in `EXPR1`, a define variable or an expression of them, and its direction in `MAX_MIN`.
4. Vary rows as for a sensitivity ([sensitivity.md](sensitivity.md)): `insert_row` on `Input\VARY_VARTYPE`, then type, block or stream, variable, `LOWER` and `UPPER`.
5. Constraint: `EXPR1` `OPER` `EXPR2` within `TOL`. Attach it with `insert_row` on `Input\CONID` of the optimization and its ID in `CONID\#n`.

Keep the objective near 1 in size: `(VF-40)**2` stopped the default SQP block with errors, `(VF-40)**2/100` converged at 40.1 kmol/hr.

The run ends at the constraint when it limits the objective: here the vapor benzene fraction ends at 0.62.

Aspen converges it with an SQP block of its own (`Output\CVBLKID`, e.g. `$OLVER01`); its settings: [convergence-optimization.md](../convergence/convergence-optimization.md).

## Objective

| Path | Type | Purpose |
|---|---|---|
| `Input\EXPR1` | string | Objective: a define variable or an expression |
| `Input\MAX_MIN` | `MAXIMIZE`, `MINIMIZE` | Direction |
| `Input\CONID\{row}` | ID | A constraint applied (`insert_row` first) |

## Vary

| Path | Type | Purpose |
|---|---|---|
| `Input\VARY_VARTYPE\{row}` | `BLOCK-VAR`, `STREAM-VAR`, `MOLE-FLOW`, `MASS-FLOW` | Kind of input varied |
| `Input\LOWER\{row}` | string | Lower limit |
| `Input\UPPER\{row}` | string | Upper limit |
| `Input\STEP_SIZE\{row}` | real | Step used for the derivatives |
| `Input\MAX_STEP_SIZ\{row}` | real | Largest move per iteration |
| `Input\DISABLE\{row}` | `NO`, `YES` | Hold this row at its current value |

## Constraint

| Path | Type | Purpose |
|---|---|---|
| `\Data\Model Analysis Tools\Constraint\{con}\Input\EXPR1` | string | Left side: a define variable or an expression |
| `\Data\Model Analysis Tools\Constraint\{con}\Input\OPER` | `GE`, `LE`, `EQ` | Relation: >=, <=, = |
| `\Data\Model Analysis Tools\Constraint\{con}\Input\EXPR2` | string | Right side |
| `\Data\Model Analysis Tools\Constraint\{con}\Input\TOL` | string | Tolerance |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BLKSTAT` | int | 0 when it converged |
| `Output\FINAL_VAL\{n}` | real | Final value of define variable n |
| `Output\INIT_VAL\{n}` | real | Its value at the start |
| `Output\OPTMETH` | string | Method used (`SQP`) |
| `\Data\Model Analysis Tools\Constraint\{con}\Output\FINAL_VAL\{n}` | real | Constraint variable n at the end |
| `\Data\Blocks\{flash}\Output\B_TEMP` | TEMPERATURE | Flash temperature at the optimum |
