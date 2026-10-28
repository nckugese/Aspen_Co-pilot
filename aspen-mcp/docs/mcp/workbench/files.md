# Files, settings and window events

## Files

Under `~/.aspen-mcp/workbench/`:

| File | Written by | Holds |
|---|---|---|
| `state.json` | server | Tabs, programs (with loose stacks) and their versions, requests, run logs, tables, optimization results, each session's flowsheet, arrangement and journal summary, `catalog` |
| `events.jsonl` | window | The window's events (below) |
| `heartbeat` | server | About once a second while it serves the window: `{"v": 1, "t", "pid", "loop", "act", "last", "holders"}` (calls in flight, the last one ended, who holds each session). Older than 6 s: the server is gone; `loop` 2.5 s behind `t`: busy |
| `owner.json` | server | `{"pid", "srv", "root", "t"}` of the server that serves the window; `"standalone": true` when that is the standalone workbench (below) |
| `handoff.json` | the standalone workbench and an AI client's server | The standalone workbench's sessions and window going to an AI client's server (below) |
| `prefs.json` | window | Panel sizes, layers, drafts, one-time hints, per-model view choices (`wb.*` keys) |
| `learn.json` | server | Learning mode's flag ([review.md](review.md#learning-mode)) |
| `asks-handed.json`, `ai_turn.json` | plugin hooks | Requests the hooks handed the AI; the AI's turn `{start, begin, stop, client, owner, mine}` |
| `pins/<model id>.json` | server | Notes pinned on blocks and streams |
| `layouts/<model id>.json` | server | The model's arrangement and the last layout read from Aspen |
| `proposals/<model id>/` | server | Proposals not loaded: `<tab id>.json`, `index.json` (entries and deletion marks), `model.json` (the model tab's chat when it closed) |
| `runs/<tab id>/` | server | Optimization results of program steps |

Elsewhere under `~/.aspen-mcp/`:

| Path | Holds |
|---|---|
| `journal/<model id>/journal.jsonl` | The change journal ([changes.md](changes.md)); `deep/<kind>-<NAME>.json.gz` the notes of the inspector's check for Aspen-window edits (at most 200 per model) |
| `checkpoints/<model id>/` | Restore points (`index.jsonl`, `.bkp` with any `.apw` / `.def`) and the backups made before a file was overwritten or restored |
| `models.json` | The model id registry |
| `aspen-strings/<version>/` | Field, option, form and sheet names read from the local Aspen, never shipped: `labels.json`, `prompts.tsv.gz`, `learned.json`; `status.json` the last extraction. The newest two versions kept |
| `codex-app-servers/<pid>.json` | Codex app-servers the plugin's launcher started |

The Aspen strings are read once in the background when the workbench first opens, and again when Aspen's localization DLL changes; `aspen-mcp --extract-strings` runs it now, `ASPEN_LOCALIZATION_DLL` points at another DLL. Without them fields keep the workbench's own names and options show their codes.

`aspen-mcp --check` reports, besides the install: the model registry, restore points, the journal, the heartbeat, review, which server serves the window, the Aspen strings, and how many tools are registered and classified.

## Without an AI client

`aspen-mcp --workbench [model.bkp ...] [--hidden] [--lang zh|en]` opens the workbench with no MCP client and no network: that process holds the Aspen sessions and runs the sync loop. Values, runs, block programs, restore points and **Open Aspen model…** work as with a client; Ask AI requests wait for one. With no file the window opens on the tabs it had, and a model one of them shows that a visible running Aspen still has open is taken back. It ends when the window closes; Aspen stays open.

Aspen registers each open document under its file's path (the Running Object Table), so a server takes a document that is already open without opening the file again: `open_aspen_plus` and **Open Aspen model…** do for a file a running Aspen has open (the user's own included), and the answer says so.

When an AI client's server gets a tool call while a standalone workbench serves the window, it takes that workbench's sessions and the window over before the call runs: the standalone process lets go and exits, the server attaches to the same running documents, the window stays open. Nothing is saved, closed or reopened. The standalone workbench refuses while a program or a run is in progress; the call then runs without the sessions and asks again 10 s later at the earliest. Only a standalone owner is asked: two AI clients' servers never take each other's sessions.

The window is a pywebview window on Edge WebView2, provisioned by `uv` on first use.

## Environment

| Variable | Effect |
|---|---|
| `ASPEN_MCP_WORKBENCH_AUTO=0` | The window no longer opens with each session opened |
| `ASPEN_MCP_CHANNELS=1` | Claim that the client takes pushed Ask AI requests (Claude Code with the channels flag) |
| `ASPEN_MCP_CHANNEL_SPEC` | The channel spec the server's hint names, verbatim |
| `ASPEN_MCP_CODEX_APP_SERVER` | The Codex app-server URL, in place of the launcher's record |
| `ASPEN_MCP_BRAKE=0` | No review modes, pauses or approvals |
| `ASPEN_MCP_ATTACH=0` | A file a running Aspen already has open is opened a second time, not taken as it is |
| `ASPEN_MCP_HOLD_S` | Seconds a held call waits for the user |
| `ASPEN_MCP_JOURNAL=0` | No change journal, and nothing built on it |
| `ASPEN_MCP_EXTERNAL=0` | Edits in Aspen's own window are not looked for |
| `ASPEN_MCP_LEARN=0` | Learning mode enforces nothing |
| `ASPEN_MCP_LEARN_WEAK=remind` | A weak reason gets a reminder, not a refusal |
| `ASPEN_MCP_GROUPS=0` | No `group` statement, no run by group |
| `ASPEN_MCP_PREVIEW=0` | No proposal preview on the flowsheet |
| `ASPEN_MCP_MISSING_SCAN=0` | No automatic completeness scan |
| `ASPEN_MCP_CHECKPOINT_MAX_S` | Longest automatic restore-point export, seconds (15) |
| `ASPEN_LOCALIZATION_DLL` | The DLL the Aspen strings are read from |

## Features

The window hides a control whose part the server runs without (for example the journal, review or learning mode turned off by the variables above) and shows the rest.

## Window events

Each line of `events.jsonl` is `{"type", ...}`; the server answers in `state.json`.

| Event | Answer |
|---|---|
| `run {tab, dry_run, approve?, mode: run \| step \| group}` | The tab's `run` (and `proposal` for an approval) |
| `stop {tab}`, `step {tab, action: next \| cont}`, `breaks {tab, ids}` | The tab's `run.paused`, `breaks` |
| `program {tab, program}`, `undo`, `redo` | The tab's program and versions |
| `tab_new {session, parent?, title?}`, `tab_close {tab, stop?}`, `tab_close_cancel`, `tab_active`, `tab_rename` | `tabs`, `active` |
| `prop_open`, `prop_shelve`, `prop_delete {tab}` | `history`, the tab |
| `proposal_reply {tab, action: reject \| dismiss, text?}` | The tab's `proposal`; a note to the AI for reject |
| `note_add`, `note_edit`, `note_delete`, `note_choose {id, picks}` | The session's `notes` |
| `set_value`, `run_sim`, `save_model`, `apply_point` | The session's `sim`, `saved` |
| `inspect`, `close_inspect`, `select`, `inspect_sheet {tab, target, form, sheet, ids}`, `field_info {tab, path}`, `ext_deep` | The tab's `inspect`, `isheet`, `field_info`, `ext_deep` |
| `struct {tab, op, lists, path, label}` | `op` `row_add` / `row_del`: a row `label` into or out of the `lists` of one table (insert_row + set_label, remove_row; a list sharing the first one's rows is left alone); `sub_add` / `sub_del`: subobject `label` into or out of collection `path` (add_element, remove_element). Journaled as those tools are (via `inspector`), a chat line whose `record` lists the records (comma-separated); the inspector and the sheet read again |
| `missing {tab, paths?}` | The session's `missing` |
| `objects {tab, open?}` | The session's `objects` {t, items: [{path, name, g (setup, components, properties, reactions, convergence, flowsheeting, analysis), c (its container), type?, todo? (Aspen flags it incomplete)}], open}: the model panel's objects, read when it opens (40 a container); a Sensitivity folder is one item {n, folder} until `open` names it |
| `revert`, `restore`, `checkpoint`, `keep_checkpoint` | The session's `undo_req`, `restore_req`, `cp` |
| `to_blocks {tab, model, group \| ids, req}` | The session's `to_blocks_req` and a new tab |
| `aspen_redraw {tab, req}`, `aspen_place {tab, req, blocks}`, `aspen_layout`, `fs_layout`, `refresh` | The session's `redraw_req`, layouts, flowsheet |
| `brake_mode`, `brake_pause`, `brake_resume`, `brake_card`, `brake_dismiss`, `brake_stuck` | `brake` |
| `learn_mode {on}` | `learn` |
| `predict_watch {tab, id, paths}`, `predict_clear` | The session's `predict` |
| `yourturn_done {tab, force?}`, `yourturn_answer {tab}` | The tab's `run.wait`, then the run goes on |
| `pin_hide {tab, id}` | The session's `pins` |
| `flows {tab, on, comp}`, `stream_comp {tab, stream}` | The session's `flows`, `stream_comp` |
| `labels_learn`, `results`, `lang`, `closed` | Field names, results, language, the window closed |
| `open_model {paths, req}` | The **+** menu's **Open Aspen model…**: only `.bkp`, `.apw` and `.apwz` files; each file (8 at most) opened as a session of the server that serves the window -- one a running Aspen has open is taken as it is -- and shown in its model's tab; `open_req` {req, t, done: [{path, state ok \| error, text}]} |
