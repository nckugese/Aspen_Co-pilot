# Security Policy

## Supported versions

Only the latest release (the newest `vX.Y.Z` tag) receives fixes. Update the plugin
(`claude plugin update aspen-plus@aspen-mcp`) before reporting, and say which version you ran.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately, either:

- through GitHub's private vulnerability reporting on
  [nckugese/Aspen_Co-pilot](https://github.com/nckugese/Aspen_Co-pilot/security/advisories/new), or
- by email to nckugese@gmail.com.

Include what you ran, what happened, and how to reproduce it. We aim to acknowledge a report
within a week and will tell you when a fix is released.

## Scope

**The MCP server** drives the user's own installed and licensed Aspen Plus through its COM API,
on the same machine, with the user's permissions. It opens, changes, runs and saves the models
an AI client asks it to. It writes only under `~/.aspen-mcp/` and to model files in the paths it
is given.
The workbench window runs locally, on the same machine.
Reports about what an AI client chooses to do with these tools are in scope when the server
fails to apply its own safeguards (review mode, learning mode, "Not applied" refusals).

**The plugin hooks** run PowerShell scripts with `-NoProfile -ExecutionPolicy Bypass`, so they
run regardless of the machine's script policy. They are:

| Script | Runs on | What it does |
|---|---|---|
| `session-start.ps1` | SessionStart | Reads `plugin/.mcp.json` and `~/.aspen-mcp/setup-state.json`; tells the AI whether setup or an update is due; writes `~/.aspen-mcp/aspen-workbench.cmd` (on Codex also `~/.aspen-mcp/codex-aspen.cmd` and `~/.codex/agents/aspen-doc.toml`); at most once a day starts `check-update.ps1` in the background. |
| `check-update.ps1` | started by the above | Runs `git ls-remote --tags` against this repository and records the newest release tag in `~/.aspen-mcp/setup-state.json`. The hooks' only network access. |
| `workbench-asks.ps1` | Stop, UserPromptSubmit | Reads the workbench's waiting Ask AI requests under `~/.aspen-mcp/workbench/` and hands them to the AI; writes `asks-handed.json` and `ai_turn.json` there. |
| `install.ps1` | when the user accepts setup | Runs `uvx` to download the pinned server version and its dependencies, then `aspen-mcp --check`. |

The shortcuts the hooks write start `aspen-workbench.ps1` (the workbench without an AI client)
and `codex-workbench.ps1` (Codex on a local app-server) only when the user runs them.

**Out of scope:** vulnerabilities in Aspen Plus itself, in the AI clients, or in third-party
packages (report those upstream), and anything that requires an attacker who can already write
to the user's profile.
