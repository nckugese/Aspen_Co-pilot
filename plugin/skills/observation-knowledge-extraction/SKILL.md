---
name: observation-knowledge-extraction
description: Use when building or modifying an Aspen Plus process and you hit a feature, unit-operation, or setting you don't know how to configure — i.e. progressive disclosure (the aspen-doc agent / docs) turned up nothing for it ("you don't know what you don't know"). Observe a user's GUI demonstration with snapshot_tree/diff_snapshot, reproduce it to verify you understood, then record it as reusable docs so the gap is filled next time. Do NOT use for already-documented features (just read the doc) or for run-time errors (use aspen-error-troubleshooting).
version: 1.0.0
---

# Observational Knowledge Extraction

Turns a user's GUI demonstration of an unfamiliar Aspen feature into reusable, retrievable
knowledge — the "demonstration → extract → retrieve" loop. Sibling of the
`aspen-error-troubleshooting` skill (that one learns from fixing errors; this one learns
from observing setups).

## When to use

Activate when, while building/editing a flowsheet, you cannot find HOW to configure
something and the `aspen-doc` agent / the docs have no entry for it (an unfamiliar unit op,
table, reaction type, analysis tool, ...). Do NOT activate for features already documented
(read the doc instead) or for `run_simulation` errors (use `aspen-error-troubleshooting`).

## Where knowledge lives

- `<ASPEN_DOCS_ROOT>` — read-only docs shipped inside the installed `aspen-plus` MCP
  server. Its absolute path is announced in the server's MCP instructions as an
  `ASPEN_DOCS_ROOT: <path>` line. Never guess a relative `aspen-mcp/docs/`.
- `<ASPEN_USER_DATA>` — this machine's writable knowledge, at `~/.aspen-mcp/`
  (`%USERPROFILE%\.aspen-mcp\` on Windows). Everything **you** learn is written here.
  A plugin upgrade replaces the installed directory wholesale, so anything written into
  `<ASPEN_DOCS_ROOT>` is silently lost.

Read from both; write only to `<ASPEN_USER_DATA>`.

## Tools

- `snapshot_tree(session, root_path, input_only=True, count_only=False)` — capture a region
  server-side. Per node it records value, unit, **recordtype** (the object type, e.g. an
  `LHHW` reaction set), and key attributes; every node is recorded so the diff sees added /
  removed nodes too. Returns only an id + node count (the tree never enters your context).
- `diff_snapshot(session, id_before, id_after)` — the delta: changed / added / removed nodes.
  Only this small result reaches you — it is exactly what the demonstration changed.
- Construction tools for the reproduce step: see
  `<ASPEN_DOCS_ROOT>/mcp/elements.md`.

## Workflow

### 1. Detect the gap
You're building a process and need a feature you can't find in the docs (aspen-doc returns
nothing). State the unknown explicitly: "I don't know how to configure X."

### 2. Demonstration or self-attempt
Ask the user to demonstrate it in the Aspen GUI. If they can't, attempt it yourself from
partial knowledge — either way you will snapshot around the change.

### 3. Snapshot BEFORE — frame the root
Pick the smallest region that will contain the change:
- a block: `\Data\Blocks\<B>` (or `\Data\Blocks\<B>\Input`)
- reactions: `\Data\Reactions\Reactions`
- analysis: `\Data\Model Analysis Tools\Sensitivity`
Unsure of size? probe with `count_only=True` and narrow if it warns it's large. Keep
`input_only=True`. Take the snapshot → note `id_before`.

### 4. Demonstrate → Snapshot AFTER → diff
After the demonstration, snapshot again (`id_after`) and call
`diff_snapshot(id_before, id_after)`. Read the delta: the object **recordtype** (what kind
of thing it is), the changed/added paths + values (including string-keyed component
entries, e.g. `COEF\1\C MIXED`), with units.

### 5. Reproduce to verify — close the loop
Recreate the same setup (fresh blank sim, or the working file) using
`<ASPEN_DOCS_ROOT>/mcp/elements.md`:
map each delta line to a tool —
- existing scalar / string-keyed **value** → `set_value` (string-keyed: use the literal diff path),
- object **type** → given when it is created: `add_element(folder, "NAME!TYPE")` or the
  object's own tool (`add_reaction_set(type=...)`),
- a **new row / element / object** (set_value says `Node not found`) → create it first
  (`insert_row` / `add_element` / `add_reaction_set`), then fill,
- reactions / sensitivity → the create-then-fill recipes in `reactions/reactions.md`,
  `flowsheeting/flowsheeting.md` (define and vary rows) and `analysis/sensitivity.md`.

Then snapshot your reproduction and `diff_snapshot` it **against the demonstrated snapshot**.
Iterate until only cosmetic differences remain (`userentered` flags, internal `CC Nodes`).
This proves you learned both the WHAT (values) and the HOW (construction steps).

### 6. Write it into the knowledge base
Summarize the user's **intent** + the verified recipe as a natural-language note:
- **New unit op / feature** → create `<ASPEN_USER_DATA>/learned/<feature>.md` and add a line
  to `<ASPEN_USER_DATA>/learned/index.md` (create both if absent).
- **Known block, new detail** → append a section to `<ASPEN_USER_DATA>/blocks/<type>.md`,
  starting the file with a one-line pointer back to `<ASPEN_DOCS_ROOT>/blocks/<type>.md` so
  the shipped doc and your addition read as one.
Record: what it is (recordtype), the exact input paths + values (with units, copied literally
from the diff), the construction order, and any create-then-fill gotchas.

### 7. Done — gap filled
The feature is now retrievable by progressive disclosure (the `aspen-doc` agent) next time —
it searches `<ASPEN_USER_DATA>` alongside `<ASPEN_DOCS_ROOT>`. The loop is closed.

If the recipe is generally useful (not specific to this plant), consider opening a PR
against `aspen-mcp/docs/` so the next release ships it to everyone.

## Scoping & token notes
- The full snapshot stays server-side; only the diff reaches you. Frame `root_path` tightly;
  use `count_only` to probe before a large walk.
- `input_only=True` skips the Output (results) branch, so the diff is the deliberate inputs.
- Snapshots are in-memory and cleared on MCP server restart — re-snapshot if that happens.

## Knowledge-write rules
- Hybrid storage: new feature → `<ASPEN_USER_DATA>/learned/`; known block →
  `<ASPEN_USER_DATA>/blocks/`. Always update the relevant index so progressive disclosure
  can find it.
- Pair the mechanical diff (the WHAT) with the user's intent (the WHY) — knowledge needs both;
  the diff alone records state, not purpose.
