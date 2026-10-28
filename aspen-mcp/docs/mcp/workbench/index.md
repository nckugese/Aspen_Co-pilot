# Aspen Workbench

A desktop window beside Aspen Plus with one tab per model. A model tab shows the flowsheet with an inspector, a block program, the AI chat and the change log; the model's other programs and the AI's proposals are its sub-tabs. The user inspects streams and blocks, builds block programs, asks the AI (Ask AI requests) and approves the AI's proposals. The AI works in it with four tools.

## Tools

| Tool | Purpose |
|---|---|
| `open_workbench(session_name, new_tab=False, title=None, lang=None)` | Open the window and show the model's tab (made the first time, with its kept History and chat; never a second one). `new_tab=True` adds a program sub-tab. The answer names the tab and sub-tab ids |
| `workbench_read(session_name=None, tab=None)` | The tab as JSON: requests (`notes`), selection, program with ids, flowsheet, last run, proposals, model state, changes, review state ([below](#workbench_read)) |
| `workbench_edit(session_name=None, tab=None, program=None, insert=None, after_id=None, remove_ids=None, highlight=None, message=None, note_replies=None, refresh_flowsheet=False, lang=None, proposal=None)` | Change a tab live: replace the program, insert statements after `after_id` (none: at the end), remove by id, highlight objects, post a chat message, answer requests, write a proposal, set the language. Each change is one undo step for the user |
| `workbench_run(session_name=None, tab=None, dry_run=True)` | Check (default) or run a tab's program; returns the log, loop tables, tables, plots and Pareto sets ([runs.md](runs.md)) |

## Which tab a call means

1. `tab` (id or title); with `session_name` as well, the tab must be on that session.
2. Else, with `session_name`: the active tab if it is on that session, else that model's tab, else the session's first tab.
3. Else the active tab.

A proposal id kept in History or deleted gets an answer saying so ([proposals.md](proposals.md#history)). `workbench_read` on an open session no tab shows returns `{"tab": null, "session", "window_open", "tabs", "brief", "model_status", "checkpoints", "changes", "brake"}`.

## Opening and working modes

- `open_aspen_plus` and `create_new_simulation` open the window on the session they open and add `[workbench]` lines to the answer, unless the mode is `chat` or `ASPEN_MCP_WORKBENCH_AUTO=0`. A window that cannot open (no pywebview, or the standalone workbench or another AI client's server serves it) leaves the model open and says why.
- `mode` (asked once per session before opening, the aspen-process-workflow skill): `workbench` (proposals of blocks, questions as choices) or `chat` (the conversation; the window stays shut). It is recorded per session and shown in the `[workbench]` lines and `workbench_read` `mode`. Never recorded: the window opens and the answer reminds the AI to ask. `open_workbench` switches a session to `workbench`.
- `open_workbench` is refused for a session opened by another process (the standalone workbench or another AI client's server), and while another one serves the window.
- `lang`: `en` or `zh`; pass `zh` when the user writes Chinese. The window keeps the last language.
- The first opening result in a server process may say how the user connects Ask AI ([requests.md](requests.md#how-requests-reach-the-ai)): tell them once.

## workbench_read

| Key | Content |
|---|---|
| `tab`, `model_tab`, `tabs` | The tab read (`id`, `title`, `session`, `kind`, `parent`); its model tab (`stale` when its file is no longer the session's); all model tabs with their sub-tabs as `children` |
| `archived` | `true`: a proposal read from History |
| `window_open`, `lang`, `mode` | Window state; the session's working mode |
| `selection` | What the user selected |
| `notes` | Ask AI requests ([requests.md](requests.md)) |
| `program`, `program_origin` | Statements with ids ([program-format.md](program-format.md)) |
| `flowsheet` | `blocks` ("NAME (TYPE)"), `streams` ("FROM -[S]-> TO"), `components`, `block_errors`, `arrangement`, `model` {id, file} |
| `last_run` | `status`, `dry_run`, `paused`, `wait`, `vars`, `log_tail` (20 lines), `tables` (60 rows each, `rows_total`), `optimizations` |
| `model_state` | Where the last real run left the model ([program-format.md](program-format.md#where-a-program-leaves-the-model)) |
| `window_sim`, `window_saved` | The user's last Run simulation and Save model ([runs.md](runs.md#the-windows-run-simulation-and-save-model)) |
| `model_status`, `changes`, `brief`, `checkpoints` | Change journal views ([changes.md](changes.md)) |
| `missing`, `diagnosis` | What Aspen still needs; why the last run failed ([runs.md](runs.md)) |
| `proposals`, `proposal_history`, `closed_proposals` | [proposals.md](proposals.md#what-workbench_read-lists) |
| `history` | Program undo / redo counts |
| `brake` | Review mode and pause ([review.md](review.md)) |
| `learning` | `true` in learning mode |
| `hint` | A proposal's run is tagged and not explained yet |

## Layout reminder

Placing, removing, connecting and disconnecting leave Aspen's own drawing stacked. Run `layout_flowsheet` once when a request's topology edits are done. The server reminds you once per request: a line at the end of a `run_simulation`, `save_simulation` or `workbench_edit` with `note_replies` answer, or of the next request's first call. A successful `layout_flowsheet` clears it.

## Files here

| File | Read it for |
|---|---|
| [program-format.md](program-format.md) | Every statement, expressions, finish, checks and their codes, `pinch` |
| [proposals.md](proposals.md) | Writing and revising proposals, statuses, approval, groups, result tags and their explanation |
| [requests.md](requests.md) | Ask AI requests, `note_replies`, choices, highlights, how requests reach the AI, a heat plan request |
| [runs.md](runs.md) | `workbench_run`, stepping, manual steps, the window's Run and Save, faults, diagnosis, missing inputs |
| [review.md](review.md) | Review modes, "Not applied" answers, learning mode, one writer per session |
| [changes.md](changes.md) | The change journal, `[workbench]` lines, Aspen-window edits, restore points, undo, convert to program |
| [window.md](window.md) | What the user sees and where to click, the flowsheet arrangement, keys, `.awb` files, English–Chinese words |
| [files.md](files.md) | Files under `~/.aspen-mcp`, environment variables, features, window events |
