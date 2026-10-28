# Calculator

Runs Fortran lines on defined variables during the run and writes the results into blocks and streams.

Root: `\Data\Flowsheeting Options\Calculator\{id}`

1. `add_element` on `\Data\Flowsheeting Options\Calculator` with an ID.
2. Define each variable it reads or writes ([flowsheeting.md](flowsheeting.md#define-a-variable)).
3. List the names it reads in `Input\READ_VAR` and those it writes in `Input\WRITE_VAR`: `insert_row`, then `set_value` on `#0`, `#1`, ...
4. Put one Fortran line in each row of `Input\FORTRAN_EXEC` (`insert_row`, then `set_value`).

A value written to a block input is used by the run but not stored: the flash ran at 90 C while its `Input\TEMP` still reads 95 C.

Lines are fixed-form Fortran: begin each in column 7, after six spaces. A line that begins in column 1 stops the run before it starts.

With read and write lists the run places the calculator itself. Without them set `WHEN`; with neither the run does not start.

## Calculate

| Path | Type | Purpose |
|---|---|---|
| `Input\READ_VAR\{row}` | variable name | A defined variable it reads |
| `Input\WRITE_VAR\{row}` | variable name | A defined variable it writes |
| `Input\FORTRAN_EXEC\{row}` | Fortran line | One executable line, e.g. `      FLT = 85.0 + FEEDB/10.0` |
| `Input\FORTRAN_DEC\{row}` | Fortran line | One declaration of a local variable, e.g. `      REAL*8 X` |
| `Input\METHOD` | int | `0` (the default): the calculation is Fortran lines |

## Sequence

| Path | Type | Purpose |
|---|---|---|
| `Input\WHEN` | `FIRST`, `BEFORE`, `AFTER` | When it runs: once at the start, or just before or after the object in `BLK_ID` |
| `Input\BLOCK_TYPE` | `BLOCK`, `CONVERGENCE`, `CALCULATOR`, `TRANSFER`, `BALANCE` | Kind of object `BLK_ID` names |
| `Input\BLK_ID` | ID | The object it runs before or after |

## Streams it writes

| Path | Type | Purpose |
|---|---|---|
| `Input\KODE\{stream}` | `NOFLASH`, `TP`, `PH`, `PV`, `TH`, `TV` | How a stream it writes is flashed afterwards; one row per stream, labelled with its ID |

## Diagnostics

| Path | Type | Purpose |
|---|---|---|
| `Input\TERM_LEVEL` | int 0-10 | Detail of messages on the control panel |
| `Input\SIM_LEVEL` | int 0-10 | Detail of messages in the history |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BLKSTAT` | int | 0 when it ran without error |
| `Output\VARID\{n}` | string | Names of its variables |
| `Output\READ_VAL\{n}` | real | Value each variable had when read, same order |
| `Output\WRITE_VAL\{n}` | real | Value each written variable got |
