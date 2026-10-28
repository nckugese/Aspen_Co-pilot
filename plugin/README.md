# Aspen Plus plugin

Bundles everything an agent needs to drive Aspen Plus into one installable unit: the MCP
server, the documentation-lookup subagent, the error-troubleshooting and knowledge-capture
workflows, the process-building workflow, and a setup checker.

Works in **Claude Code** and **Codex / ChatGPT**, from the same directory — the two
ecosystems read different manifests (`.claude-plugin/plugin.json` and
`.codex-plugin/plugin.json`) but share `.mcp.json`, `skills/`, the hook scripts and the marketplace entry.

## Install

Prerequisites: Windows, and a licensed Aspen Plus installation.

**1. Install uv** (once per machine):

```bash
winget install --id=astral-sh.uv -e
```

> **Open a new terminal after installing uv**, and restart your MCP client if it was
> already running. Installing uv updates `PATH` only for processes started afterwards, so
> anything already open still cannot find `uvx` and the server reports
> *Failed to connect*.

**2. Add the marketplace and install:**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
```

```bash
claude plugin install aspen-plus@aspen-mcp
```

On Codex, run `codex plugin marketplace add nckugese/Aspen_Co-pilot` instead,
then enable **Aspen Plus** from `/plugins`.

**3. Restart the client, and say yes when it offers to finish setup.** The first session
after the restart notices the environment is not set up for the pinned version and asks.
That step downloads ~200 MB and takes one to three minutes, with progress on screen.

It is deliberately not done at server startup: MCP clients allow a server roughly 60
seconds to answer its handshake, which a cold download does not fit, and the resulting
*failed to connect* says nothing about a download. The script behind the prompt is
`scripts/install.ps1` and can be run by hand instead.

**4. Run `/aspen-doctor`** from any folder to confirm the wiring.

The repo's [INSTALL.md](../INSTALL.md) carries the step-by-step version, including what to verify after each
command and the two points that have to be handed back to a human.

## Contents

| Path | Purpose |
|---|---|
| `.mcp.json` | Launches the `aspen-plus` MCP server via `uvx`, pinned to a release tag |
| `hooks/hooks.json` | SessionStart (offers setup, surfaces an available update), Stop and UserPromptSubmit (hand over waiting Ask AI requests) |
| `hooks/codex.json` | Codex's copy: the same scripts with `-Client codex`; also installs `aspen-doc` into `~/.codex/agents` (Codex plugins cannot bundle subagents) |
| `scripts/session-start.ps1` | The SessionStart body. Reads local state and never blocks; writes `~/.aspen-mcp/aspen-workbench.cmd` (on Codex also `~/.aspen-mcp/codex-aspen.cmd` and `~/.codex/agents/aspen-doc.toml`); starts `check-update.ps1` in the background at most once a day |
| `scripts/check-update.ps1` | Background release check (≤ 1/day, `git ls-remote --tags` against this repository — the hooks' only network access), and the "don't ask again" record |
| `scripts/workbench-asks.ps1` | Stop / UserPromptSubmit: hands the AI the workbench's waiting Ask AI requests when the client takes no pushed message |
| `scripts/aspen-workbench.ps1` | Opens the workbench with no AI client (`~/.aspen-mcp/aspen-workbench.cmd`) |
| `scripts/codex-workbench.ps1` | Starts Codex on its app-server so Ask AI reaches it at once (`~/.aspen-mcp/codex-aspen.cmd`) |
| `scripts/install.ps1` | One-time environment setup for the pinned version. Idempotent |
| `scripts/_state.ps1` | Shared read/merge/write for `~/.aspen-mcp/setup-state.json` |
| `.claude-plugin/plugin.json` | Claude Code manifest |
| `.codex-plugin/plugin.json` | Codex manifest (adds the directory `interface` block) |
| `agents/aspen-doc.md` | Doc-lookup subagent — keeps 570 KB of docs out of the main context |
| `skills/aspen-process-workflow/` | Building or changing a process, in the workbench or the conversation |
| `skills/aspen-error-troubleshooting/` | Simulation error diagnose → fix → record |
| `skills/observation-knowledge-extraction/` | Turn a GUI demonstration into reusable docs |
| `skills/aspen-doctor/` | `/aspen-doctor` setup checker |

The docs themselves are **not** in this directory — they ship inside the `aspen-mcp`
Python package, and the server announces their absolute location to the client as
`ASPEN_DOCS_ROOT`. That keeps one copy in the repo and makes lookups independent of the
user's working directory.

## Two roots, one writable

| Root | Contents | Writable |
|---|---|---|
| `ASPEN_DOCS_ROOT` | Docs shipped with the server | No — replaced on upgrade |
| `ASPEN_USER_DATA` (`~/.aspen-mcp/`) | This machine's error history and learned recipes | Yes |

Agents read from both and write only to the second. Anything written into the installed
plugin or package directory is lost the next time it is upgraded.

## What works out of the box

`.mcp.json` installs `aspen-mcp[all]`, so everything is available once setup has finished
(step 3):

- Flowsheet construction, simulation, and results
- All nine optimizers — NSGA-II/III, PSO, DE, gradient, grid search, BO, CBO, AFM-CBO —
  behind one `optimize` tool
- Pinch analysis. `uv` provisions Python 3.14 and OpenPinch on the first
  `pinch_analysis` call (OpenPinch needs a newer interpreter than the server runs on), so
  that one call takes a few minutes; later calls are immediate.

The package defines three extras: `opt` (derivative-free and gradient), `bo` (Bayesian —
torch, botorch, gpytorch), and `all`. On Windows the whole set is about 200 MB — torch's
Windows wheel is ~122 MB, not the multi-gigabyte CUDA build seen on Linux. To trade
install size for the BO family, swap `[all]` for `[opt]` in `.mcp.json`.

## Verifying

`/aspen-doctor` is the normal route. It checks uv, the MCP connection, Aspen COM
registration, the docs roots, the optimizer extras, the pinch backend, and whether setup
matches the pinned version.

Underneath, `aspen-mcp --check` prints a report — version, docs root, which extras
resolved, the pinch backend, and the registered tool count — then exits without serving.
Re-running setup runs exactly that against the pinned version, and is safe at any time:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File "<plugin>/scripts/install.ps1"
```

Prefer that over a hand-written `uvx --from ...` line, which can silently inspect a
different environment than the one the client actually launches.

## Developing

The plugin is consumed from the repo root's `.claude-plugin/marketplace.json`, which
points at `./plugin`. To test plugin changes (skills, subagent, hooks) without publishing,
add the local checkout as a marketplace:

```bash
claude plugin marketplace add ./
```

That installs the plugin files from your checkout, but `.mcp.json` still runs the
**pinned release tag** of the server. To test server changes, register the checkout as its
own MCP server under a different name and disable the plugin's `aspen-plus` server meanwhile:

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
