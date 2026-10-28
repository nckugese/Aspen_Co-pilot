# Calculation sequence

The order in which blocks are computed, how convergence blocks nest, and the options Aspen sequences with.

Root: `\Data\Convergence\Sequence\{id}`

## A sequence of your own

1. `add_element` on `\Data\Convergence\Sequence` with an ID.
2. For each entry, in order: `insert_row` on `Input\BLOCK_TYPE`, then write `BLOCK_TYPE\#n` and `BLOCK_ID\#n`.
3. A loop starts at a row with its convergence block and `RETURN\#n` `BEGIN`, and ends at a later row with the same block and `RETURNTO`.

A loop must hold every block that computes its tear stream: with the splitter left out the run did not start.

| Path | Type | Purpose |
|---|---|---|
| `Input\BLOCK_TYPE\{row}` | `BLOCK`, `CONVERGENCE`, `CALCULATOR`, `TRANSFER`, `SENSITIVITY`, `SEQUENCE` | Kind of the entry |
| `Input\BLOCK_ID\{row}` | ID | Its ID; the row's kind must be written first |
| `Input\RETURN\{row}` | `BEGIN`, `RETURNTO` | On a convergence row: start of its loop, or the jump back to it |

## Nesting order

1. `insert_row` on `\Data\Convergence\Conv-Order\Input\CVBLOCK`, then write `CVBLOCK\#n` with a convergence block ID; a block already listed is refused.

| Path | Type | Purpose |
|---|---|---|
| `\Data\Convergence\Conv-Order\Input\CVBLOCK\{row}` | ID | Convergence block; the first is solved innermost |

With the tear block first, the tear loop ran inside the spec loop; with the spec block first, the spec ran inside.

## Sequencing options

| Path | Type | Purpose |
|---|---|---|
| `\Data\Convergence\Conv-Options\Input\TEAR_WEIGHT` | int | Weight on the count of tear variables when Aspen picks tears |
| `\Data\Convergence\Conv-Options\Input\LOOP_WEIGHT` | int | Weight on loops torn more than once when Aspen picks tears |
| `\Data\Convergence\Conv-Options\Input\TEAR_VAR` | `NO`, `YES` | Also tear the variables Calculator blocks write |
| `\Data\Convergence\Conv-Options\Input\CHECKSEQ` | `YES`, `NO` | Check a sequence you give |
