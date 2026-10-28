# Run mode

Sequential modular solves the blocks one after another; equation oriented solves the whole flowsheet at once.

Root: `\Data\Setup`

| Path | Type | Purpose |
|---|---|---|
| `Sim-Options\Input\PARADIGM` | `SM`, `MIXED` | Solution mode; `SM` is the default |

With `EO` a run started over COM never starts: no Run-Status, no results. Keep `SM` (or `MIXED`) for runs and optimizations driven from here.

## Run status (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Results Summary\Run-Status\Output\UOSSTAT2` | int | Verdict of the last run: 8 clean, 9 errors, 10 warnings only |

It reads 9 after a block error and 10 when the worst is a warning.
