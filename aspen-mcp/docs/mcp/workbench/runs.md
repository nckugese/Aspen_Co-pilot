# Runs

## workbench_run

`workbench_run(session_name=None, tab=None, dry_run=True)` checks (`dry_run=True`, the default) or runs a tab's program and returns its log, one table per loop, table and plot, and each optimization's feasible count and Pareto set (at most about 9000 characters). Ask the user before `dry_run=False`; a proposal is never run this way ([proposals.md](proposals.md)).

- Refused at once when the tab already runs, or its session is busy with another tab (named, with where it is paused); a real run also waits up to 10 s for another writer ([review.md](review.md#one-writer-at-a-time)).
- A tab whose model is no longer the session's file (stale) cannot run.
- A run that reaches a manual step returns there ("Paused at step 3 (…, your turn): waiting for the user to set …") while it goes on waiting.
- Stop acts before the next statement, never inside an Aspen run or an optimization.
- A real run's tables and optimization results stay on the tab (the Results panel), so a later check does not wipe them; the next real run that makes any replaces them.

Runs belong to tabs. Tabs on different sessions run at the same time, interleaved statement by statement; a tab whose session is in use waits as queued.

## Stepping

The user can step through a program or a proposal's approval.

- **Step**: pauses before every step outside a loop; an `if` and a `call` count, and so does each statement of the branch taken or the procedure called. A loop or an `optimize` is one step. Breakpoints (`tab.breaks`) pause any run the window starts; a step inside a loop cannot have one.
- **By group**: pauses before each group's first step that changes the model (its heading and the technical steps ahead of it run first). Next applies the group and pauses before the next; Apply the rest goes on without pausing.
- While paused the program holds the session with no timeout. Only the user's inspector edits go through, recorded as the user's in the run's change group and kept when the program ends. The AI's changes are refused, naming the step.
- `workbench_read` `last_run.paused`: `at` (the statement), `n`, `since`, `why` (`group` for a by-group pause), `next` (what the step does: current → new value). By group, state.json's `run.paused.group` also holds the group's head, its `rows` (at most 12, current → new) and `conflict` (fields it sets that the user set by hand since the approval).
- Stop, closing the window or a server restart ends the run.

## Manual steps

A `yourturn` statement stops the run until the user sets the named input (in the inspector or in Aspen's own window) and presses Done; no timeout. Use it in a teaching proposal instead of setting the value yourself.

- Meanwhile the program keeps the model: the user's edits, Run simulation, Save and restore points go through; the AI's changes are refused, naming the field; other programs queue.
- `workbench_read` `last_run.wait`: `sid`, `n`, `path`, `hint`, `t`, `tries`, `msg` (null, `unchanged`, `expect`), `expect`, `before`, `now`.
- Done with the value unchanged asks to confirm; an `expect` not met keeps waiting. After 3 misses, a step with an `answer` offers **Show answer**, which writes it and goes on.
- A value that passes is recorded as the user's and held in the step's variable.
- Stop or a server restart ends the wait; a closed window does not.

## The window's Run simulation and Save model

**Run simulation** (F5) runs the model once as it stands, like Aspen's Run, without the program; **Reinitialize, then run** first goes back to initial estimates. Refused while a program or the AI's optimize holds the session. `workbench_read` `window_sim` is its last outcome:

| Key | Content |
|---|---|
| `status` | `running`, `done`, `error` (did not run: incomplete inputs, no session, a fault), `busy` (refused) |
| `outcome` | `ok`, `warn`, `error`, or `unknown` (the run status could not be read; never taken as converged) |
| `errors`, `warns` | Blocks with errors or warnings |
| `msgs`, `nmsgs` | Aspen's run-status lines (at most 20, information lines dropped first), and how many in all |
| `first_warn`, `warns_more` | After a warned run: `{kind, objs, where, line}` and up to 3 more. `kind` `block`, `conv`, `flash`, `input`, `calc`, `prop`, `other`; `where` `blk` (the block's Results › Status), `conv` (Convergence results), `cp` (Control Panel), `rs` (Results Summary › Run Status) |
| `text` | The line a program's run step would log |
| `source` | `apply_point` for a point applied from a sweep, design spec or optimization result |
| `incomplete` | A run refused for incomplete inputs |

A line Aspen writes after every clean run ("… was never executed") and information messages are not warnings.

**Save model** (Ctrl+S) saves as `save_simulation` does: the file backed up first, then written to the session's file on record; `window_saved` holds the last one (`path`, `backup`).

## Internal fault

When Aspen reports an internal fault (RPC_E_SERVERFAULT) in a session, every later run of it is refused (the AI's `run_simulation` and Reinitialize, the window's Run, a program's run step, applying a point, an optimization) until the model is opened again; reads keep working. A re-run the server would make by itself is recorded `refused`.

## Why a run failed

After a run that fails, warns or is refused for incomplete inputs, whoever ran it, the window builds a diagnosis card: where it failed (most upstream block first), the failure kind, matching error-history entries, and what changed since the last good run. `workbench_read` `diagnosis`: `level` (`error`, `warn`, `refused`), `run`, `text` (at most 600 characters), `fixed` once a later run ended ok. When someone else's run failed, the AI's next result starts with a `why:` line. The AI's corrections after a failure are grouped as **Diagnose and fix: <block>** until a run converges (an open Ask AI request takes precedence). A request about a run has target `{"kind": "run", "id"}`.

## What Aspen still needs

After every run, open and burst of edits, the server reads Aspen's completeness flags. `workbench_read` `missing`: `state` (`complete`, `incomplete`), `n`, `runnable`, `objects` (names), `more`, `stale`; `check_inputs` gives the details. A RadFrac with fewer operating specs than it needs, and an MCompr knockout stream without `PROD_PHASE`, are listed by the workbench's own rule (`rule_by: "server"`). `ASPEN_MCP_MISSING_SCAN=0` turns the automatic scan off.
