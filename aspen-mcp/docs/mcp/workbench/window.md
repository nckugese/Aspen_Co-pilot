# The window

What the user sees, so the AI can say where to click. A control for a part the server can be without shows only when the server lists it (`catalog.features`, [files.md](files.md#features)).

## Layout

| Area | Holds |
|---|---|
| Header | The logo (Help: beginner tour -- by itself once for a new viewer, and once with only the steps added since for one who dismissed an older version -- flowsheet legend, keyboard shortcuts); one tab per model; the model capsule; **Save model**; **Run simulation** with ▾ (**Reinitialize, then run**; in learning mode **Predict, then run…**); the AI pill (what the AI is doing now, ⏸ pauses it); **AI is thinking…** and its seconds while the AI's turn runs; the review shield; the connection state when not normal; **⋯** (Model, Block program files, View with **English** / **中文**, Tracking and learning, Help) |
| Model capsule | The model's file and what Aspen last said of it: Aspen calculating, Not open, Calculating, Program running, Input incomplete · N, Input changed, Errors · N, Warnings · N; a green dot for results available, grey for none; **Unsaved · N**. A click opens the model panel: file and path, unsaved changes, state, the last run, blocks with errors or warnings, **Run diagnosis**, **Missing inputs**, **Model objects**, restore points, and the actions (Run simulation, Reinitialize then run, Save model, Save model as…, Create restore point…, Reload the flowsheet from Aspen) |
| **+** beside the model tabs | A tab on a model open in Aspen; **Open Aspen model…** (a `.bkp` picked there is opened by the server that serves the window, with no AI needed -- one Aspen already has open is taken as it is; a file not opened is said in a toast); **Open .awb as new tab…** |
| Sub-tab row | **My program** (the model tab's own program), the model's other programs, **+** (**New program**), the AI's proposals in progress (✦), proposals reopened from History, and **History n** at the right end |
| Program column (left) | The run bar (↶ / ↷ for program versions, the AI's edits included; **Check program**, **Run program**, **Step**, **Stop** while running; ⋯ with Fit, save as `.awb`, replace from `.awb`) and the block editor. A proposal shows its card here instead ([proposals.md](proposals.md)) |
| Flowsheet (right) | The drawing; layers **Values**, **Flow**, **Heat plans**, **Annotations**; the zoom; **⋯** (Layout, Show as boxes, Legend, Export SVG…); the inspector floating at its right |
| Dock (bottom) | **AI chat**, **Changes**, **Run log**, **Tables & charts**, and the Ask AI box under them |
| AI chat's waiting line | Under the newest request still waiting, or at the chat's end: **AI is thinking…** with the header's seconds (one state, shown in both places together), else **Sent** with the seconds since sending, or what to tell the AI in the client when the request did not reach it; after 8 s, **Play while waiting** opens a small game under the chat (Catch the reflux, Baffles, Hold the setpoint, Cut point; ↻ the next; Esc closes; the best score kept) |

Edits made in the window, Aspen's own window or by the AI all show in **Changes** ([changes.md](changes.md)).

## Block editor

Categories: Change & run, Stream & block values, Studies (sweep and design spec), Optimize, Heat integration, Flowsheet changes, Tables & charts, Advanced (branches, loops, calculations, procedures, the start block, the group heading). Manual step is the last block of Change & run.

- Stacks not under the start block or a procedure are loose: faded, not run, counted by Run and Check; a version keeps them.
- An input slot (set, sweep, design spec, decision variable) takes inputs only; a result dropped there does not snap in. Read, if, table columns and objectives take both. Input path blocks are purple, result path blocks slate.
- A step's `why` shows under the block in learning mode, else in its tooltip; the right-click menu edits it, and **Turn this step off** writes `"off": true`.
- A statement kind the page does not know shows as a grey block and is sent back unchanged.
- A place step's type menu lists the block types by Aspen's model palette tab (`catalog.palette`), the most used tab first (Exchangers, Mixers/Splitters, Separators, Columns, Reactors, Pressure Changers, then the rest); a tab's name is a heading, not a choice (Chinese window: Aspen's English with our Chinese beside it). Types of the port table no docs tab lists come last, after a line.
- The streams and blocks menus list the fields of each type's general docs file (`docs/streams/streams.md`, `docs/blocks/<type>.md`: every block type with one), a field with an `{id}` segment other than a stream's component left out; any other path is a raw path block.

**Model objects** in the model panel: what is set outside the flowsheet, a line per group of Aspen's navigation pane (Setup, Components, Properties, Reactions, Convergence, Flowsheeting Options, Model Analysis Tools), each object a capsule with an amber dot where Aspen marks it incomplete. A click opens it in the inspector. Read when the panel opens; a Sensitivity folder after a run is one capsule with its count until clicked (listing its objects makes Aspen load their cases).

## Inspector

A click on a stream or block -- or a model object in the model panel, or a missing item's **Open** -- opens it over the flowsheet, out to its left edge (dragged narrower, it keeps that width; a double-click on the edge, the widest again; while the missing inputs or the diagnosis card shows, it leaves them room): the rows of its type's general docs file that Aspen has, with values and units, coming as they are read (about 20 ms of reads a pass; a stream with a hundred component rows never holds the window up). It reads like Aspen's form: a line under the head says **Inputs complete**, or what is missing (**2 missing: Pressure, Temperature**, each name going to its field, its section opened); the inputs come under Aspen's sheets in Aspen's order (Aspen V15: the sheets of the forms the general docs file names; else the docs' tables), each a line with the docs' rows of its table, the first open and the others shut as the user leaves them for that type; a sheet the docs have no rows of is read when opened, one they have rows of reads its other fields on **All fields on this sheet**; a missing field no table holds under **Inputs**; then **More Aspen forms** (Aspen V15: the other forms and the subobjects, open where one is incomplete); the **Results** apart -- beside the inputs where the inspector is wide, under them else -- one line until a run. An input is a box to type in, its unit beside it (typing in place, the box, the unit menu and ✓ share the row); a value Aspen takes from a list -- an option, the phases, a component or stream of the model -- is a menu of what each value means (**Pressure & duty** for `PD`, **Vapor-Liquid** for `2`, the code in its tooltip; from the docs' codes and the descriptions of the user's Aspen, else our own words), never typed; one the current settings do not use is greyed in its place, its box empty, and cannot be changed there: one Aspen refuses (HAP_ENTERABLE 0: RadFrac's operating specs not chosen) and one the form's own conditions turn off (a sheet's CC flag at 0: Flash2's temperature under `PD`, a stream's vapor fraction under `TP` -- Aspen still lets the tree take a value there, the run ignores it), its tooltip naming the option field above it on the sheet and its value; an empty required one is outlined red. A row with an `{id}` segment shows once per entry Aspen has there (a feed stage per feed, a flow per component), at most 24, those holding a value first; a stream made by a block shows its results only. A type whose general file has no row here takes the first other file of its type that has one (a heat stream: `streams-heat-work.md`). **All fields** adds every non-zero result under **Results**, and without the forms every other input with a value. Fields are named as in Aspen, else by what the docs say they are for; a row's tooltip says what it is (the docs' first sentence) and what it takes -- a number in its unit and the others it accepts, one of its menu's values, a component or stream ID, a word -- or, for a result, that Aspen computes it; no tree path (the field help card has it). The Chinese window puts our Chinese beside the English -- a field's, and every title the user clicks: forms, sheets, collections, model objects and their groups, palette tabs, docs table headings, list tables -- from the glossary and `tools/data/terms_zh.json`, in the inspector ours first and Aspen's after it, quieter (the Chinese for pressure, then **Pressure**); a title it does not have stays English.

- A click on an input's value edits it in place; the write is noted in the AI chat ("MEOHCOL › Reflux ratio: 2 → 2.5") and refused while a program or the AI's optimize holds the session.
- Per row (under the pointer): **?** opens the field help card (the field's prompt, value, units, options, related completeness rules, the docs rows about it); ⊕ adds it to the program as a `set` or `read`, sweeps it (±20 %, 5 points), seeks a target, or makes it an optimize variable, objective or constraint; **Back to the previous value** takes its last change back. A drag into the program does the same as ⊕'s first item.
- A stream's **Composition** section lists component flows or fractions, mass or mole.
- **More Aspen forms** (Aspen V15 only): a row per other GUI form in Aspen's order, titled as the navigation pane of the user's Aspen titles it (read from its strings; a form they do not title by its class, as words), a collection's form once per member (**Pumparounds P-1**); an open form shows its sheets as capsules, the ones Aspen hides left out. An amber dot marks an incomplete sheet, its form or section and the line (Aspen's completion flags, the sheet Next would open); what the user opens or closes is remembered per form. A sheet's fields are read only when its capsule is clicked or its section opened (about 20 ms of reads a pass), those holding a value first; an empty field a completeness rule requires is marked **missing**, the other empty fields of an incomplete sheet **empty** (Aspen marks the sheet, not which of them it needs); they edit, ⊕ and help like any row. A list of values on the sheet (feed stages by stream, side duties by stage, kLa by component) is a small table: its name with **+**, a row per label with **−** under the pointer; lists whose rows share one dimension (a row inserted in one is in all) form one table with a column each. **+** asks for the row's label (a stage number; the block's streams or the components not used yet are offered; a list without labels just gets a row); Enter adds it, Escape puts the line away.
- Subobjects (blocks with collections, under **More Aspen forms**): a line per collection that has members, each member a capsule (it opens the member's first sheet) with **−** under the pointer, and **+** to add one with the next ID offered (P-1, P-2 → P-3); a nested collection (an internals' sections, a pumparound's heating curves) a line per member it hangs under. The empty collections are behind one **Add** menu.
- A row or subobject added or removed is applied at once as the user's change, like a typed value: a restore point before the first structural change of the user's group, a chat line with **Undo**. A label Aspen refuses (a stage past the column's stages, a stream or component that is not there) leaves no row; Aspen's words are in the chat. Stream and component labels are upper-cased. Not while a program or the AI's optimization holds the model.
- The line under the head, when incomplete: its lead opens the first incomplete sheet, or without the forms the **Missing inputs** list at the object. A missing item in that list opens the inspector on its sheet, the field flashed.
- Head icons: **Ask AI** (about this object), **Add to program**, **Check for edits in the Aspen window** (the last two for blocks and streams).
- A model object shows its docs rows (its object folder's files: `setup/setup.md`, `reactions/reactions.md`, ...) and, on V15, its forms: a reaction's Stoichiometry and Kinetic sheets, a design spec's Define / Spec / Vary, Conv-Options' methods. A form none of whose completion flags or fields the object has is left out (Setup's Units-Sets and Stream-Groups forms belong to their own objects).

## Flowsheet

- Drawn left to right; recycles dashed. Red outline and "!" an Aspen error, amber "⚠" a warning, violet dashed with ✦ an AI highlight, a dot at a block's corner its changes not seen yet.
- **Values**: each stream's T, P and flow by its label; faded after an input changed until the next run; ▲ ▼ after a value the last run moved.
- **Flow**: a band under each stream, width by flow on a log scale; total flow, composition, or one component.
- **Heat plans**: after a real `pinch` run with matches, each exchanger match as an arc between the blocks, and the utility each block still needs; the card's **Apply via AI…** writes a request ([requests.md](requests.md#a-heat-plan-request)).
- **Annotations**: the AI's reasons, replies and pinned notes per object (on by default in learning mode).
- **Follow AI edits** (⋯ › Tracking and learning, off by default): each AI edit brings the view to its object, never while the user is working there.
- A proposal waiting for review is drawn over the flowsheet (**Preview · not applied**): new objects violet dashed, removed grey dashed, a tag per object set with current → proposed values. Nothing for the AI to write: it comes from the program's check. The preview is part of the drawing for the view: on a new model's empty flowsheet it is framed when it first shows, and it pans, zooms and fits like any block.
- After a proposal's run, result tags show before → after values; a click on a tag's line pins its path along the streams ([proposals.md](proposals.md#result-tags)).

## Arrangement

- **⋯ › Layout**: **Automatic**, or **Aspen layout** (reads Aspen's drawing; an export in the background, the model file untouched). Blocks and stream bends can be dragged; moves change only the picture and are kept per model. **Undo layout** / **Redo layout** step through moves and layout switches.
- **Redraw Aspen's diagram** runs `layout_flowsheet` as the user's own change (Aspen reopens the model).
- **Apply arrangement to Aspen** asks first, saves the model, then writes the workbench's block positions into Aspen's drawing and reopens it. Refused for a model with no drawing (Redraw first).
- `layout_flowsheet(session, from_workbench=true)` does the same for an arrangement moved by hand (`workbench_read` `flowsheet.arrangement` `custom (…)`); the automatic one is refused, with what the user presses instead; Aspen's own drawing unmoved has nothing to write.
- `arrangement` is `auto`, `aspen` or `custom (moved from auto | aspen)`: only the picture, never the topology.
- Reading Aspen's layout makes Aspen count the model as changed: closing Aspen by hand then asks whether to save.

## The window follows by itself

After a tool call that changed a session a tab shows, the window re-reads what changed (the flowsheet after a topology change or an open, results after a run, the inspector after a value write), about 0.8 s after the last call of a burst and at most 3 s after the first; it waits while a program or optimize holds the session. Neither `open_workbench` nor `refresh_flowsheet=True` is needed for that. A new server process (a `/mcp` reconnect) serves a window left open at once.

## Keys

| Key | Action |
|---|---|
| F5 | Run simulation (the program does not run) |
| F6 | Run program |
| Ctrl+F5, Ctrl+Shift+Enter | Check program |
| Ctrl+. | Stop the program |
| F10 | Next step of a paused program; Done at a manual step |
| Ctrl+Tab, Ctrl+Shift+Tab | Next / previous model tab |
| Ctrl+PgDn, Ctrl+PgUp | Next / previous sub-tab |
| Ctrl+Shift+H | History |
| Ctrl+K, / | The Ask AI box |
| Ctrl+S | Save model (the old file backed up first) |
| Ctrl+Shift+S | Save the block program as `.awb` |
| Ctrl+O | Open an `.awb` as a new program sub-tab |
| Ctrl+0 | Fit the block program in view |
| Ctrl+Z, Ctrl+Y | Undo / redo the last edit of the blocks or a move on the flowsheet |
| Esc | Close the topmost menu, card or dialog, then the AI's highlights |

## Workbench files (.awb)

**Save block program (.awb)…** writes a tab's work as JSON `{"format": "aspen-workbench", "version": 1, "saved", "title", "session", "program", "loose", "results"}`. **Open .awb as new tab…** makes a program sub-tab (on the file's session when it is open, else on the shown tab's); **Replace this tab's blocks from .awb…** puts one into a tab as one version. The file never holds the model: the `save` statement saves that.

## Learning mode in the window

With learning mode on ([review.md](review.md#learning-mode)): a **Learning** chip beside the shield; Annotations on; steps' `why` under the blocks; principle chips on groups; **Predict, then run…** lets the user guess up to 3 results (Up / Same / Down) before the next run and compare after it. Guesses stay in the window: they never reach the AI, the journal or a report.

## Words

| English | 中文 |
|---|---|
| AI review · Review mode | AI 審核 · 審核模式 |
| Read-only / Approve risky / Auto-apply | 唯讀／需核准／自動套用 |
| Pause AI / Resume AI | 暫停 AI／繼續 AI |
| Approval request · Approve / Decline… | 核准請求 · 核准／拒絕… |
| Run simulation | 執行模擬 |
| Restore point · Create restore point… | 還原點 · 建立還原點… |
| Changes | 變更 |
| Proposal · To review · Draft | 提案 · 待審核 · 草稿 |
| Step · Breakpoint · Continue | 逐步執行 · 中斷點 · 繼續 |
| Manual step · Waiting for input | 手動步驟 · 等待輸入 |
| Learning mode · Prediction | 學習模式 · 預測 |
| Follow AI edits | 追蹤 AI 修改 |
| Diagnosis · Missing inputs | 診斷 · 缺少的輸入 |
| More Aspen forms · All fields on this sheet · Add | 更多 Aspen 表單 · 此頁全部欄位 · 新增 |
| Inputs complete · 2 missing: | 輸入齊全 · 還缺 2 項： |
| Model objects | 模型物件 |
| missing · empty (a field's mark) | 缺 · 空白 |
| Field help · Add to program · Convert to program | 欄位說明 · 加入程式 · 轉為程式 |
| Apply arrangement to Aspen | 排列套用到 Aspen |
