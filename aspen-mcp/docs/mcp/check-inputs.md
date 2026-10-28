# check_inputs

`check_inputs(session)` names what Aspen still needs before it can run: per incomplete object, the form sheet Aspen marks incomplete and the fields empty on it. With nothing missing it returns `All required inputs are complete. Ready to run.`

## What it reads

An object is incomplete when its COMPSTATUS (attribute 12) holds bit 0x40. Objects read: the children of `\Data\Blocks`, `Streams`, `Reactions\Chemistry`, `Reactions\Reactions`, `Components\Henry-Comps`, `Components\Comp-Groups`, `Flowsheeting Options\Balance`, `Calculator`, `Design-Spec`, `Transfer`, `Model Analysis Tools\Sensitivity`, `Optimization`, plus `\Data\Components\Specifications` and `\Data\Properties\Specifications`. A folder whose own bit is set while none of its children's is gets listed under its own path, marked `(Aspen flags the folder itself, none of the objects in it)`.

The object `\Data`'s `NextIncomplete()` names (where the GUI's Next goes) is listed first, marked `(Aspen's Next goes here first)`.

A flagged block's top `Input` values are first read the way a GUI form reads them (30 values, 3 s at most); a just-placed block whose flag then clears is not reported.

## Sheet layer

Used when `tools/data/gui_forms_v15.json.gz` is present, `ASPEN_MCP_SHEETS` is not `0`, and the Aspen that COM starts is V15.0 (Localization.dll build 41.0). The table holds identifiers only (form and sheet classes, completion-flag paths, bound keywords, header keys, subobject collection names): 415 forms, 1,091 sheets, every input tab of a form; a tab without completion flags is always complete. It also names the forms the workbench never shows (Dynamics, EO, Costing, wizards) and, per block type, its subobject collections and the forms of each member (`Pumparounds` → the pumparound form), and per object container (`\Data\Blocks`, `\Data\Reactions\Reactions`, the singleton `\Data\Setup`, ...) its group and the forms prefix of each record type (a reaction of type USER takes the `Userdef` forms, not the User block's); the inspector reads the same table ([workbench/files.md](workbench/files.md)).

A sheet is incomplete when one of its completion flags under the object's `CC Nodes` is 0; a hidden sheet is skipped. Flags under a subobject ID are read per ID, and the sheet is named `<Form> <id> › <Sheet>`; a collection's form by its collection (`Pumparounds P-1 › Specifications`, `Column Internals CS-1 › Geometry`).

A sheet's listed fields are its bound `Input` nodes that hold no value (a list: no row with a value), are enterable (attribute 7) and are not switched off by the sheet's own flags. A labelled table's row without a label comes first, then fields with a prompt, scalars before lists.

```
RCSTR X1 › Setup › Kinetics: RXN_ID[] is empty (Reaction set ID); also empty on this sheet: CRYST_ID[], ACT_VALUE[]
```

`KW[]` is an empty list. One of the listed fields is usually the gap; not each of them is required. The form and sheet titles come from the strings read from the user's Aspen (the navigation pane's and the sheet's own); until they are read, the class's part shows as words (`React`, `Spec Summary`). One object's look stops after 3 s.

The field walk is used instead when the layer is off or does not fit this Aspen, the table has no form for the object, or no sheet accounts for a flagged object.

## Field walk

Reads the object's `Input` two levels deep, at most 400 empty fields:

| Line | Meaning |
|---|---|
| `unset:` | Empty fields with their prompts, scalars first |
| `zero-valued:` | Fields at 0: suspects only, Aspen stores many unset numbers as 0 |
| `modes:` | Values of fields whose names hold `OPT`, `SPEC`, `TYPE` or `BASIS` |
| `violated` | A GUI rule of the "X must be given" kind with no condition, whose field `Input\X` exists and is empty |
| `candidate GUI rules` | Up to 8 rules of the object's form table, ranked by word overlap; check each condition against the values |
| `GUI rules: not read yet` / `unavailable` | The rule texts are still being read / could not be read |

The rule texts are not shipped: `tools/aspen_strings.py` reads them from the user's own `AspenTech.AspenPlus.Localization.dll` (of the Aspen that COM starts) on first use, in the background, into `~/.aspen-mcp/aspen-strings/<version>/` (`prompts.tsv.gz`, `labels.json`), and again when the DLL changes. `tools/gui_rules.py` finds the object's form table by matching its field prompts (attribute 19) to those texts.

## Lines the server adds (both layers)

| Line | When |
|---|---|
| `open required port: <port>` | A required port is not connected |
| `required: <field> (<n> operating specifications required, ...)` | A RadFrac has fewer operating specs than its condenser and reboiler call for |
| `required: PROD_PHASE\<stream> (...)` | An MCompr knockout stream on `LK(OUT)` has no phase |
| `required: No components defined (...)` / `No property method selected (...)` | The components' or the methods' Specifications is flagged and nothing else required was found (`... input incomplete` when some are defined) |
| `ports connected:` / `ports unconnected:` | A block's ports, from the port catalog |

Under `Aspen's input translator would reject:` it lists setups no flag shows that stop the run: an ID with a character other than letters, digits, `-`, `+`, `#`, `$`; an Analyzer prop-set with more than one property; a USER3 configuration file in none of its `CFG_DIR_WNT` folder, the model's folder and `..\APINIT`; a BatchOp while the process type is not `BATCH`.

`run_simulation` refuses to start on the same flags, open required ports and translator setups; it does not read sheets or rules.

## Settings

| Setting | Effect |
|---|---|
| `ASPEN_MCP_SHEETS=0` | Field walk only |
| `ASPEN_GUI_PROMPTS=<file>` | Rule-text file read instead of the extraction |
| `ASPEN_LOCALIZATION_DLL=<dll>` | DLL the strings are read from |
| `aspen-mcp --extract-strings` | Read the strings now, in the foreground |
| `aspen-mcp --check` | Prints the `aspen-strings ...` and `gui-sheets ...` state |
