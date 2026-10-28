# Ask AI requests

The user types a goal or a question in the Ask AI box ("outlet purity > 99 %: what should I change?"). Requests belong to the session: every tab on it shows them. They reach the AI as `workbench_read`'s `notes`, or pushed by themselves ([below](#how-requests-reach-the-ai)).

## A request

| Key | Content |
|---|---|
| `id` | The request's id (a pushed one carries it as `note_id`) |
| `text` | What the user wrote |
| `tab` | The tab it was sent from |
| `status` | `open` or `done` |
| `target` | null (the whole tab) or one of the kinds below |
| `target_text` | Open requests with a target: what it is, in words with its path (a change as measured, a group's counts and first lines, a field's value and last change, a step's statement) |
| `group`, `group_model` | The change group the AI's work on it made |
| `answer_to`, `picked` | A pick from choices: the request asked, and the labels picked |
| `event`, `outcome` | A server event, not the user's: `proposal_end` ([proposals.md](proposals.md#after-the-run)) |

| Target `kind` | Keys |
|---|---|
| `block`, `stream` | `name` |
| `change` | `id` (a change record), `model`, `label`, `obj`, `name`, `path` |
| `group` | `id` (a change group), `model`, `label` |
| `field` | `path`, `label`, `obj`, `name` (an inspector field) |
| `stmt` | `tab`, `sid`, `label` (a step of a program) |
| `run` | `id` (a run record), `model`, `label` |
| `proposal` | `tab`, `name` |

## Answering

1. `workbench_read` the request's tab.
2. Turn the goal into statements; look every path up in the docs. Ask when it is ambiguous (which component, mole or mass basis, which variables may move, what budget).
3. `workbench_edit` with the statements (`insert` or `program`, or a [proposal](proposals.md)), `highlight`, a short `message`, and `note_replies`.
4. Let the user check and run; call `workbench_run(dry_run=False)` only when asked.

Write replies, reasons and proposals in the user's language.

| `note_replies` item key | Purpose |
|---|---|
| `id` | The request answered |
| `reply` | The answer, shown under the request in the AI chat |
| `done` | `true` closes the request. `{"id", "done": true}` alone closes one that has an answer, or an event |
| `choices` | 2 to 6 options `[{"label", "detail"?}]` shown as buttons under the reply; labels unique, at most 80 characters, `detail` at most 240; the recommended first |
| `multi` | `true`: several options may be picked |
| `working` | `true`: more work follows (a subagent, a long call, the next proposal); it counts as a sign of the AI's turn, so the window shows **AI is thinking…** until the turn ends (the Stop hook; without hooks 30 s after the last sign) |

- An item with another key (`text`, `options` are the usual slips), a blank `reply` or bad `choices` is refused and changes nothing for its request; the answer names applied and refused ids.
- `choices` need their question in `reply` and leave the request open (`done` with them is refused). The user's pick closes it and arrives as a new request whose `text` is the labels, with `answer_to` and `picked`. The user may type an answer instead: an ordinary request. A later reply on the same request replaces the options.
- Ask with `choices` rather than listing options in the text.

## Highlights and notes

`highlight=[{"kind": "block" | "stream", "name", "note"?}]` outlines those objects on the flowsheet until the user presses Esc or the next `highlight` (`[]` clears). A `note` (one or two sentences on why) is also pinned on the object in the Annotations layer: at most 300 characters, 60 per model, kept in `~/.aspen-mcp/workbench/pins/<model id>.json`; the user can remove it.

`message` posts a line in the tab's AI chat. Each program change by `workbench_edit` also leaves a chat line counting statements added, changed and removed, with **Undo this change**.

## How requests reach the AI

Without any of these, a request is seen only when the user tells the AI to look at the workbench.

| Route | Client | How |
|---|---|---|
| Hooks (default) | Any client running the plugin's Stop and UserPromptSubmit hooks | Waiting requests are handed over when the AI is about to end its turn, or when the user next types |
| App-server (experimental) | Codex started from `%USERPROFILE%\.aspen-mcp\codex-aspen.cmd` | The request starts a turn in the conversation (or joins the running one), ending with its `note_id` |
| Channel (research preview, opt-in) | Claude Code started with the development channels flag | Each new or edited request is pushed as a `notifications/claude/channel` message naming the session, object and text, attributes `note_id`, `session`, `tab`, `target` (and `event`, `answer_to`, `proposal` where they apply). A request about a change, group, field or step adds a line "The user asks this about …" |

The hooks need nothing beyond the plugin and are the route to use by default.

**Channel (research preview, opt-in).** Claude Code channels are a research preview. To use them, the user sets `ASPEN_MCP_CHANNELS=1` and starts Claude Code with `--dangerously-load-development-channels plugin:aspen-plus@aspen-mcp`. That flag lets the named server, which is not on Claude Code's approved channel list, push messages into the conversation that the AI reads and acts on; Claude Code shows a warning to confirm. Pass it only for this plugin's server, and only when the user wants requests to arrive at once. A session held by Claude Code's background daemon drops pushes silently, so the channel works only in a foreground session the user started this way; stopping the daemon also ends its background sessions, so leave that decision to the user rather than handing them a command for it.

- A server registered by hand is named `server:<its name in .mcp.json>` instead of `plugin:...`; the server's own hint names the right one. `ASPEN_MCP_CHANNEL_SPEC` overrides it.
- Only one session should own the workbench at a time: each starts its own server.
- When the hint in an opening result says how the user connects Ask AI, tell them once.

A request's delivery is marked on it: `delivered` (pushed to a client known to deliver, handed by a hook, or read with `workbench_read`; then also `handed` or `read`), `pushed` (to a client that may drop it), `undelivered` (no client session yet, e.g. after a `/mcp` reconnect: pushed after the next tool call).

## A heat plan request

**Apply via AI…** on the heat plan card writes a request for the plan shown into the Ask AI box; the user sends it. To answer it:

1. Keep an undo point and move the session off it: `save_simulation(session, "<model> before heat integration <time>.bkp")`, then at once `save_simulation(session, "<model> heat integrated.bkp")`.
2. Look up how to build each match before changing anything ([HeatX](../../blocks/heatx.md) between two heaters; heat streams for a condenser or reboiler); ask when a match needs a stream split or the docs do not cover it.
3. Build it with the flowsheet tools, `layout_flowsheet`, `run_simulation`; run the tab's `pinch` again; reply with heating and cooling before and after and the snapshot's path.

Undo is opening the snapshot file.
