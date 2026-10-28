# Aspen Co-pilot

**English** · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Русский](README.ru.md)

**Let an AI agent design, simulate and optimize chemical processes in your own Aspen Plus —
while you see every step and stay in charge.**

Aspen Co-pilot connects Aspen Plus to AI agents such as Claude Code and Codex through the
Model Context Protocol (MCP). You describe the process in plain language; the agent does the
work in Aspen, and you review it.

Windows only. You need your own licensed Aspen Plus; this project does not include it.
Developed by NCKU GESE Lab.

## What it can do

**Build and change processes.** Create a flowsheet from a description — components, property
methods, reactions, unit operations and streams — set and adjust any parameter, run the
simulation and read the results. Most Aspen Plus functions are available.

**Go from literature to a working model.** With your AI client's research tools, the agent can
gather kinetics, operating conditions and process routes from papers and patents, then build
them into an Aspen model you can check against the sources.

**Find out why a run fails.** It checks what Aspen still needs before a run, explains failed
runs and warnings, and fixes them. Fixes that worked are kept on your machine for next time.

**Optimize the process.** Nine algorithms behind one tool — NSGA-II, NSGA-III, PSO, DE/GDE3,
gradient (SLSQP), grid search and three Bayesian methods (BO, CBO, AFM-CBO) — for single- or
multi-objective problems with constraints, plus pinch analysis and heat-exchanger match
suggestions for heat integration.

**Look things up instead of guessing.** A reference for every block, stream and setting
([aspen-mcp/docs](aspen-mcp/docs/aspen.md)) that the agent consults before it changes a field.

## Built for working with people

An LLM agent that operates software on its own is hard to trust: you cannot see what it
changed or why, or stop a mistake before it reaches the model. Aspen Co-pilot closes that gap
with the **Aspen Workbench**, a desktop window beside Aspen Plus.

- **See what the AI does.** The flowsheet, the results and every change the AI made, with its
  reason, update live. Undo any change, or go back to a restore point.
- **Stay in control.** In review mode the AI's changes wait for your approval; larger changes
  arrive as proposals that only you can run.
- **Define the work yourself with block programs.** Assemble parameter sweeps, calculations,
  tables, charts and optimization studies — your own variables, objectives and constraints —
  from drag-and-drop blocks, with no code. The AI can write a program for you to edit, or run
  yours.
- **Work together.** Click any stream or block and **Ask AI** about it. In learning mode the AI
  explains the process principle behind each change.

The workbench has English and Chinese interfaces, and it also runs without an AI client
(`%USERPROFILE%\.aspen-mcp\aspen-workbench.cmd`: no network, no tokens).

## Install

You need **Windows**, a licensed **Aspen Plus**, and **[uv](https://docs.astral.sh/uv/)**
(`winget install --id=astral-sh.uv -e`; it brings its own Python).

**Claude Code:**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
claude plugin install aspen-plus@aspen-mcp
```

**Codex:** `codex plugin marketplace add nckugese/Aspen_Co-pilot`, then enable **Aspen Plus** in
`/plugins` and trust its hooks in `/hooks`.

Then restart the client. In the first session it offers to finish setup (about 200 MB: Python,
the server and the optimizer libraries); say yes, and restart once more. `/aspen-doctor`
checks the result.

The plugin pins one release, so nothing changes until you update it
(`claude plugin update aspen-plus@aspen-mcp`); it tells you when a newer release exists.

Other MCP clients (Claude Desktop, Gemini CLI, Codex without the plugin), the step-by-step
version with checks, and troubleshooting: **[INSTALL.md](INSTALL.md)**.

## Privacy

Everything the server keeps stays on your machine, under `~/.aspen-mcp/`: its log, the change
journal, restore points (copies of your models) and your error history. Your models, results
and conversation are never sent anywhere by this project. The only network access is:

- the plugin's update check, at most once a day (`git ls-remote` against this repository);
- the first `pinch_analysis` call, which downloads Python 3.14 and OpenPinch through uv;
- installing and updating, which fetch the server and its dependencies through uv.

What your AI client sends to its own provider is governed by that client.

## Feedback

Questions and bug reports: [GitHub Issues](https://github.com/nckugese/Aspen_Co-pilot/issues). Security reports: [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 NCKU GESE Lab.

If you use this software in academic work, please cite this repository.

## Disclaimer

Aspen Plus® and AspenTech® are trademarks of Aspen Technology, Inc. This project is an
independent, unofficial integration and is not affiliated with, endorsed by, or sponsored
by Aspen Technology, Inc. It does not include or distribute Aspen Plus; it controls a
separate, user-provided installation, and you need your own valid Aspen Plus license.
