# Change journal, undo and restore points

The server records every change to a model as it measured it, not as a tool reported it: the AI's tool calls, the user's actions in the window, block program steps, the optimizer, and edits found in Aspen's own window.

## Records

- A value written is one record with value, unit and basis read before and after. A block, stream, component, reaction, row or element added or removed is one; a connection is one (naming any stream it took off the port); taking a stream off a port is one per end.
- A run says ok, warn or error, which blocks, and `msgs` (Aspen's run-status lines, at most 20; `nmsgs` all). A save or layout lists the files written and their backups.
- A loop or an optimization is one summary record: points, range, where each input started and ended, runs.
- Each record has `actor` (`ai`, `user`, `program`, `optimizer`, `external`), `via` (`mcp`, `window`, `inspector`, `program`, `aspen`), the tool, and `status` (`changed`, `unchanged`, `failed`, `refused`, `error`).
- A long call (the AI's optimize, a program run, each loop in it) leaves a `begin` record closed by its summary or `end`. A server that died in between leaves only the begin; the next server tells the AI once.
- A changing tool's optional `reason` (one sentence) is kept on the call's first record and shown as the AI's own words; a statement's `why` is recorded the same way (`reason_src: "why"`).
- File: `~/.aspen-mcp/journal/<model id>/journal.jsonl` (the id is `workbench_read` `flowsheet.model.id`, from `~/.aspen-mcp/models.json`). Past 8 MB it rotates; above 200 MB of archives, files older than 180 days go. A record that cannot be written is logged and dropped; no tool fails for it.
- `ASPEN_MCP_JOURNAL=0` stops recording, and with it the Changes tab, undo, the auto-pause rules, predictions, Convert to program, result tags and the `[workbench]` lines. Review modes, pauses, approvals and learning mode still act.

## Change groups

- The AI's changes form one group per Ask AI request: a new group starts when the request it works on changes, once that request is closed, or after 90 s without an AI call (counted from the end of the last call).
- Title: the request's text, else the first `reason`, else what it did ("3 values, 1 addition").
- A program run is one group (actor `program`; started by `workbench_run`, linked to the AI's group). The user's hand edits split after 90 s of quiet. An optimization joins its starter's group.

## What the AI reads

`workbench_read` `changes`: the newest three groups of the model, newest first, each with its lines oldest first (about 3000 characters in all; older lines counted in a "…" line):

```json
{"model": "m3f2a9c01be", "total": 42, "note": "values measured by the server; reason = the AI's own words",
 "groups": [{"id": "g…", "actor": "ai", "title": "Raise the top purity", "t0": "2026-09-26 14:02",
             "t1": "2026-09-26 14:05", "n": 3,
             "lines": ["14:02 ai set_value ESTCOL BASIS_RR 1.5 → 2 · reason: purity above 99 %",
                       "14:03 ai run_simulation run: ok"]}]}
```

Asked what it changed, the AI answers from these lines.

`workbench_read` `model_status` (also for a session no tab shows): `file`, `unsaved` (net inputs changed since the file was in step), `runs_since_save`, `stale` {n, paths: inputs changed since the last run, at most 10}, `last_run` {seq, status, t, actor, via, errors, warnings, delta_top}, `last_save` {t, actor, via, how}, `external_checked`.

## [workbench] lines

After the user, a program the user started, or Aspen's own window changes the model, the AI's next result starts with up to 8 `[workbench]` lines saying what changed, fields in words with their path (a JSON result: `workbench_brief`; `workbench_read`: `brief`). The AI's own changes, including programs it ran, are never told back. They also tell: a pause that ended (with the user's note and what changed meanwhile), a pause still on, an automatic pause, a review-mode switch, an approval decided after its call ended, a learning-mode switch, a restore, an undo. Each is told once. Take them into account before continuing.

## Edits in Aspen's own window

Found by comparing, not watched: before each AI call; before the window's Run, Save, applied points and inspector edits; about 2 s after the user leaves Aspen's window. Compared: fields inspected, inputs changed since the last run, each block's usual inputs, feed conditions, what the AI read. Not caught: edits before the first compare, other fields, rewiring only, a rerun that changes nothing. The inspector's **Check for edits in the Aspen window** reads every input of one block or stream. Recorded `actor: "external"`, `via: "aspen"`, with `detect`, `since`, `known`, `why`. `ASPEN_MCP_EXTERNAL=0` turns it off.

## Restore points

- Made before the AI's first structural change in a request, before each optimization and before a proposal's approved run. Reused when nothing changed since the last; a copy of the model file when the model is what the file holds; otherwise an export if it takes at most `ASPEN_MCP_CHECKPOINT_MAX_S` (15 s). Otherwise none, and the AI's answer says so.
- Value changes never make one; `create_chemistry` copies the saved file first; `layout_flowsheet` makes none.
- The user can make a named one (kept). Automatic ones rotate, 20 per model; above 1 GB in all the oldest automatic ones go.
- A copy of the file holds what the file held: an Aspen-window edit no compare found is not in it.
- `workbench_read` `checkpoints`: the newest 5, `{id, at, name, reason, state (saved | live), kept}`. Restoring is the user's, from the window.
- Restore: the current state saved as a point first (unless unticked), the model file (`.bkp` only) backed up and replaced, Aspen reopens it under the same session name; tabs, programs and notes stay. Refused while a program or the AI's optimize changes the model. Files: `~/.aspen-mcp/checkpoints/<model id>/`.

## Undo

Every change in the Changes tab can be taken back by the user: one record, a whole group, or an undo itself (redo). The window previews first; applying writes exactly the preview, or, if the model changed meanwhile, nothing and a new preview. Values come back from the recorded before values (value, unit, basis); added blocks, streams, connections, list rows and subobjects are removed (a row by its label: shared rows go once); deletions and other structural changes need a restore point (**Restore to before this group** = restore, then undo of the older values). Results are not undone: run again. The AI is told at the top of its next call.

## Convert to program

The user can turn a change group or picked records into a block program in a new tab ("Redo: …"); nothing changes until it runs. Oldest first: a value → `set` (unit or basis only where the call gave one; the property method → `method`), a run → `run` (a Reinitialize just before it → `"reinit": true`), additions and removals → `place`, `remove`, `component`, a connection → `connect`, a disconnect → `remove` with its port, a loop's or optimization's summary → a `set` of each field it left changed. Consecutive sets of one field fold into the last; a call's reason becomes the first statement's `why`. Skipped and counted: attribute settings, saves, restore points, opening and closing, analyses, file edits, redraws, a Reinitialize with no run after it, a restore, reactions, table rows, other elements, a loop with no end, a block whose type was not recorded; failed, refused and unchanged records.
