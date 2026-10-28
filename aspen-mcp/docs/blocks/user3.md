# USER3

Equation-based unit model. The route documented here: a built-in EO model type chosen with `SUBMODEL` and described by a plain-text configuration file (`.cfg`) you write. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F1(IN)` material inlets, `P2(OUT)` material outlets. The model numbers streams in the order they were connected.

Outlet 1 of the model is the first stream connected to `P2(OUT)`.

## Making it run (in this order)

1. Write the configuration file `<name>.cfg` ([user3-config-files.md](user3-config-files.md)).
2. Set `Input\SUBMODEL` to the model type the file declares.
3. Set `Input\CFGNAM` to the file name without `.cfg`; left empty, the block ID is used.
4. Put the file in the run folder (the simulation file's folder), or set `Input\CFG_DIR_WNT` to its folder.

No file found: input translation stops, so the run leaves no block status and no stream results (the block's input still counts as complete, so check_inputs does not flag it).

`CFG_DIR_WNT` must end with `\`; a relative folder starts at the run folder (`cfg\` and `..\..\out\user3\` both ran). A long absolute folder is cut short and the file is not found (a 56-character one failed): prefer a relative folder.

`SUBMODEL` and `USRMODEL` exclude each other: setting the second is refused.

## Setup | Subroutines

| Path | Type | Purpose |
|---|---|---|
| `Input\SUBMODEL` | `EOMIXER`, `EOCSPLIT`, `EOSPLIT` | Built-in model type: mixer, component splitter, stream splitter |

## Parameters | Control

| Path | Type | Purpose |
|---|---|---|
| `Input\CFGNAM` | name, 8 characters max | Configuration file name, without `.cfg` (default: block ID) |
| `Input\CFG_DIR_WNT` | folder | Folder that holds the file, ending in `\` |

## Input | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\FLASH_FEEDS` | `NO`, `YES` | YES: flash the inlets before the model is solved |
| `Input\BYPASS_USER` | `NO`, `YES` | YES: skip the model while the total inlet flow is zero |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\VARIABLE\{id}` | name | Model variable names, rows `1`, `2`, .. |
| `Output\VFINAL\{id}` | real | Value of each variable after the solve, in the units of `VUNITS` |
| `Output\VUNITS\{id}` | unit | Unit of each variable |
| `Output\VSTATUS\{id}` | `F`, `N` | F: fixed (inlet values, model specs); N: solved for |
| `Output\FUNCTIONS\{id}` | name | Model equation names; `RESIDUAL\{id}` holds their residuals |
| `\Data\Streams\{stream}\Output\MOLEFLMX\MIXED` | MOLE-FLOW | Outlet flow (190 kmol/hr from the two feeds) |

The split run lists the inlet's variables as `F`, the outlets' as `N`, and the first outlet's split ratio `STRM_2_RATIO` as `F` at 0.5.

More: [user3-config-files.md](user3-config-files.md) (file format), [user3-variables.md](user3-variables.md) (initial values), [user3-solver.md](user3-solver.md) (Jacobian and tolerances), [user3-eo-options.md](user3-eo-options.md) (EO block options).

Not covered: Block Options | Reactions (its reaction field is not in the tree); Equation status by row, Equation status by name (equation status flags: accepted, effect not seen); Compiled USER3 models (USRMODEL, USER_SUBS, USRREPORT, NIWORK, NWORK) (needs a compiled EO model, not checked); Other SUBMODEL types (EOCALC, EOANLZR, EOVALVE, CAPEOPEN ...) (each has its own file syntax, not checked); Changing the splitter's ratio (a fixed model variable; VINIT does not move it, other ways not checked); EO scripts and component groups (SC_METHOD, EO_COMPS) (not checked); ENERGY_BAL NO on USER3 (did not converge); INTER (interactive solver) (opens an interactive session, not checked).
