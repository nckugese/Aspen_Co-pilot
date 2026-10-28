# Installing Aspen Co-pilot

The full setup guide. The [README](README.md) has the short version.

**Contents:** [Requirements](#requirements) · [Install — Claude Code and Codex](#install--claude-code-and-codex) ·
[Updating](#updating) · [Install — other MCP clients](#install--other-mcp-clients) ·
[Ask AI: how requests reach the AI](#ask-ai-how-requests-reach-the-ai) ·
[Codex: the workbench as the one approval gate](#codex-the-workbench-as-the-one-approval-gate) ·
[Troubleshooting](#troubleshooting) · [Development](#development)

## Requirements

- **Windows** — Aspen Plus is Windows-only
- **Aspen Plus**, installed and licensed. This project does not include or distribute it;
  it drives your own installation over the COM API.
- **[uv](https://docs.astral.sh/uv/)** — fetches a matching Python and every dependency
  for you. You do not need to install Python yourself.

## Install — Claude Code and Codex

Every command below is a normal shell command that runs from any Windows shell — PowerShell,
cmd, or Git Bash — and none of them is a slash command. Each step states how to tell it
worked, so an agent can run the whole thing and check itself.

**Two steps cannot be done from inside a session** — installing uv changes `PATH` only for
processes started afterwards, and a client only picks up a newly installed plugin on
restart. Both are marked **HANDS OFF TO USER** below. An agent that reaches one must stop
and ask; there is no way to work around either from within the session, and continuing
past them produces a *Failed to connect* that looks like a broken install.

### 1. Check the prerequisites

```bash
powershell -NoProfile -Command "Get-ChildItem 'HKLM:\SOFTWARE\Classes' | Where-Object { $_.PSChildName -like 'Apwn.Document*' } | Select-Object -ExpandProperty PSChildName"
```

Expect `Apwn.Document` plus a versioned entry such as `Apwn.Document.41.0`. Nothing
returned means Aspen Plus is not installed or its COM registration is broken — stop, and
say so. This project cannot install or repair Aspen Plus.

### 2. Install uv

```bash
uvx --version
```

Check `uvx`, not `uv` — the client launches the server with a bare `uvx`, and that is the
name that has to resolve. If it prints a version, skip to step 3. Otherwise:

```bash
winget install --id=astral-sh.uv -e
```

> **HANDS OFF TO USER.** Ask the user to **open a new terminal**, and to restart the MCP
> client if it was already running. `winget` updates `PATH` only for processes started
> afterwards, so the current session — and the client that spawned it — still cannot
> resolve `uvx`. Continuing anyway makes the server fail to connect later, with an error
> that says nothing about `PATH`.

### 3. Install the plugin

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
```

```bash
claude plugin install aspen-plus@aspen-mcp
```

Expect `Successfully installed plugin: aspen-plus@aspen-mcp (scope: user)`. Confirm with
`claude plugin list`, which should show the entry with `Status: ✔ enabled`:

```
  ❯ aspen-plus@aspen-mcp
    Version: 1.0.0
    Scope: user
    Status: ✔ enabled
```

On Codex the equivalents are `codex plugin marketplace add nckugese/Aspen_Co-pilot`
and enabling **Aspen Plus** from `/plugins`. Codex then asks the user to trust the plugin's
hooks once in `/hooks`; say yes, or step 4 will not offer itself. Codex gets the
`aspen-doc` subagent from the second session on — see [Hooks on Codex](#hooks-on-codex).

> **HANDS OFF TO USER.** Ask the user to fully restart the client. A session that was
> already open when the plugin was installed does not pick up its MCP server, and
> `/aspen-doctor` will report the server as not connected even though it is healthy.

### 4. Say yes when it offers to finish setup

On the first session after the restart, the plugin notices that the environment has not
been set up for the version it pins, and asks whether to do it now. Say yes. It downloads
about 200 MB — Python, the server, and the optimizer libraries — and takes one to three
minutes, with progress on screen.

There is nothing to type. If you would rather run it yourself, it is a plain script:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File "<plugin>/scripts/install.ps1"
```

**Why this is a separate step rather than something the server does on startup.** An MCP
client gives a server roughly 60 seconds to answer its handshake. A cold 200 MB download
does not fit in that budget, and a server that misses it reports only *failed to connect* —
which says nothing about a download. Moving the download off the startup path is what makes
the failure impossible rather than merely unlikely. The same reasoning is why the pinned
version never changes on its own: see [Updating](#updating).

Once it finishes, restart the client one more time so the server starts from the warm cache.

### 5. Verify

In the restarted client, from **any folder**, run `/aspen-doctor`. It checks uv, the MCP
connection, Aspen COM registration, the docs and user-data roots, the optimizer extras, the
pinch backend, and whether setup matches the pinned version, then prints a pass/fail table.

`claude mcp list` is a good cross-check — the entry
`plugin:aspen-plus:aspen-plus` should read `✔ Connected`.

The plugin registers **globally** (`scope: user`) — it works in every folder, not just a
checkout of this repo. It bundles the MCP server, the documentation-lookup subagent, the
error-troubleshooting and knowledge-capture workflows, and the setup checker. See
[plugin/README.md](plugin/README.md) for what is inside.

### Install size and extras

To trade install size for the Bayesian optimizers, swap `[all]` for `[opt]` in the `uvx`
commands of [Install — other MCP clients](#install--other-mcp-clients). Extras are `opt` (derivative-free and gradient), `bo` (torch, botorch,
gpytorch) and `all`. On Windows the full set is about 200 MB — torch's Windows wheel is
~122 MB, not the multi-gigabyte CUDA build seen on Linux.

OpenPinch needs a newer interpreter than the server runs on, so `uv` provisions Python 3.14
for it on the first `pinch_analysis` call — that one call takes a few minutes, later calls
are immediate.

`aspen-mcp --check` reports version, docs root, which extras resolved, the pinch backend,
and the tool count. Run it whenever something looks wrong.

## Updating

**The version you install is the version you keep running.** `.mcp.json` pins an exact
release tag, so pushing to `main` does not change what anyone's server does. Nothing is
rebuilt behind your back, and nothing that worked yesterday breaks today because of a commit
you never asked for.

That matters most for published work: an optimization campaign that spans days and sessions
runs one server version throughout, and that version is a tag you can name in a methods
section. The plugin pins the server version only; third-party dependency versions (numpy,
pymoo, torch, …) resolve within their declared ranges when the environment is installed, so
record them too (`uv pip freeze` in the server's environment) if exact reproduction matters.

Updates are offered, never applied:

- At most once a day, in the background and off the session-start path, the plugin looks for
  a newer release tag. It never blocks a session on the network, and a failed check is
  silent — an update notifier that produces errors is worse than none.
- When a newer release exists, the plugin mentions it at a natural pause and asks. It will
  not interrupt work in progress for it.
- Decline, and it stops asking for that release.

To take an update:

```bash
claude plugin update aspen-plus@aspen-mcp
```

Then restart the client. The new version pins a new tag, so the next session offers to
finish setup exactly as it did on first install — the same path, not a special case.

## Install — other MCP clients

Skip this section if you use Claude Code or Codex with the plugin. Clients without a plugin
system register the server directly. Use the same `uvx` command
as below — there are no absolute paths to fill in, and nothing to `pip install`.

Run step 1 first regardless of client.

**These clients have no plugin system, so they get no setup prompt and no update check** —
both of those ship inside the plugin. Do the download by hand once, before pointing the
client at the server, or its first launch will time out:

```bash
uvx --from "aspen-mcp[all] @ git+https://github.com/nckugese/Aspen_Co-pilot@v1.0.0#subdirectory=aspen-mcp" aspen-mcp --check
```

It succeeds when the report looks like this (trimmed; your paths and counts differ):

```
aspen-mcp 1.0.0
python    3.11.9  (C:\Users\<you>\AppData\Local\uv\cache\...\python.exe)
docs      C:\Users\<you>\AppData\Local\uv\cache\...\aspen_mcp\docs
user data C:\Users\<you>\.aspen-mcp
docs index: ok
extra [opt]: installed
extra [bo]: installed
pinch     uv (provisions Python 3.14 + OpenPinch on first use)
journal   C:\Users\<you>\.aspen-mcp\journal (0 models, 0.0 MB, on, writable)
...
tools     52 registered, 52 classified (33 take reason)
```

Any line reading `absent`, `MISSING`, or `NONE` means the download did not finish. Re-run it
once; if the second run says the same, the cause is network or proxy and a third attempt
will not fix it.

Bump the tag in both the command above and the config below when you want a newer release —
on these clients that is a manual step.

### Claude Desktop

**Settings → Developer → Edit Config**, then fully quit and reopen the app (closing the
window is not enough).

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "aspen-plus": {
      "command": "uvx",
      "args": [
        "--from",
        "aspen-mcp[all] @ git+https://github.com/nckugese/Aspen_Co-pilot@v1.0.0#subdirectory=aspen-mcp",
        "aspen-mcp"
      ]
    }
  }
}
```

### Gemini CLI

Same JSON, in `~/.gemini/settings.json` (Windows: `%USERPROFILE%\.gemini\settings.json`)
for all projects, or `.gemini/settings.json` for one. Confirm with `/mcp`.

### Codex without the plugin

`~/.codex/config.toml` (Windows: `%USERPROFILE%\.codex\config.toml`):

```toml
[mcp_servers.aspen-plus]
command = "uvx"
args = ["--from", "aspen-mcp[all] @ git+https://github.com/nckugese/Aspen_Co-pilot@v1.0.0#subdirectory=aspen-mcp", "aspen-mcp"]
```

### Porting the workflow knowledge

The server sends a short set of operating rules to the client as MCP server instructions —
where the docs live, never guess Aspen paths, what each change's `reason` is for — and its
tool results say the rest when it matters: finish topology edits with `layout_flowsheet`,
follow the troubleshooting workflow when a run fails. **Every client gets both
automatically**, so the essentials work anywhere.

What a plugin-less client misses is the packaged extras in [plugin/](plugin/): the
`aspen-doc` subagent (keeps 570 KB of docs out of the main context) and the two skills.
Both are plain Markdown and port directly:

| From | Gemini CLI | Codex |
|---|---|---|
| `plugin/agents/aspen-doc.md` | `.gemini/agents/aspen-doc.md` (same MD+YAML; set a Gemini model) | `.codex/agents/aspen-doc.toml` — written for you by the Codex hook ([Hooks on Codex](#hooks-on-codex)) |
| `plugin/skills/*/SKILL.md` | body into `GEMINI.md`, or a subagent | copy as `SKILL.md` into a Codex skill dir |

**Adapt freely:** file format, model names, tool names.
**Copy VERBATIM (do not paraphrase):** the privacy rules in the troubleshooting skill — the
*"Strip before writing"* list and the `record_error` field table.

### Hooks on Codex

[plugin/hooks/hooks.json](plugin/hooks/hooks.json) runs two PowerShell scripts from
[plugin/scripts/](plugin/scripts/), on three events; both find the plugin from their own
location:

| Hook | Event | What it does |
|---|---|---|
| `session-start.ps1` | `SessionStart` | Tells the AI when setup has not been run for the pinned server version (and offers it), or when a newer release exists. Reads `.mcp.json` from the folder above `scripts/` and a local cache of the latest release. At most once a day it starts `check-update.ps1` in the background, which runs `git ls-remote --tags` against this repository to refresh that cache — the hooks' only network access. Writes `~/.aspen-mcp/aspen-workbench.cmd`; on Codex also `~/.aspen-mcp/codex-aspen.cmd` and `~/.codex/agents/aspen-doc.toml` (below). |
| `workbench-asks.ps1` | `Stop`, `UserPromptSubmit` | Hands the AI the Aspen Workbench's waiting **Ask AI** requests when the client cannot take them as they are sent (plain Codex, or Claude Code without channels): when the AI ends its turn, or when the user next types. Silent when none wait. |

**Codex with the plugin needs nothing ported.** Its manifest points at
[plugin/hooks/codex.json](plugin/hooks/codex.json) instead: the same scripts, run with
`-Client codex`, because Codex differs from Claude Code here (checked on Codex CLI 0.146):

| | Claude Code | Codex |
|---|---|---|
| Before a hook runs | nothing | the user reviews and trusts it once in `/hooks` (again after any change to it) |
| What reaches the AI from `SessionStart` | `systemMessage` | only `hookSpecificOutput.additionalContext` (or plain stdout) |
| Subagents in a plugin | bundled (`plugin/agents/`) | not supported ([openai/codex#18988](https://github.com/openai/codex/issues/18988)) |

A Codex plugin cannot bundle a subagent, so on Codex `session-start.ps1` builds
`~/.codex/agents/aspen-doc.toml` from `plugin/agents/aspen-doc.md` (the one copy of its
instructions) and rewrites it whenever that changes. Codex reads its agents before the hook
runs, so the subagent is there from the **second** session on; the first session is told to
read the docs directly. Removing the plugin leaves that file behind — delete it by hand.

**Ask AI reaching Codex at once.** Codex takes no message an MCP server pushes, so with plain
`codex` an Ask AI request from the workbench reaches the AI through the hooks above. To have
it arrive the moment it is sent, as with Claude Code's channels, start Codex with the
plugin's launcher instead:

```bat
%USERPROFILE%\.aspen-mcp\codex-aspen.cmd
```

It runs Codex's (experimental) app-server on a free loopback port and the usual Codex screen
on top of it; the workbench puts each request into the conversation as your message and the
AI answers at once. Arguments go on to Codex. The shortcut is written by the Codex
SessionStart hook, so it exists after the first Codex session with the plugin. Details:
[docs/mcp/workbench/requests.md](aspen-mcp/docs/mcp/workbench/requests.md#how-requests-reach-the-ai).

**Codex without the plugin:** copy `plugin/scripts/`, `plugin/agents/` and
`plugin/.mcp.json` into one folder, keeping that layout (the scripts expect `.mcp.json` and
`agents/` one level above them; make the pin in `.mcp.json` match your `config.toml`). Put
the hooks in `~/.codex/hooks.json` (`%USERPROFILE%\.codex\hooks.json`) with absolute paths
and `-Client codex`, and trust them in `/hooks`:

```json
{
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "timeout": 10,
      "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:/aspen-hooks/scripts/session-start.ps1\" -Client codex"}]}],
    "Stop": [{"hooks": [{"type": "command", "timeout": 15,
      "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:/aspen-hooks/scripts/workbench-asks.ps1\" -Event stop -Client codex"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "timeout": 15,
      "command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:/aspen-hooks/scripts/workbench-asks.ps1\" -Event prompt -Client codex"}]}]
  }
}
```

The hooks are conveniences, not requirements: without them the server and the workbench
work the same, but setup has to be run by hand (step 4), no update is offered, and Ask AI
requests wait until the AI is next asked to look.

## Ask AI: how requests reach the AI

| Client | Start it with | Ask AI reaches the AI |
|---|---|---|
| Claude Code (default) | `claude` | when the AI ends its current turn, or when you next type (through the plugin's hooks) |
| Claude Code (research preview, opt-in) | channels — see [requests.md](aspen-mcp/docs/mcp/workbench/requests.md#how-requests-reach-the-ai) for what it takes and what the development-channels flag allows | at once |
| Codex (default) | `codex` | when the AI ends its current turn, or when you next type |
| Codex (experimental) | `%USERPROFILE%\.aspen-mcp\codex-aspen.cmd` | at once (Codex's app-server; see [Hooks on Codex](#hooks-on-codex)) |

## Codex: the workbench as the one approval gate

You can let the workbench be the one approval gate — otherwise Codex asks before
every Aspen tool call on top of the workbench's own review. **Only do this if you keep the
workbench window open with review mode on whenever Codex works on a model**: the setting
turns off Codex's own prompt for every Aspen tool, so with the window closed or review off,
the AI's changes reach Aspen with no one asked. Add to `~/.codex/config.toml`:

```toml
[plugins."aspen-plus@aspen-mcp".mcp_servers.aspen-plus]
default_tools_approval_mode = "approve"
```

Use exactly that table: a `[mcp_servers.aspen-plus]` table for a plugin's server stops
Codex's config from loading. Remove the line again when you work without the workbench. Full reference: [aspen-mcp/docs/mcp/workbench/index.md](aspen-mcp/docs/mcp/workbench/index.md).

## Troubleshooting

- Run `/aspen-doctor` in Claude Code or Codex: it checks uv, the server connection, Aspen's
  COM registration, the docs, the optimizer extras and the pinch backend, and prints a
  pass/fail table.
- Outside a plugin client, run `aspen-mcp --check` (the `uvx` command in
  [Install — other MCP clients](#install--other-mcp-clients)).
- *Failed to connect* right after installing usually means the client was not restarted after
  uv or the plugin was installed (steps 2 and 3), or setup (step 4) has not finished.
- The server log is `~/.aspen-mcp/aspen_mcp.log`. For anything else, open an issue at
  <https://github.com/nckugese/Aspen_Co-pilot/issues>.

## Development

```bash
pip install -r aspen-mcp/requirements.txt
python aspen-mcp/server.py
```

The repo root doubles as a plugin marketplace via
[.claude-plugin/marketplace.json](.claude-plugin/marketplace.json).
`claude plugin marketplace add ./` installs the plugin files from your working copy — skills,
the subagent, hooks — but its `.mcp.json` still runs the **pinned release tag** of the
server, not your checkout. To try server changes, register the checkout as a separate MCP
server under its own name, for example in a project `.mcp.json`:

```json
{
  "mcpServers": {
    "aspen-plus-src": {
      "command": "C:/path/to/checkout/aspen-mcp/.venv/Scripts/python.exe",
      "args": ["C:/path/to/checkout/aspen-mcp/server.py"]
    }
  }
}
```

Disable the plugin's `aspen-plus` server while you do, so the AI does not see two copies of
every tool. `aspen-mcp --check` (or `python aspen-mcp/_entry.py --check`) prints the version,
the docs and user-data roots and the tool count.

The pages under `aspen-mcp/docs/blocks/` are generated: report a correction as an issue rather
than editing them.
