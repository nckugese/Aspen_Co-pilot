# Proposals

A proposal is a block program the AI writes for the user to review. It is a sub-tab of its model's tab. Only the user runs it, and running it is the approval: `workbench_run(dry_run=False)` on a proposal is refused in every review mode, `dry_run=True` checks it. In read-only review mode this is how the AI makes changes at all.

## Writing and revising

`workbench_edit(session_name, proposal={...}, program=[...])` opens a new proposal; with `tab` set to a proposal's id it revises that one.

| Key | Purpose |
|---|---|
| `title` | Required for a new one; one line, cut to 120 characters (the tab shows 60) |
| `reason` | Why, cut to 1000 characters |
| `status` | `ready` (default: waits for review), `draft` (cannot be approved yet), `withdrawn` (takes an existing one back) |
| `watch` | Up to 3 results `[{"path", "label"?}]` tagged after its run, the goal first ([below](#result-tags)) |
| `explain` | After its run: how the change reached the tagged results ([below](#explaining-the-tags)) |

- A new proposal needs steps unless it is a draft. With `tab` naming a tab that is not a proposal, the new one starts from that tab's program, then the edits apply. A proposal on a model with no tab open makes its tab.
- Any change of program, title, reason or status on a proposal tab is a revision: `rev` + 1, status back to waiting for review (a draft stays a draft), the user's edits replaced (their version stays one undo away). A revision while the user runs it is refused.
- `watch` and `explain` are not revisions: no new rev, no reopening, no check.
- Give every step a `why`. In learning mode the answer names the steps without one, and the headed groups without a `principle` key.
- When its model is open and idle, a new or revised proposal is checked at once; otherwise the user presses Check.

## Statuses

| Status | Window | Where |
|---|---|---|
| `draft` | Draft | sub-tab row |
| `open` | To review | sub-tab row |
| `running` | Running / Stepping | sub-tab row |
| `partial` | Partly applied | sub-tab row |
| `failed` | Failed | sub-tab row |
| `stopped` | Stopped | sub-tab row |
| `applied` | Applied | History |
| `rejected` | Sent back | History |
| `withdrawn` | Withdrawn | History |
| `dismissed` | Closed (`dismissed` {t, was}) | History |

## What the user does

1. **Approve and run**, **Approve step by step** or **Approve by group** (the default in learning mode). Refused at once for `draft`, `running`, `withdrawn`, `dismissed`, or with every step turned off.
2. The program is checked against the model as it is now; any error and nothing happens.
3. A restore point is made, however long it takes; when none can be saved the user may run without one.
4. The steps run as one change group, each record marked approved by the user and linked to the proposal. The end is `applied`, `partial` (a step failed or was stopped after something changed), `failed` or `stopped`.

Afterwards the user may **Restore to before the proposal**, **Undo this group**, or, after a stop part-way, **Continue from step N**: the same mode, the model-changing steps before N not run again, the first restore point kept. Continuing needs the program as the run left it (`run.resume.rev` = the tab's `program_rev`) and nothing taken back. **Send back…** sends the user's comment (may be empty) to the AI as a note: status `rejected` until the AI revises. **Close proposal** makes it `dismissed`; a revision reopens it.

## After the run

- An end of `applied`, `partial` or `failed` (not a stop) adds a note with `event: "proposal_end"`, `outcome` and target `{"kind": "proposal", "tab", "name"}`, pushed like a request, so a phased workflow goes on. Close it with `note_replies=[{"id", "done": true}]`; no reply needed.
- Revising after a `partial` or `failed` run (not undone): the top-level steps that applied and are unchanged start `"off": true` and are listed in `proposal.ran`; the answer names them. Left on, a step that placed a block would fail the check (`exists`). After the first changed step, unchanged runs, sweeps, optimizations and saves stay on, so they work on the changed model; sets and flowsheet steps do not.
- The user may edit an `applied` or `partial` proposal after its run (not undone). The edits its run did not apply are listed in `proposal.unapplied` (statement ids), and the card offers **Apply my changes and run**. That is an approval like the first, with a new restore point and its own change group. The same steps a revision would turn off are left out of it, without changing the program. A step turned off or removed is not taken out of the model. Run simulation in the header only runs Aspen; it does not apply block edits.

## History

- Finished proposals (`applied`, `rejected`, `withdrawn`, `dismissed`) go to the model's History; at most 8 stay loaded, older ones are archived in `~/.aspen-mcp/workbench/proposals/<model id>/`.
- A tab id stays valid in History: `workbench_read(tab=…)` reads it there (`"archived": true`); `workbench_edit` with a revision reopens it as a sub-tab; a withdrawal, `watch`, `explain` or message is written into the kept record; `workbench_run(dry_run=True)` is refused until it is reopened.
- A tab id whose record the user deleted answers so: write a new proposal.
- Closing a model's tab never deletes a proposal: they come back with the model's chat when its file is opened again.

## What workbench_read lists

| Key | Content |
|---|---|
| `proposals` | The model's loaded proposals, latest first, at most 5: `tab`, `title`, `status`, `rev`, `edited` (the user's edits), `unapplied` (edits its run did not apply), `reply`, `run`, `refused`, `check` {ok, errors, warns, current, problems (at most 5)}, `watch`, `effects`, `explained` |
| `proposal_history` | The latest 5 finished: `tab`, `title`, `status`, `was`, `rev`, `t`, `group`, `undone`, `archived` |
| `closed_proposals` | The latest 3 closed without running |

## Groups

A `group` heading names the purpose of the steps under it; **Approve by group** pauses before each group's first step that changes the model.

- One heading per purpose (a new unit with its streams and settings, one change of conditions), at most 8 per proposal. `title` like "Add the scrubber SCRUB", `why` one clause.
- A step without `why` takes its heading's as the reason of what it changes.
- Steps before the first heading join group 1 when all are technical, else form their own group.
- A last group that only runs the simulation joins the one before.
- Without headings the server groups the program itself: consecutive steps on one block or stream form a group (a placed block takes its streams, connects and sets), a run / if / call / save joins the group before, technical steps join the next one, runs of single sets or single placements merge, and past 8 groups the smallest merges into its smaller neighbour.

A check's `tab.check.groups` lists them: `n`, `sid` (null: automatic), `key` (the heading's sid, or `~` + the first step's), `title`, `tpl`, `auto`, `why`, `principle`, `rows`, `tech`, `tech_kinds`, `objs`, `at` (the step a run by group pauses before; null when the group changes nothing). Each record of such a run carries `gsid` = its group's `key`.

## Principle cards

`"principle": ["<key>"]` on a heading (or its steps) shows the library card of that key in learning mode: [principles/index.md](../../principles/index.md) lists the keys and when each fits. Leave it off where none fits. A group with no key may get one inferred from `docs/principles/rules.md` (a field of a block type mapped to a key).

## Result tags

`watch` names the results that tell whether the proposal worked, the goal first (the product purity or rate the phase is for). Prefer mass basis (`MASSFRAC`, `MASSFLOW`); a model without it is read at the mole-basis twin. The label is a short word, no numbers. The check warns `watch_missing` for a path the model does not have, unless a step places its object.

After the run the window tags at most 3 objects with before → after values: the watched results first, then results the run moved past the thresholds (a temperature 0.5 K, a fraction 0.001, anything else 0.5 % relative). `workbench_read` `proposals[].effects` holds them: `run`, `joint_outside` (inputs changed outside the proposal took effect in the same run), `more`, `items` [{path, b, a, u, goal}]. In the chat afterwards do not repeat these numbers; add only what the drawing does not show (a yearly capacity, a cost, a judgement, the next step).

## Explaining the tags

```
workbench_edit(tab, proposal={"explain": {"run": "<effects.run>", "items": [
  {"result": "<a path in effects.items>",
   "via": ["VENT", "SCRUB", "WASHLIQ", "MIXB", "COL", "PRODUCT"],
   "words": {"SCRUB": "ethanol dissolves in the wash"},
   "text": "The vent's ethanol dissolves in SCRUB's wash and returns with it to the column."}]}})
```

- At most 3 items; `run` must be the run the tags show now. `{"explain": null}` clears it.
- `via`: 2 to 24 blocks and streams in flow order; used only when each step follows a stream of the flowsheet, else the window finds the path itself.
- `words`: one object, cut to 12 CJK or 24 other characters. `text`: one sentence on the mechanism, cut to 140 CJK or 280 other characters.
- No numbers in `words` or `text` (a digit inside a name such as HX1 or CO2 is fine): such an item is dropped and the answer says so.
