# Review, learning mode and one writer

What the workbench does to the AI's tool calls before any COM. Reads and dry runs always pass. A result that starts "Not applied" changed nothing: read why, do not retry it in a loop, and end the turn when it says the user must act.

## Review modes

The user picks the mode in the window's review menu (the shield).

| Mode | Code | The AI's changing calls |
|---|---|---|
| Read-only | `observe` | Refused: propose the change as a [proposal](proposals.md) instead |
| Approve risky | `risk` (default) | Risky calls wait for the user's approval in the window; the rest apply |
| Auto-apply | `auto` | All apply, all recorded |

Risky calls: the eight `remove_*` tools (block, stream, component, element, reaction, reaction set, row, side duty), `reinit_simulation`, `create_new_simulation`; `save_simulation` onto an existing file other than the model's own (or its `.apw` / `.def`); a real `workbench_run` whose program removes something or saves over another file. `remove_row` of a row the AI inserted itself in this server process asks nothing. `layout_flowsheet`, `create_chemistry`, `disconnect_stream` and `close_aspen_plus` never ask (closing takes a restore point first when the model has unsaved changes).

- **Pause**: the user pauses the AI; changing calls are held. An automatic pause comes when the AI looks stuck (only its own changes count): failed runs in a row (3; 2 to 10), one field changed in a request with no successful run (4; 3 to 20), its own changes reverted (2; 1 to 10). Each rule can be turned off. A pause stops no calculation, optimization or program already running.
- A held or waiting call is held at most 40 s for Claude Code and Codex, 25 s for other clients (`ASPEN_MCP_HOLD_S` overrides). Nothing is applied inside a call more than 55 s (35 s for other clients) after it came in: an approval after that is applied right after the answer ("Not applied yet #12: the user approved …"), and a later result confirms it.
- "Not applied" says why: read-only, paused (end the turn), paused automatically (diagnose first), an approval still waiting (it stays open: do not call again), declined (with the user's note: do not retry), the window closed or the request expired, a repeat of a waiting call, or the model changed while it waited (the changes listed).
- Review acts only while this server serves the open window (`~/.aspen-mcp/workbench/owner.json` names it). Window closed, or served by another process (the standalone workbench or another AI client's server): calls apply as in Auto-apply, still recorded. `ASPEN_MCP_BRAKE=0` turns review off.
- A server restart keeps the mode, a pause and the rules; open approval requests expire.
- `workbench_read` `brake`: the mode, `live`, the pause (with `why` when automatic), the latest 5 approval requests with status and the user's comment, the auto-pause thresholds.

Client permissions: only while the window is open with review on is the workbench a gate at all, so only then may the client run this server's tools without its own prompt. With the window closed, review off, or `ASPEN_MCP_BRAKE=0`, calls apply with no one asked, so keep the client's own prompt. Codex `exec` cancels a call it would have to ask about; if the user works with the window open and review on, they may give this server `default_tools_approval_mode = "approve"`, and should remove it when they work without the workbench. For the plugin's server that table is `[plugins."aspen-plus@aspen-mcp".mcp_servers.aspen-plus]`; a server added to `config.toml` by hand keeps `[mcp_servers.<name>]`.

## Learning mode

On by default; the user switches it in the window. While it is on, every changing call the AI makes (tools of kind value, structure or batch: `set_value`, `place_block`, `connect_stream`, `optimize`, a real `workbench_run`, …; not runs, files, reads or dry runs) needs a `reason` that explains the process principle behind it.

- No `reason`: refused.
- A weak one (fewer than 8 words or 12 CJK characters counted together, no cause-and-effect word, or only "as the user asked"): refused once per tool and target in 120 s; the next attempt applies, its records marked `reason_weak`.
- A refusal starts "Not applied … learning mode" and says what to add; it is recorded `refused` with `learn`.
- `workbench_edit` is not refused; its answer lists the changing steps without `why`.
- `workbench_read` carries `"learning": true`; the AI hears of a switch at the top of its next result.
- Flag file `~/.aspen-mcp/workbench/learn.json` `{v, on, since, by, weak?}`, read by the standalone workbench and an AI client's server, and in force with the window closed; no file or no `on` means on.
- `ASPEN_MCP_LEARN_WEAK=remind`: a weak reason gets a reminder instead of a refusal. `ASPEN_MCP_LEARN=0`: nothing enforced.

## One writer at a time

While a program runs on a session, or the AI's `optimize` does, the window's own changes (a typed value, Run, Save, applying a point) are refused, and another program waits in the queue. The AI's changing calls wait up to 10 s, then are refused, recorded as `refused`:

```
Not applied: session 'bio' is being changed by the workbench program on tab 'Reflux sweep' (running 2 min 5 s). Reads still work. Wait for it (workbench_read shows its status), or ask the user to stop it.
```

- `workbench_run` refuses at once when the tab's session is busy with another tab.
- A paused or waiting run keeps the session: the AI's changes are refused, naming the step it waits at.
- `close_aspen_plus` without a session waits on every session.
