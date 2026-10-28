# Error History

Aspen Plus errors met on live runs, each with its cause and fix. `## ` is the error keyword: a
fragment of Aspen's message in upper case, or of the MCP tool's reply when Aspen says nothing.
`### ` is one case, `<Block> — <cause>`, with Block type, Cause and Fix lines. The fix names the
field to change first, as `Data.Blocks.{name}.Input.<KEYWORD>` for a block and as its tree path
(`\Data\Streams\{id}\Input\...`) for other objects; Block type then names the object or the tool.
Treat entries as hints to check.

# The run is refused, does not start, or does not return

## REQUIRED INPUTS ARE INCOMPLETE

### Compr, Flash3 — value written but the spec code not set

- **Block type**: Compr, Flash3
- **Cause**: Writing a spec value does not pick its spec code. Compr's `OPT_SPEC` stays empty after `PRES`, `DELP`, `PRATIO` or `POWER`; Flash3's `SPEC_OPT` stays TP after e.g. `PRES` + `VFRAC`.
- **Fix**: Set `Data.Blocks.{name}.Input.OPT_SPEC` (Compr) or `Input\SPEC_OPT` (Flash3, PV here) to the code that matches the values. Flash3 PQ / TQ also need a heat stream on `HS(IN)`.

### Compr, Valve, Electrolyzer — curve or parameter table with fewer than 4 points

- **Block type**: Compr (`OPT_SPEC=USE-CURVE` or `CALC_SPEED=YES`), Valve (`VP_DAT` table), Electrolyzer (performance curve)
- **Cause**: Each curve or valve-parameter table needs at least 4 points; with 3 the block stays incomplete.
- **Fix**: Give 4 or more points per curve: a row on the flow or opening list, then every column of that row (see `blocks/compr-curves.md`, `blocks/valve-parameters.md`).

### Compr — power-loss coefficient without a shaft speed

- **Block type**: Compr
- **Cause**: `PLOSS_COEF2` or `PLOSS_COEF3` was written (even as 0) without `ACT_SH_SPEED`.
- **Fix**: Set `Data.Blocks.{name}.Input.ACT_SH_SPEED`, or clear the unused coefficient (write "").

### MHeatX — outlets not paired, or wrong number of stream specs

- **Block type**: MHeatX
- **Cause**: Connecting `HP(OUT)` / `CP(OUT)` does not pair an outlet with its inlet, so `OUT\{inlet}` stays empty; or every stream has a SPEC, or more than one has none.
- **Fix**: Write the outlet ID to `Data.Blocks.{name}.Input.OUT.{inlet}` for every inlet, and leave exactly one stream without a SPEC (it closes the energy balance).

### Extract — no temperature estimate, stage pressure or key component

- **Block type**: Extract
- **Cause**: With `OPT_THERMAL` ADIABATIC (the default) or DUTY the block needs a `TEMP_EST` row, a stage pressure (`STAGE_PRES`; one row on stage 1 sets every stage) and one key component in each of `COMP1_LIST` and `COMP2_LIST`.
- **Fix**: Insert and fill the missing rows, e.g. `Data.Blocks.{name}.Input.TEMP_EST` on stage 1.

### SCFrac — steam stream connected after the fractionation-index rows

- **Block type**: SCFrac
- **Cause**: A stream connected to `SF(IN)` after the `FINDEX` / `FIEST` rows exist leaves the block incomplete although every field is filled.
- **Fix**: Connect the steam stream first, then create the `Data.Blocks.{name}.Input.FINDEX` rows (or delete and recreate them).

### MultiFrac — column without top and bottom temperature estimates

- **Block type**: MultiFrac
- **Cause**: A column has no `TEMP_EST\{col}` rows for its first and last stage.
- **Fix**: Insert `Data.Blocks.{name}.Input.TEMP_EST.{col}` rows labelled with stage 1 and the last stage, and give them temperatures.

### MultiFrac, PetroFrac — packing sizing or rating without vendor, material and size

- **Block type**: MultiFrac, PetroFrac (Pack Sizing / Pack Rating objects)
- **Cause**: An object given only `PS_PACKTYPE` (and HETP) stays incomplete.
- **Fix**: Set `Data.Blocks.{name}.Input.PS_VENDOR.{id}`, then `PS_PACK_MAT`, then `PS_PACK_SIZE`: the valid size codes depend on the first three, so a size written earlier is refused as not a valid value.

### PetroFrac — section, runback or stripper row inserted without a label

- **Block type**: PetroFrac
- **Cause**: A row inserted on `STEFF_STAGE1`, `THEFF_STAGE1` or `PZ_OPSETNAME\{stripper}` and never labelled.
- **Fix**: Label each row (section number or first stage) right after inserting it, e.g. on `Data.Blocks.{name}.Input.STEFF_STAGE1`.

### REquil — no reaction row

- **Block type**: REquil
- **Cause**: `Input\COEF` has no row.
- **Fix**: Add a reaction: a `Data.Blocks.{name}.Input.COEF` row labelled 1, then its reactant rows on `COEF\1` and product rows on `COEF1\1`.

### RGibbs — key-component phase assignment without a cutoff

- **Block type**: RGibbs (`ASSIGN_PH=KEY-COMPS`)
- **Cause**: `KEY_CID\{stream}` rows were given but `CUTOFF\{stream}` was left empty.
- **Fix**: Write `Data.Blocks.{name}.Input.CUTOFF.{stream}` (its row appears with the KEY_CID row), e.g. 0.5.

### RPlug — reactor type, size, reactions or coolant data missing

- **Block type**: RPlug
- **Cause**: `TYPE`, `LENGTH`, `DIAM` or an `RXN_ID` row is missing; COUNTER-COOL lacks the coolant `TEMP` or `CVFRAC`; CO-COOL or COUNTER-COOL has no streams on `C(IN)` and `C(OUT)`; or the catalyst density went to `RHO_CAT` instead of `CAT_RHO`.
- **Fix**: Fill the missing field; the catalyst density goes in `Data.Blocks.{name}.Input.CAT_RHO` (see `blocks/rplug.md`).

### Electrolyzer — port or geometry rule not met

- **Block type**: Electrolyzer
- **Cause**: ALKALINE fed on `FA(IN)` only (it needs `FS(IN)`, or `FA(IN)` + `FC(IN)`); RIGOROUS without `AREA_CELL`, `THICK_ANODE`, `THICK_CATHD`, `THICK_MEMBRN` (alkaline also `DIST_MMB_EL`); MODULE scope with a PEM cell, or without all four product compositions (`H2_FRAC_MOL` / `O2_FRAC_MOL` on both outlets).
- **Fix**: Meet the rule, e.g. set `Data.Blocks.{name}.Input.AREA_CELL`; `\Data\Blocks\{name}\CC Nodes\ALL` turns 1 once the block is complete (see `blocks/electrolyzer-rigorous.md`).

### Makeup — product connected to the purge port

- **Block type**: Makeup
- **Cause**: `P(OUT)` is the purge and `O(OUT)` the product outlet, which is required once a target is set.
- **Fix**: Connect the outlet to `O(OUT)` (see `blocks/makeup.md`).

### Screen — deck setup the block cannot complete

- **Block type**: Screen with `NDECKS` 2 or more
- **Cause**: A lower deck has no stream on `MS(OUT)` named in `COARSE_STRM\{n}`, or MODEL BOM or USER-SPEC is used on more than one deck.
- **Fix**: Connect one stream per lower deck to `MS(OUT)` and write its name to `Data.Blocks.{name}.Input.COARSE_STRM.{n}`; for BOM or USER-SPEC use one deck, or a curve model (PLITT, ROGERS, MOLERUS, WHITEN, IDEAL) on every deck.

### FluidBed — solids discharge, distributor or minimum fluidization input missing

- **Block type**: FluidBed
- **Cause**: `SOL_OUT_LOC` (a fraction of the height) is empty, or `NUM_ORIFICE` / `DIAM_ORIFICE` are empty for the default perforated plate, or `MF_VEL` is empty while `MINFVEL` is still VEL.
- **Fix**: Set `Data.Blocks.{name}.Input.SOL_OUT_LOC` (0 = bottom), the distributor fields, and either `MF_VEL` or `MINFVEL=CORRE`.

### CFuge — stream on the O(OUT) port

- **Block type**: CFuge (all types)
- **Cause**: A stream connected to `O(OUT)` leaves the block incomplete.
- **Fix**: Disconnect it; connect only `F(IN)`, `L(OUT)` for the liquid and `P(OUT)` for the cake.

### CCD — stage, side-stream or heat-transfer input missing

- **Block type**: CCD
- **Cause**: No stage row holds both `MEFF` (mixing efficiency) and `RATIO` (underflow liquid-to-solids ratio); a stream on `SF(IN)`, `SP(OUT)`, `PS(OUT)`, `HS(IN)` or `HS(OUT)` has no stage and direction in its row; or a stage uses `HEAT_UA`, which the block cannot complete.
- **Fix**: Insert a `Data.Blocks.{name}.Input.MEFF` row labelled with a stage and write `MEFF` and `RATIO` for it; give each side stream its stage and direction (`FEED_STAGE` + `FEED_DIRCODE`, `PROD_STAGE` + `PROD_DIRCODE`, `PSEUDO_STAGE` + `PSEUDO_DIRCO`, `H_FEED_STAGE` / `H_PROD_STAGE`); use `HEAT_SDUTY` or `TEMP` instead of UA.

### User — USRMODEL is empty

- **Block type**: User
- **Cause**: `Input\USRMODEL` has no value. check_inputs lists the block as incomplete and run_simulation refuses to run; an engine run would stop in input translation (BSUBPR.1, 'SUBROUTINE FOR: "MODEL" MUST BE SUPPLIED').
- **Fix**: Set `Data.Blocks.{name}.Input.USRMODEL` to the name the DLL exports, in upper case (see `blocks/user.md`).

### RStoic — fields of the previous spec option left set (not a cause)

- **Block type**: RStoic (V15)
- **Cause**: None from the left fields: after switching `SPEC_OPT` (e.g. to PD with `TEMP` still set) the old option's values stay stored and are ignored, the block's incomplete bit stays clear, and the run gives the same outlet as without them. Earlier "stale flag" reports came from old tools reading COMPSTATUS before re-reading the block.
- **Fix**: Nothing to clear: look for the field the new option needs, which check_inputs (it re-reads the block) names; do not close and reopen Aspen to clear the flag. `Data.Blocks.{name}.Input.SPEC_OPT` needs no clean-up.

## BLOCKS WITH NO RESULT

### Selector — selected stream is not an inlet

- **Block type**: Selector
- **Cause**: `Input\STREAM` names the block's outlet or a stream not on `F(IN)` / `HS(IN)` / `WS(IN)`; the value is accepted.
- **Fix**: Set `Data.Blocks.{name}.Input.STREAM` to a stream on the block's inlet port.

### Flash2 — free water switched on by a WD stream after NPHASE 3

- **Block type**: Flash2
- **Cause**: `NPHASE` 3 was set first and a stream then connected to `WD(OUT)`, which turns free water on; the run gives the block nothing.
- **Fix**: Use free water only with NPHASE 2: remove the `WD(OUT)` stream, or set `Data.Blocks.{name}.Input.NPHASE` to 2 (see `blocks/flash2-free-water.md`).

### Classifier — input the model cannot run

- **Block type**: Classifier (sifter and Husemann impeller types)
- **Cause**: The whole run never starts. Seen with `SIFT_INP=CROS-SEC` on `TYPE=CROSS-CURREN`, where it is not a valid input, and with `TYPE=IMP-HUSEMANN` without `WHEEL_HEIGHT`, `WHEEL_RADIUS` and `WHEEL_SPEED`.
- **Fix**: For CROSS-CURREN set `Data.Blocks.{name}.Input.SIFT_INP` to CUT-VEL, DENS-SIZ or SEPA-EFF (each with `L_W_RATIO`), or LEN-WIDTH. For IMP-HUSEMANN set the three wheel fields and `BLADE_DIST`, `BLADE_WIDTH`, `CRS_DIS_RAD`, `FNS_DIS_RAD`, `HUSEMANN_A`, `HUSEMANN_B`, `STD_FLOW`.

### Screen — spline interpolation of a user selection function

- **Block type**: Screen (`MODEL\1=USER-SPEC`)
- **Cause**: `INTERPOLATE` LIN-SPLINE or LOG-SPLINE.
- **Fix**: Keep `Data.Blocks.{name}.Input.INTERPOLATE` LINEAR (the default) and give more table points.

### Dryer — spray dryer without a droplet-interval count

- **Block type**: Dryer (SPRAY)
- **Cause**: `NUM_DROP_INT` is empty.
- **Fix**: Set `Data.Blocks.{name}.Input.NUM_DROP_INT` (3 ran).

### CCD — hidden side-draw flag set

- **Block type**: CCD
- **Cause**: `P_S\{stream}=YES` on a side draw (not on the GUI form) leaves the block complete, but the engine never starts.
- **Fix**: Leave `Data.Blocks.{name}.Input.P_S.{stream}` at NO.

### Setup — equation-oriented run mode

- **Block type**: Setup (`Sim-Options\Input\PARADIGM`)
- **Cause**: With `PARADIGM` EO a run started over COM never starts: no Run-Status and no results (V15).
- **Fix**: Write `\Data\Setup\Sim-Options\Input\PARADIGM` SM (or MIXED) before running or optimizing (see `setup/setup-run-mode.md`).

### GENERAL reaction set — a reaction without a name

- **Block type**: Reaction set (GENERAL)
- **Cause**: A GENERAL reaction whose `REACNAME` is blank stops input translation; no block gets results.
- **Fix**: Write `\Data\Reactions\Reactions\{id}\Input\REACNAME\{rxn}` for every reaction (see `reactions/reactions-general.md`).

### Data-Fit point data set — data cells addressed as one segment

- **Block type**: Data-Fit data set (POINT-DATA)
- **Cause**: Cells written as `VALUE\#1 TF INPUT` (one segment, as a listing prints them) stay empty, and a regression on that set never starts.
- **Fix**: Write the cells as `VALUE\#row\VAR\INPUT` and `VALUE\#row\VAR\RESULT` (three segments; see `analysis/data-fit.md`).

## A USER SUBROUTINE COULD NOT BE LINKED

### User, User2, User3 — the linker options file is not set

- **Block type**: User (also User2, User3 or any block that calls a user subroutine)
- **Cause**: The run has no linker options file, so the engine cannot find the DLL that exports the subroutine named in `USRMODEL`; the block gets no status and the outlets get no results.
- **Fix**: Write the DLL's full path in a plain text `.opt` file, run `set_engine_file(session, <path to the .opt>, kind="linker_options")` and run again; save the .bkp, which keeps the setting. With `USRMODEL` empty see the User entry under REQUIRED INPUTS ARE INCOMPLETE (see `blocks/user.md`).
- **Diagnostic note**: Aspen reports "COULD NOT RESOLVE USER OR IN-LINE FORTRAN SUBROUTINE(S)"; the history file shows CPLNKI.5 (dynamic link error), FPFNDI.1 (`SUBROUTINE "<name>" IS MISSING`) and FPRSLV.1, and run_simulation's reply suggests the fix. User2 with both `USRMODEL` and `EXCEL_FILE` empty fails differently: see BLOCK IS IN MASS IMBALANCE.

## INTERNAL FAULT

### Classifier — Whiten fit of a grade-efficiency table

- **Block type**: Classifier (METHOD DATA, INTERPOLATE FITTING)
- **Cause**: `OPT_WHITEN=YES`, alone or with the other fits, crashes the engine during the run (RPC_E_SERVERFAULT 0x80010105, V15).
- **Fix**: Reopen the model, leave `Data.Blocks.{name}.Input.OPT_WHITEN` off and use `OPT_ROGERS`, `OPT_PLITT` or `OPT_MOLERUS`.

### Screen — fitted user selection function

- **Block type**: Screen (`MODEL\1=USER-SPEC`)
- **Cause**: `INTERPOLATE=FITTING`, with any of the Plitt, Rogers or Molerus switches and 4- or 6-point tables, crashes the engine during the run.
- **Fix**: Reopen the model, keep `Data.Blocks.{name}.Input.INTERPOLATE` LINEAR and give more table points.

### Session — Aspen faulted on a tree walk; later runs would hang

- **Block type**: Session (any model)
- **Cause**: Aspen V15 raised RPC_E_SERVERFAULT, seen when the children of some property-parameter tables are read by index. The server marks the session and refuses its runs ("Aspen reported an internal fault in this session; runs would hang ...").
- **Fix**: Save or export a copy, close the model and open it again; reads keep working meanwhile.

## RUN NEVER RETURNS

### BatchSep — controller switched in an operating step

- **Block type**: BatchSep
- **Cause**: A CONTROLLER / MODE changed variable (`OPS_CONTROL`, `CTRLMODE` AUTO) keeps the step from ever starting; the integrator ran on past t = 600 while memory grew to 1.6 GB.
- **Fix**: Give the controller no step change, since a defined controller acts from t = 0; for a temperature PV put the set point in `Data.Blocks.{name}.Input.CONT_SPTEMP`, not `CONT_SP` (see `blocks/batchsep-controllers.md`).

### User2 — Excel workbook without the template macros

- **Block type**: User2 (Excel model)
- **Cause**: `EXCEL_FILE` points to a workbook that has the four Aspen sheets but not the macros of `userxltemplate.xls`; the engine opens Excel and never returns, with no dialog.
- **Fix**: Start the workbook from a copy of `<Aspen Plus>\Engine\User\userxltemplate.xls` and set `Data.Blocks.{name}.Input.EXCEL_FILE` to it. To recover, end only that run's AspenPlus.exe and the Excel it started with `/automation -Embedding` (see `blocks/user2-excel.md`).

## NOT A VALID TERTIARY KEYWORD

### Granulator — elutriation switched on for a gas inlet

- **Block type**: Granulator (V15)
- **Cause**: With a stream on `G(IN)` the GUI keeps the block incomplete until elutriation is on, but the V15 engine does not know the ELUTRIATION keyword and drops the block's whole parameter sentence, METHOD included; the gas ports are then rejected and the run does not start.
- **Fix**: None in V15: disconnect `G(IN)` / `G(OUT)` and model the gas side in another block.

### User2 — reaction set listed on the Reactions sheet

- **Block type**: User2 (V15)
- **Cause**: A row in `Input\RXN_ID` is written and read back fine, but the input translator rejects the REACTIONS keyword (BLDSNT.5) and translation stops.
- **Fix**: Remove the `Data.Blocks.{name}.Input.RXN_ID` rows; pass reaction data through the INT / REAL arrays if the model needs it.

## BADUNT

### RBatch — unit written on the feed-profile time

- **Block type**: RBatch
- **Cause**: `Input\FPROF_TIME\{stream}\#n` was written with a unit; the translator rejects the unit tag for this keyword, so the block is rejected and nothing runs.
- **Fix**: Write `Data.Blocks.{name}.Input.FPROF_TIME` as a plain value; it is read in the global time unit (hours with METCBAR).

## PROP-SET CONTAINS MORE THAN ONE PROPERTY

### Analyzer — property set with two properties

- **Block type**: Analyzer
- **Cause**: A property set listed in `Input\PSETNAME` holds more than one property, while the Analyzer reports one per set; the input translator stops with a severe error (ZUSPAN.2). run_simulation refuses this setup before running.
- **Fix**: Put one property in each set and list each set in its own `Data.Blocks.{name}.Input.PSETNAME` row (see `blocks/analyzer-property-sets.md`).

## UNABLE TO LOCATE CFG FILE

### User3 — configuration file not where the engine looks

- **Block type**: User3 with SUBMODEL (a built-in EO model)
- **Cause**: No `{CFGNAM}.cfg` (default name: the block ID) in `CFG_DIR_WNT` or the simulation file's folder; also when CFG_DIR_WNT lacks a trailing backslash or is an absolute folder over 48 characters. Code -00001 stops the run; code -00002 alone is harmless.
- **Fix**: Put the file next to the simulation file (run_simulation's pre-check looks there and in `..\APINIT`), or set `Data.Blocks.{name}.Input.CFG_DIR_WNT` to a relative folder ending in a backslash; give `CFGNAM` without .cfg and at most 8 characters (see `blocks/user3-config-files.md`).

## BLOCK CONSTRUCTION FAILED

### User3 — configuration file path too long

- **Block type**: User3 with SUBMODEL
- **Cause**: The file is found, but folder + name + .cfg runs past about 51 characters, so the location string is cut and the file cannot be read (U3BLK_INQ_CFGLOC-00002); the block ends with BLKSTAT 1 and a mass-balance error.
- **Fix**: Use a shorter absolute folder in `Data.Blocks.{name}.Input.CFG_DIR_WNT`, or a relative one.

## HAS NOT BEEN DEFINED AS A VALID SYMBOL

### Swash — PHASE S with NPHASE 1

- **Block type**: Swash
- **Cause**: The tree accepts `Input\PHASE` = S (write and read back pass), but the engine has no solid-only flash for this block: input translation rejects it (RDSYM.1, TKW: PHASE, paragraph ignored) and the run never starts.
- **Fix**: Use `Data.Blocks.{name}.Input.PHASE` L or V, or leave `NPHASE` at 2.

# A write is refused (set_value: Error writing)

## ERROR WRITING

### FSplit, Sep, Sep2 — second spec on an item that already has one

- **Block type**: FSplit, Sep, Sep2
- **Cause**: FSplit takes one spec per outlet (`FRAC`, `BASIS_FLOW`, `VOL_FLOW`, a limit or `R_FRAC`); Sep takes a split fraction or a flow per component and outlet; Sep2 takes one spec per component across both outlets and one stream spec in total. The second spec is refused and the old value kept (FSplit and Sep say "Only one of ... is allowed").
- **Fix**: Clear the existing spec (write "" to e.g. `Data.Blocks.{name}.Input.FRAC.{stream}`) before writing the new one.

### FSplit, Sep — spec on the last free outlet

- **Block type**: FSplit, Sep
- **Cause**: One outlet (on Sep, one per substream) must stay free to take the remainder, so once the others have specs its spec fields lock. It is whichever outlet is left free, not the last connected one.
- **Fix**: Leave that outlet blank, or clear another outlet's spec first (e.g. `Data.Blocks.{name}.Input.FRAC.{stream}`).

### Sep, Swash — conflicting flash specs

- **Block type**: Sep (outlet flash), Swash
- **Cause**: A Sep outlet-flash row takes two of `TEMP`, `PRES`, `DELT`, `VFRAC`, and TEMP excludes DELT. Swash takes a temperature or a duty, not both, and TEMP also excludes `T_EST`.
- **Fix**: Clear one spec (e.g. `Data.Blocks.{name}.Input.TEMP`) before writing the other; Swash with neither is adiabatic.

### Swash — inlet heat stream without an outlet heat stream

- **Block type**: Swash
- **Cause**: With a stream on `HS(IN)` and none on `HS(OUT)`, `TEMP` and `DUTY` are refused. The run still ends BLKSTAT 0, but the inlet duty never reaches the outlets (QCALC 0, enthalpy balance off).
- **Fix**: To heat the washer set `Data.Blocks.{name}.Input.DUTY` with no heat stream, or connect both `HS(IN)` and `HS(OUT)` and set `TEMP`; `HS(OUT)` then carries the inlet duty minus QCALC.

### Sep2 — only composition specs on one outlet

- **Block type**: Sep2
- **Cause**: One outlet carries as many mole- and mass-fraction specs as there are components, or more.
- **Fix**: Replace one with a split fraction or a flow, or give the outlet a stream spec (`Data.Blocks.{name}.Input.FRAC` / `FLOW`) and fewer fraction specs.

### Heater, DSTWU — free water set to NO while a decant stream is connected

- **Block type**: Heater (`WD(OUT)`), DSTWU (`CWD(OUT)`)
- **Cause**: A stream on the decant port needs a free-water or dirty-water option ("... when there is a decant stream").
- **Fix**: Keep `Data.Blocks.{name}.Input.BLKOPFREWAT` at YES or DIRTY, or disconnect the decant stream first.

### Flash2 — three phases together with free water

- **Block type**: Flash2
- **Cause**: Writing `NPHASE` 3 while `BLKOPFREWAT=YES` is refused.
- **Fix**: Use free water only with NPHASE 2, or remove the WD stream and turn free water off before setting `Data.Blocks.{name}.Input.NPHASE` to 3 (see `blocks/flash2-free-water.md`).

### HeatX — film-coefficient or geometry U in the shortcut model

- **Block type**: HeatX (`MODE=SHORTCUT`)
- **Cause**: `U_OPTION` FILM-COEF or GEOMETRY is refused while the model is SHORTCUT ("... unless model fidelity is detailed").
- **Fix**: Set `Data.Blocks.{name}.Input.MODE` to DETAILED with the shell and tube geometry first, or use CONSTANT, PHASE or POWER-LAW.

### MHeatX — QFRAC on a material stream, or flash-table interpolation without zones

- **Block type**: MHeatX
- **Cause**: `SPEC\{inlet}=QFRAC` is only for heat streams on `HLF(IN)` / `CLF(IN)`, and `OPT_CALC=TQTABLE` is refused while `NPOINT` is 0 (the default).
- **Fix**: Use TEMP, DUTY, VFRAC, ... on material streams; set `Data.Blocks.{name}.Input.NPOINT` above 0 before `OPT_CALC=TQTABLE` (and `TQTAB_NPOINT`).

### MHeatX — positive duty or temperature change on a hot stream

- **Block type**: MHeatX
- **Cause**: Hot-side duties and temperature changes are outlet minus inlet, so a positive `VALUE` with `SPEC\{inlet}` DUTY, DELT, MOLAR-Q or MASS-Q on a hot stream is refused ("... not allowed for the Hot side").
- **Fix**: Write `Data.Blocks.{name}.Input.VALUE.{inlet}` as a negative number (e.g. DELT -50), or put the spec on a cold stream.

### Extract — thermal option or product flow the block does not take

- **Block type**: Extract
- **Cause**: Switching `OPT_THERMAL` to TEMP is refused while `TEMP_EST` rows exist, and `PROD_FLOW` is refused on `TP(OUT)` / `BP(OUT)`, whose flows follow from the mass balance (only `SP(OUT)` takes one).
- **Fix**: Remove the TEMP_EST rows, then set `Data.Blocks.{name}.Input.OPT_THERMAL` to TEMP and add `TSPEC_TEMP` rows; use a side product for a fixed draw.

### MultiFrac — spec count, flow-spec duty or heat stream placement

- **Block type**: MultiFrac
- **Cause**: Each column takes at most two specs, and a condenser or reboiler set to NONE counts as one, so a third spec or `BASIS_D` with `BASIS_B` is refused (columns 2+ take one spec per end they have: D, B, Q1, QN). A `BASIS_L_SPEC` / `BASIS_V_SPEC` duty on a stage that already has `HEATER_DUTY` is refused, and so is a `QSTREAM_IN\{cs}` heat stream already placed on a column with `H_FEED_COL`.
- **Fix**: Clear a spec (e.g. `Data.Blocks.{name}.Input.BASIS_B`) before writing another, move the flow-spec duty or the side duty to another stage, and use a separate heat stream for the connect-stream heater.

### PetroFrac — third spec, or a spec pair the column does not allow

- **Block type**: PetroFrac
- **Cause**: With two specs set (e.g. `BASIS_RR` + `BASIS_D`) the rest are locked ("only two column specifications"). D with B, or a condenser or reboiler duty with a reflux spec, is refused ("combinations ... are not allowed"); RTYPE NONE-BOTFEED / NONE-BOTPA counts as a zero reboiler duty, so it is refused while `BASIS_RR` is set; CTYPE NONE-TOPPA is refused while `BASIS_D` is set.
- **Fix**: Clear a spec (write "" to e.g. `Data.Blocks.{name}.Input.BASIS_RR`) before writing another; use a distillate or bottoms rate before setting a NONE bottom; for NONE-TOPPA + NONE-BOTFEED give only `BASIS_OVFL`, `FRN_DUTY` or `FRN_TEMP`.

### PetroFrac — vapor-distillate top type with a stream on LD(OUT)

- **Block type**: PetroFrac
- **Cause**: CTYPE PARTIAL-V, NONE-TOPPA and NONE-TOPFEED send the distillate out of `VD(OUT)`, so the change is refused while a stream sits on `LD(OUT)` ("PHASE=LIQUID is not allowed for the distillate stream").
- **Fix**: Move the distillate stream from `LD(OUT)` to `VD(OUT)` first, then set `Data.Blocks.{name}.Input.CTYPE`.

### PetroFrac — main stripping steam not fed to the bottom stage

- **Block type**: PetroFrac
- **Cause**: `MAIN_STEAM` (steam rate from STEAM:PROD) accepts only a stream fed on stage `NSTAGE`.
- **Fix**: Set `Data.Blocks.{name}.Input.FEED_STAGE.{steam}` to the bottom stage before `MAIN_STEAM`.

### RBatch — single phase with a vent at fixed or profiled pressure

- **Block type**: RBatch
- **Cause**: With a stream on `VP(OUT)` and `PRES_TYPE` CONSTANT or PROFILE, setting `NPHASE` back to 1 is refused.
- **Fix**: Keep `NPHASE` at 2 or 3 while the vent is connected, or set `Data.Blocks.{name}.Input.PRES_TYPE` to CALCULATE first.

### Compr — equal-pressure-ratio steps with direct integration

- **Block type**: Compr (TYPE INT-POLYTROP or INT-POS-DISP)
- **Cause**: `INT_STEP=EQUAL-PRATIO` is refused together with `INT_METHOD=DIRECT`.
- **Fix**: Use `Data.Blocks.{name}.Input.INT_METHOD` N-METHOD, or `INT_STEP=EQUAL-DELP` with `INTERVALS`.

### Compr — turbine pressure drop given as a negative number

- **Block type**: Compr (`MODEL_TYPE=TURBINE`)
- **Cause**: A turbine takes its pressure drop and the power it delivers as positive numbers; a negative `DELP` is refused ("pressure decrease less than 0 is not allowed").
- **Fix**: Write `Data.Blocks.{name}.Input.DELP` and `POWER` as positive numbers, or give `PRES` or `PRATIO` below 1.

### MCompr — discharge spec type mixed across stages

- **Block type**: MCompr
- **Cause**: `OPT_CSPEC` must use the same code on every stage.
- **Fix**: Use one `Data.Blocks.{name}.Input.OPT_CSPEC` code on all stages.

### Distl — reflux ratio or distillate-to-feed ratio at its limit

- **Block type**: Distl
- **Cause**: Distl takes the reflux ratio itself, which must be above 0 (at most 100), with no negative multiple-of-minimum form as in DSTWU ("zero reflux ratio is not allowed"); `D_F` must lie strictly between 0 and 1.
- **Fix**: Give a positive `Data.Blocks.{name}.Input.RR` and a `D_F` between 0 and 1.

### Mult — negative factor on a material stream

- **Block type**: Mult
- **Cause**: A negative `FACTOR` is refused while a material stream is connected; it is accepted only on heat or work streams, where it flips the sign.
- **Fix**: Use a `Data.Blocks.{name}.Input.FACTOR` of 0 or more for material streams.

### Crusher — gap settings or King parameters written in the wrong order

- **Block type**: Crusher (JAW, CONE)
- **Cause**: A write that makes the closed-side setting `CSS` not smaller than the open-side `OSS` is refused and the old value kept; `KING_ALPHA2` not above `KING_ALPHA1` is refused the same way.
- **Fix**: Write `Data.Blocks.{name}.Input.CSS` first and below OSS; write `KING_ALPHA1` before a larger `KING_ALPHA2`.

### Heat stream — point lists on class HEAT

- **Block type**: Stream (HEAT)
- **Cause**: "No. of points is not allowed for heat stream class": `NPOINT`, `QVEC` and `TVEC` belong to class LOAD.
- **Fix**: A duty stream needs only `\Data\Streams\{id}\Input\DUTY`.

### Reaction set — reactant exponents still set when switching to EQUIL or CONV

- **Block type**: Reaction set (POWERLAW, LHHW, REAC-DIST)
- **Cause**: "Exponents for reactants may be entered only when Reaction Type=Kinetic" (REAC-DIST: "Exponent is not allowed unless Reaction Type=Kinetic"). add_reaction always writes reactant exponents, so `REACTYPE` EQUIL / CONV is refused while one holds a value.
- **Fix**: Write "" to each `EXPONENT\{rxn}\{comp}\MIXED` (REAC-DIST: `EXPONENT\{rxn}\{comp}`), then `REACTYPE` (see `reactions/reactions-equilibrium.md`).

### RadFrac — a non-REAC-DIST set written to REACID

- **Block type**: RadFrac
- **Cause**: "Could not create ID": `REACID` takes only REAC-DIST sets; a POWERLAW set ID is refused.
- **Fix**: Create the set with type REAC-DIST, then write it to `Data.Blocks.{name}.Input.REACID` (see `reactions/reactions-reac-dist.md`).

### Convergence — stream, design spec or optimization already on another block

- **Block type**: Convergence block
- **Cause**: "... is being converged by another convergence block": a tear stream (label on `TOL` / `SID_TOL`), a design spec (`SPECID`, `SPEC` label) or an optimization (`OPTID`) belongs to one convergence block only.
- **Fix**: Take it off the first block (remove_row, or write "" on `SPECID` / `OPTID`) or delete that block first.

### Convergence, Tear — tear row on a feed or product stream

- **Block type**: Convergence block, Tear
- **Cause**: "Tear stream may not be a feed or product stream": the label names a stream that is not connected at both ends.
- **Fix**: Tear a stream inside the loop, between two blocks (see `convergence/convergence-tear.md`).

### Broyden, Newton — tears-only first pass on a block without both a spec and a tear

- **Block type**: Convergence block (BROYDEN, NEWTON)
- **Cause**: "Tear tolerance and tear tolerance ratio are not allowed": `OPT_TTOL` TEAR-TOL / TOL-RATIO needs a design spec and a tear on the same block.
- **Fix**: Keep `\Data\Convergence\Convergence\{id}\Input\OPT_TTOL` NO, or add a `SPEC` row and a `SID_TOL` row first.

### Conv-Order — convergence block listed twice

- **Block type**: Conv-Order
- **Cause**: "Value has already been specified in this list": each block may appear once in `\Data\Convergence\Conv-Order\Input\CVBLOCK`.
- **Fix**: Write "" on the old row first, then the ID on its new row.

### Sensitivity — cases and series together

- **Block type**: Sensitivity
- **Cause**: "Only one of Cases (Vary sheet) or Series can be checked": `SERIES` YES is refused while `CASES` is YES.
- **Fix**: Use one of the two (see `analysis/sensitivity.md`).

## PHASE IS NOT ALLOWED WHEN NPHASE>1

### Heater, RYield, RPlug — NPHASE raised while PHASE still holds a value

- **Block type**: Heater, RYield, RPlug (also `CPHASE` / `CNPHASE` of the RPlug thermal fluid)
- **Cause**: `PHASE` keeps its single-phase value, so writing `NPHASE` 2 or 3 is refused and the old value kept.
- **Fix**: Write "" to `Data.Blocks.{name}.Input.PHASE` first, then set `NPHASE`. To go back, write NPHASE 1 before PHASE (see `blocks/heater-phases.md`).

## NOT A VALID VALUE

### Distl — feed stage written before the stage count

- **Block type**: Distl
- **Cause**: The feed-stage field has no valid range until the stage count exists.
- **Fix**: Write `Data.Blocks.{name}.Input.NSTAGE` first, then `FEED_LOC` (1 to NSTAGE).

### Pump, Compr — curve flow unit written before the independent variable

- **Block type**: Pump, Compr with performance curves
- **Cause**: `H_FLOW_UNIT`, `EF_FLOW_UNIT` and the other curve flow units refuse every unit until `INDEP_VAR` is set. With a per-speed variable (`INDEP_VAR1=VOL-FLOW/N`, as `DEP_VAR=HEAD-COEF` uses) the unit must also be per speed, such as cum/hr/rpm.
- **Fix**: Write `OPT_SPEC=USE-CURVE`, the curve type, `DEP_VAR` and `Data.Blocks.{name}.Input.INDEP_VAR` first, then the units (see `blocks/pump-curves.md`).

## VALUE IS OUT OF RANGE

### Pump — turbine drop or power given as a negative number

- **Block type**: Pump (turbine)
- **Cause**: A turbine takes the pressure drop and the power it delivers as positive numbers; a negative `DELP` or `POWER` is refused.
- **Fix**: Set `Data.Blocks.{name}.Input.PUMP_TYPE` to TURBINE and enter `DELP` and `POWER` as positive numbers, or give `PRES`.

### Reaction set — negative product coefficient

- **Block type**: Reaction set
- **Cause**: "It must be equal to or greater than 0": `COEF1` (products) takes only values of 0 or more.
- **Fix**: Give products positive values in `COEF1`; reactants go in `COEF`, which is stored negative whatever sign is written.

## UNAVAILABLE ACTION

### Mult — second stream on a port

- **Block type**: Mult
- **Cause**: Mult takes exactly one inlet and one outlet of one stream class; a second feed or outlet, or a heat or work stream beside a material one, is refused when connecting.
- **Fix**: Use one Mult per stream, and combine several feeds with a Mixer first.

## AE_UNDERSPEC

### PetroFrac — pumparound curve field written before the curve exists

- **Block type**: PetroFrac
- **Cause**: `PA_NPOINTS` is keyed by pumparound ID then curve ID; with no curve object the write fails.
- **Fix**: Add an element with an ID on `Subobjects\Pumparounds\{pa}\Subobjects\Hcurves`, then write `Data.Blocks.{name}.Input.PA_NPOINTS.{pa}.{curve}`.

## IS NOT ENTERABLE

### FSplit, Sep — another spec already fills that place

- **Block type**: FSplit, Sep (set_value)
- **Cause**: A spec is already written where the new one would go: FSplit takes one of `FRAC`, `BASIS_FLOW`, ... per outlet, and Sep takes one of `FRACS` or `FLOWS` per component and outlet. set_value checks that the field is enterable before writing and refuses; the old value stays.
- **Fix**: Clear the existing spec with "" (e.g. `Data.Blocks.{name}.Input.FRAC.{stream}`), then write the new one (see `blocks/common.md`).

# Messages from several block types

## PHASE STABILITY CHECK

### Flash2, Heater, Pump — water and organic liquids solved with too few phases

- **Block type**: Flash2, Heater, Pump (water + hydrocarbon feed, e.g. benzene/toluene/water)
- **Property method**: NRTL
- **Cause**: The mixture forms two liquid phases, but the block is solved with its default `NPHASE` (2 for Flash2 and Heater, 1 for Pump); BLKSTAT 2.
- **Fix**: Set `Data.Blocks.{name}.Input.NPHASE` to 3, or use free water (`BLKOPFREWAT=YES` with a stream on `WD(OUT)`).

### Sep2 — outlet holding water and organics flashed with two phases

- **Block type**: Sep2
- **Property method**: NRTL
- **Cause**: An outlet holding both water and hydrocarbons is flashed with the default two phases, at the feed-flash conditions or in its own outlet-flash row (BLKSTAT 2). A row on the other outlet alone does not help.
- **Fix**: Give each outlet that holds both liquids an outlet-flash row (`Data.Blocks.{name}.Input.NPHASE.{stream}` 3, or free water); when all the water goes to one outlet, `NPHASE1` 3 or `BLKOPFREWAT=YES` on the feed flash also works (see `blocks/sep2-outlet-flash.md`).

### DSTWU — water forms a second liquid

- **Block type**: DSTWU (`BLKOPFREWAT` YES or DIRTY, hydrocarbon/water feed)
- **Property method**: NRTL
- **Cause**: With the block's default water-solubility option (`SOLU_WATER` 3) the property flash of the distillate fails its phase-stability check after the shortcut itself has solved (BLKSTAT 2). More water, the global free-water switch, PENG-ROB or tighter flash settings do not help.
- **Fix**: Set `Data.Blocks.{name}.Input.SOLU_WATER` to 2 (Block Options; 0 and 1 also solve). Otherwise the shortcut results are still usable as estimates, or model the column in RadFrac with three phases or free water (see `blocks/dstwu-convergence.md`, `blocks/radfrac-three-phase.md`).

## SINGLE PHASE TEMPERATURE CALCULATIONS FAILED

### RPlug — liquid-only reactor near a component's critical temperature

- **Block type**: RPlug (`NPHASE=1`, `PHASE=L`)
- **Property method**: NRTL
- **Cause**: The liquid-only setting forces any vapor into the liquid. An exothermic adiabatic rise, or a hot inlet from the upstream heater, took the forced liquid up to a component's critical temperature, where the liquid enthalpy cannot be solved; downstream blocks then failed too.
- **Fix**: Lower the inlet temperature (the upstream heater's `Data.Blocks.{name}.Input.TEMP`) and raise the pressure. To see whether the tube boils, write `PHASE` "" then `NPHASE` 2, run, and read `Output\B_VFRAC\MIXED\{id}`; return to liquid-only only when no vapor shows.

## FLASH DID NOT CONVERGE

### Compr — design-condition correction: the design inlet never reaches the run

- **Block type**: Compr (`OPT_SPEC=USE-CURVE`, `OPT_DESIGN` not NONE)
- **Cause**: `PIN_DESIGN` and `TIN_DESIGN` read back after a write but are left out of the input the engine receives. `CORR-FACTOR` then stops with the design temperature and pressure missing (BLKSTAT 1, block bypassed); `CORR-FLOW` and `DIMENSIONLES` run on undefined design values and report an isentropic efficiency far above 1 and an operating point past stonewall (BLKSTAT 2), whatever design values are given. The same curves converge without correction.
- **Fix**: No setting was found that delivers the design conditions; leave `Data.Blocks.{name}.Input.OPT_DESIGN` at NONE and shift the curves with the factors and offsets instead.

## COULD NOT USE TABLE FROM SPECIFIED BLOCK

### Pipe, Pipeline — property grid copied from a block not yet solved

- **Block type**: Pipe (`OPT_ENTRY=BLOCK`), Pipeline (`OPT_GRID=BLOCKCOPY`), with `P_T_TABLE=YES`
- **Cause**: The named block runs after this one (no stream links them), so its pressure-temperature grid does not exist yet; the run warns and continues without a grid (BLKSTAT 2).
- **Fix**: Name a block upstream of this one, or use the RANGE or LIST grid options (`Data.Blocks.{name}.Input.OPT_ENTRY` on Pipe).

## OUTLET STREAM EMPTY

### Pipe, Pipeline — flow taken from an empty product stream

- **Block type**: Pipe, Pipeline (`FLOW_CALC=INLET`)
- **Cause**: `FLOW_CALC=INLET` takes flow and composition from the product stream's own input, which is empty; the block warns (BLKSTAT 2) and uses the feed.
- **Fix**: Give the product stream a flow, composition, T and P, or keep `Data.Blocks.{name}.Input.FLOW_CALC` OUTLET.

## CUMMULATIVE PSD

### Crusher, Granulator — given distribution runs past the top of the mesh

- **Block type**: Crusher, Granulator (USER-SPEC distribution functions)
- **Cause**: Part of the given function lies above the largest mesh size (e.g. LOG-NORMAL with `OV_GMDEV` 1.5-2, which is the standard deviation of ln(size)), so the block cuts and renormalizes it (BLKSTAT 2).
- **Fix**: Use a narrower function (smaller `Data.Blocks.{name}.Input.OV_GMDEV`; 0.4-1.2 ran) or extend the PSD mesh to larger sizes.

### Crystallizer — specified distribution reaches past the PSD mesh

- **Block type**: Crystallizer (`OPT_PSD=SPEC`)
- **Cause**: The function's spread puts mass above the mesh's largest size, so its cumulative there is below 1 and the block normalizes it and warns (BLKSTAT 2): LOG-NORMAL D50 100 um with `OV_GMDEV` 1.2 on a 500 um mesh gave 0.910 (`OV_GMDEV` is the standard deviation of ln(size)); RRSB D50 200 um, n 2 gave 0.987.
- **Fix**: Narrow the function (`Data.Blocks.{name}.Input.OV_GMDEV` 0.3 converged; RRSB D50 100 um, n 3 ran) or extend the PSD mesh's top size.

## PRODUCT TOO SMALL

### CFuge, Cyclone — solids load below what the split leaves in the fluid

- **Block type**: CFuge, Cyclone (`MODEL=SOLIDS-SEP`, `PHASEP_OPT=SPLP`)
- **Cause**: `SOLID_LOAD` (solids per fluid in the fluid outlet) is below what `SOLID_SPLIT` already leaves there (0.01 with a 0.98 split); the block raises it to the minimum and warns (BLKSTAT 2).
- **Fix**: Set `Data.Blocks.{name}.Input.SOLID_LOAD` at or above (1 - SOLID_SPLIT) x feed solids / feed fluid, lower SOLID_SPLIT, or use `PHASEP_OPT=SPSL`.

### VScrub, ESP — fluid load below the minimum the split implies

- **Block type**: VScrub, ESP (`MODEL=SOLIDS-SEP`, LL options)
- **Cause**: `FLUID_LOAD` (gas carried with the separated solids) is below the smallest consistent value (about 0.56 kg/kg in the tests); BLKSTAT 2.
- **Fix**: Raise `Data.Blocks.{name}.Input.FLUID_LOAD` (1 ran), lower `FLUID_SPLIT`, or use SPSL.

## NO BLOCK PARAGRAPH HAS BEEN ENTERED

### Mixer, Pump — no input written
- **Block type**: Mixer, Pump
- **Cause**: A block with every input left at its default is left out of the input file (EDBSEM.1), and input translation stops. A Pump fed only by a work stream on `WS(IN)` is no exception: the `PUMP` shown in `PUMP_TYPE` is a default, not an input.
- **Fix**: Write one input: `Data.Blocks.{name}.Input.PRES` 0 (Mixer) or `Data.Blocks.{name}.Input.PUMP_TYPE` PUMP (see `blocks/pump.md`, `blocks/common.md` Running).

# Columns

## COLUMN NOT IN MASS BALANCE

### RadFrac — distillate rate above the column's actual feed

- **Block type**: RadFrac
- **Property method**: NRTL
- **Cause**: `BASIS_D` is higher than the mole flow that reaches the column. A common way in: an upstream reaction consumes moles (A + B → C), so the column gets less than the fresh feed BASIS_D was sized against.
- **Fix**: Lower `Data.Blocks.{name}.Input.BASIS_D` below the column feed's mole flow (the feed stream's `Output\TOT_FLOW`, not the fresh feed).

### RadFrac — distillate plus side draws exceed the feed

- **Block type**: RadFrac with a side product on `SP(OUT)`
- **Cause**: `BASIS_D` plus the side-draw rates (`PROD_FLOW\{stream}`) add up to more than the column feed.
- **Fix**: Lower `Data.Blocks.{name}.Input.BASIS_D` or `PROD_FLOW` so distillate + side draws + bottoms equals the feed.

## COLUMN DRIES UP

### RadFrac — immiscible liquids solved with two phases

- **Block type**: RadFrac
- **Cause**: The mixture forms two liquid phases (e.g. an organic with water), but the column checks only vapor-liquid (`NO_PHASE=2`).
- **Fix**: Set `Data.Blocks.{name}.Input.NO_PHASE` 3 with a `TRAY2` range and key component (see `blocks/radfrac-three-phase.md`), or use free water (`BLKOPFREWAT=YES`).

### RadFrac — light gases dissolved in a high-pressure liquid feed

- **Block type**: RadFrac fed from a high-pressure separator
- **Cause**: Gases dissolved in the liquid feed (e.g. ethylene, CO2) go overhead and starve the stripping stages.
- **Fix**: Flash the liquid at the column pressure in a Flash2 first and send only its liquid to the column.

### MultiFrac — partial condenser temperature above what the top can give

- **Block type**: MultiFrac with a PARTIAL-V-L condenser and `OPT_COND_SPC=TEMP`
- **Cause**: The condenser temperature `T1` is above what the top composition allows (84-87 C for a benzene-rich top at 1 atm).
- **Fix**: Set `Data.Blocks.{name}.Input.T1` between the bubble and dew point of the top product (82 C converged) and give `RDV_EST`.

### PetroFrac — TOTAL pumparound returned above its draw stage

- **Block type**: PetroFrac with a pumparound
- **Cause**: A TOTAL draw takes the whole stage liquid; returned to a stage above (3 to 2), it leaves the stages below with no liquid.
- **Fix**: Return a TOTAL draw below its draw stage (3 to 4 converged), or use a PARTIAL draw with a flow.

### PetroFrac — partial condenser temperature far below the distillate bubble point

- **Block type**: PetroFrac with a PARTIAL-VL condenser
- **Cause**: `T_COND` is well below the distillate's bubble point (75 C for benzene/toluene at 1 atm).
- **Fix**: Raise `Data.Blocks.{name}.Input.T_COND` (83 C converged), or use `OPT_COND_SPC=RDV` with a `BASIS_DV:D` spec.

## LIQUID-LIQUID PHASE SPLIT CALC

### RadFrac — second-liquid search range too narrow

- **Block type**: RadFrac with `NO_PHASE=3`
- **Cause**: The `TRAY2` range covers only part of the stages where the second liquid forms.
- **Fix**: Widen `Data.Blocks.{name}.Input.TRAY2` to the whole column (label 1, value `NSTAGE`).

### RadFrac — decanter return share does not fit the reflux spec

- **Block type**: RadFrac with `NO_PHASE=3` and a decanter on stage 1 (`Subobjects\Decanters\1`)
- **Property method**: NRTL
- **Cause**: The decanter fixes one return share (`L1_SPEC` or `L2_SPEC`) and the reflux spec then sets the other; `L1_SPEC` 0.5 with reflux ratio 2 and the distillate rate given would need more than all of the water phase sent back, so the column ended with BLKSTAT 1 ("LIQUID-LIQUID PHASE SPLIT CALCULATIONS FAILED", UDL03Z.7) and a nonsense top temperature.
- **Fix**: Give the share that is free to be anything, e.g. `L2_SPEC` 0 (no water returned) and let the reflux spec set the organic return; or lower `Data.Blocks.{name}.Input.BASIS_RR` so the other share stays between 0 and 1.

## COLUMN NOT CONVERGED

### RadFrac — three-phase column stops at the iteration limit

- **Block type**: RadFrac with `NO_PHASE=3`
- **Cause**: Three-phase columns need more outer-loop iterations than the default, and the operating specs were far from what the feed can give.
- **Fix**: Raise `Data.Blocks.{name}.Input.MAXOL` (e.g. 100+), set `DAMPING=SEVERE`, and move the distillate / bottoms specs to realistic values.

## INVALID COLUMN SPECIFICATIONS

### MultiFrac — vapor flow spec met by a duty on the same stage or below

- **Block type**: MultiFrac
- **Cause**: The adjusted duty of a `BASIS_V_SPEC\{col}\{stage}` (`V_SPEC_QCOL` / `V_SPEC_QSTAG`) sits on the same stage or the one below, so the enthalpy balance is singular and the block is bypassed. A liquid flow spec in a column without both condenser and reboiler gave the same message.
- **Fix**: Put the adjusted duty one stage above the specified vapor (`Data.Blocks.{name}.Input.V_SPEC_QSTAG`; vapor of stage 3, duty on stage 2 converged), and use flow specs only in a column with its own condenser and reboiler.

## FAILED TO SATISFY DESIGN SPEC

### MultiFrac — target out of reach within the vary bounds

- **Block type**: MultiFrac
- **Cause**: 0.97 benzene in the distillate was asked while varying column 1's D in 30-70 kmol/hr; the best reachable was about 0.95 with D on its lower bound.
- **Fix**: Loosen the target (0.93 converged), widen the bounds, or add stages.

## SPECIFIED REFLUX RATIO LESS THAN MINIMUM

### DSTWU — positive reflux ratio below the minimum

- **Block type**: DSTWU (`OPT_NTRR=RR`)
- **Cause**: A positive `RR` below `MIN_REFLUX` (1.0 against 1.70) gives BLKSTAT 1, and the results shown are for twice the minimum, not for the RR given.
- **Fix**: Give `Data.Blocks.{name}.Input.RR` as a negative multiple of the minimum (e.g. -1.3), or a positive value above MIN_REFLUX.

## CANNOT SOLVE UNDERWOOD EQUATION

### DSTWU — light and heavy keys swapped

- **Block type**: DSTWU
- **Cause**: `LIGHTKEY` is the less volatile of the two keys (toluene light, benzene heavy); BLKSTAT 1.
- **Fix**: Make `Data.Blocks.{name}.Input.LIGHTKEY` the more volatile component.

## INFEASIBLE DESIGN

### ConSep — material-balance mode

- **Block type**: ConSep (V15)
- **Cause**: `IMODE=MAT-BALANCE` only closes the material balance (the products follow the three specs); it never designs the column, and the missing design is reported as this error (BLKSTAT 1) whatever the specs or reflux ratio. The product streams are still right.
- **Fix**: Use `Data.Blocks.{name}.Input.IMODE` DESIGN to get stages, feed stage, ratios and duties; if only the split is needed, read the products and ignore the error, or use Sep / Sep2. In DESIGN mode the same error means the specs are unreachable (next entry).

### ConSep — product specs no column profile can connect

- **Block type**: ConSep
- **Cause**: The three product specs plus the reflux ratio describe an unreachable split, e.g. a wet benzene/toluene/water feed with `IPHASE` VLL and no decanter, a decanter case at too high a reflux ratio (10 failed, 3 converged), or a feed too hot (95 C failed, 60 C converged).
- **Fix**: Check the split against the residue curves; take the azeotrope former (water) overhead with `IPHASE=VLL` + `ICONFIG=DECANTER`; change `Data.Blocks.{name}.Input.RR` or the feed state, or relax the recoveries.

## UNMAPPED COMPONENTS ARE EQUALLY MAPPED

### ConSep — feed with more than three components

- **Block type**: ConSep
- **Cause**: A component other than `SELCOMP1`-`3` has no component-map row, so it is split equally among the three (BLKSTAT 2).
- **Fix**: Insert a row on `Data.Blocks.{name}.Input.COMP1MAP` labelled with the component (it also appears in COMP2MAP and COMP3MAP) and write its shares so they sum to 1.

## NO OTHER LIQUID PHASES ARE ALLOWED FOR THAT STAGE

### RadFrac — free water with the distillate left at phase L

- **Block type**: RadFrac (`BLKOPFREWAT` YES or DIRTY, decant on `WD(OUT)`)
- **Cause**: The decant takes phase W on stage 1, and a distillate on the same stage at `PROD_PHASE` L conflicts with it ('IF "PHASE=L", NO OTHER LIQUID PHASES ARE ALLOWED', ZUDL03.7200 with ZUDL03.7210); the run stops in input translation.
- **Fix**: Set `Data.Blocks.{name}.Input.PROD_PHASE.{distillate}` to L1 (see `blocks/radfrac-three-phase.md`).

## A VAPOR DISTILLATE STREAM IS NEEDED BUT NOT SPECIFIED

### RadFrac — CONDENSER left empty

- **Block type**: RadFrac
- **Cause**: With `CONDENSER` empty the engine treats the top as a vapor-distillate condenser (ZUDL03.7290, "RDV is greater than 0"), but only `LD(OUT)` is connected; the run stops in input translation.
- **Fix**: Set `Data.Blocks.{name}.Input.CONDENSER` (e.g. TOTAL), or put the distillate on `VD(OUT)`.

## ZUDL14.17

### PetroFrac — CTYPE left blank

- **Block type**: PetroFrac
- **Cause**: With no condenser type the engine assumes PARTIAL-VL and asks for both a vapor and a liquid top product, even on a column built for a total condenser; the run stops in input translation.
- **Fix**: Set `Data.Blocks.{name}.Input.CTYPE` (e.g. TOTAL with a stream on `LD(OUT)`).

## PETROFRAC DOES NOT HANDLE DIRTY WATER

### PetroFrac — free water set to DIRTY

- **Block type**: PetroFrac
- **Cause**: PetroFrac has no dirty-water model: `BLKOPFREWAT=DIRTY` can be written, but the input translator stops (ZUDL14.94), and a `WD(OUT)` stream with phase W is then refused too (ZUDL14.8).
- **Fix**: Use `Data.Blocks.{name}.Input.BLKOPFREWAT` YES.

## LIQUID PHASE MAY BE UNSTABLE

### RadFrac — CONV_METH PETROLEUM on a three-phase column

- **Block type**: RadFrac (`NO_PHASE` 3 with `TRAY2` and `COMP_LIST`, e.g. benzene/toluene/water)
- **Property method**: NRTL
- **Cause**: `CONV_METH` `PETROLEUM` sets `ALGORITHM` `SUM-RATES`, which works with one liquid only. Input translation warns that the `L2-STAGES` and `L2-COMPS` input is ignored (ZUDL03.7560, ZUDL03.7570). The column is then solved with one liquid and warns that the liquid may be unstable on the stages (CHKSTB.1); BLKSTAT 2.
- **Fix**: Keep `Data.Blocks.{name}.Input.CONV_METH` at `STANDARD` (or set `ALGORITHM` `STANDARD`) when `NO_PHASE` is 3 (see `blocks/radfrac-three-phase.md`).

# Heat exchangers

## PRESSURE-DROP CORRELATION PARAMETER IS MISSING

### HeatX — FLOW pressure-drop option without its parameter

- **Block type**: HeatX (SHORTCUT)
- **Cause**: `HDP_OPTION=FLOW` (or `CDP_OPTION=FLOW`) with `HDPPARMOP=NO`; a reference drop in `PRES_HOT` does not supply the parameter, and the block reports zero duty.
- **Fix**: Set `Data.Blocks.{name}.Input.HDPPARMOP` to YES and give `HDPPARM` in SI units (1e6 gave about 0.008 bar on 100 kmol/hr BTX), or go back to `HDP_OPTION=CONSTANT` with `PRES_HOT`.

## MAXIMUM ALLOWABLE DELTA-P

### HeatX — FLOW correlation parameter too large

- **Block type**: HeatX
- **Cause**: `HDPPARM` was so large that the drop exceeded `HMAX_DP` (default 0.4 of the inlet pressure); the solver then fails in its Broyden iteration.
- **Fix**: Lower `Data.Blocks.{name}.Input.HDPPARM` (the drop scales linearly with it) or raise `HMAX_DP`.

## ROOT MEAN DIAMETER

### HeatX — fin height too large for the tube

- **Block type**: HeatX (`MODE=DETAILED`, `TUBE_TYPE=FINNED`)
- **Cause**: The fin root diameter (tube OD minus twice `HEIGHT`) fell below the tube's inside diameter, so the block is bypassed.
- **Fix**: Reduce `Data.Blocks.{name}.Input.HEIGHT`, or set `OPT_FHEIGHT=ROOT-DIAM` with a `ROOT_DIAM` between the inside and outside diameters.

## ABSOLUTE AREA TOLERANCE IS TOO LARGE

### HeatX — rating with UA but no area

- **Block type**: HeatX (SHORTCUT, `PROGRAM_MODE=SIMULATION`)
- **Cause**: Only `UA` was given, so the block sees an area of about 0 and ends with a warning (BLKSTAT 2) and zero duty.
- **Fix**: Give `Data.Blocks.{name}.Input.AREA` (with the U method) instead of UA.

### HeatX — UA given in SIMULATION mode with the default U method
- **Block type**: HeatX
- **Cause**: `PROGRAM_MODE=SIMULATION` with `UA` in place of `AREA` while `U_OPTION` is still `PHASE`, its default. The block takes a near-zero area (about 3e-32 sqm), warns that the area tolerance is too large for that area, skips the T-Q curve because the duty is zero, and ends with BLKSTAT 2 and both outlets at their inlet temperatures.
- **Fix**: Set `U_OPTION=CONSTANT` together with `UA`, or give `AREA` instead of `UA`. A block accepts only one of `AREA` and `UA`.

## HAS NO T-Q PROFILE

### MHeatX — heat stream on a load port

- **Block type**: MHeatX
- **Cause**: A heat stream on `HLF(IN)` / `CLF(IN)` carries no temperature-duty profile, so its duty is booked as heat leak (BLKSTAT 2); setting `TEMP` / `TEND` on the heat stream does not help.
- **Fix**: Carry that duty on a material stream instead.

## MISMATCH IN HEAT STREAM DIRECTION

### HXFlux — heat stream direction does not match its sign

- **Block type**: HXFlux
- **Cause**: The heat stream on `HS(IN)` (or named in `DUTY_SID`) is negative, e.g. from a heater, while `HEATSTRM_DIR` is HOT-TO-COLD, or a positive stream from a cooler is paired with COLD-TO-HOT (BLKSTAT 2).
- **Fix**: Set `Data.Blocks.{name}.Input.HEATSTRM_DIR` to COLD-TO-HOT for a negative heat stream and HOT-TO-COLD for a positive one.

## OUTLET TEMPERATURE MAYBE UNREASONABLE

### HXFlux — duty, U and area do not fit the temperatures

- **Block type**: HXFlux
- **Cause**: An outlet temperature is left to be computed, but the given `DUTY` is far from U x AREA x LMTD, so the computed outlet ends up next to the other side's inlet (BLKSTAT 2).
- **Fix**: Make DUTY, U and AREA consistent with the temperatures, or leave `Data.Blocks.{name}.Input.DUTY` blank so it is computed.

## INLET TEMPERATURE IS MISSING

### HXFlux — hot or cold inlet temperature blank

- **Block type**: HXFlux
- **Cause**: `THOT_IN` or `TCOLD_IN` (or its stream reference) is not given, so the block is incomplete.
- **Fix**: Set both `Data.Blocks.{name}.Input.THOT_IN` and `TCOLD_IN`, or `OPT_HOTIN` / `OPT_COLDIN=STREAM` with a stream ID.

## INPUT VARIABLES ARE UNDERSPECIFIED

### HXFlux — radiant mode with only four radiant quantities

- **Block type**: HXFlux (`HEAT_TR_MODE=RADIANT`)
- **Cause**: Besides `TCOLD_IN`, only four of `TCOLD_OUT`, `T_FLUE_GAS`, `DUTY`, `H_CONV`, `TUBE_AREA`, `COLD_PL_AREA` were given; five are needed.
- **Fix**: Give five of the six (e.g. add `Data.Blocks.{name}.Input.H_CONV`); the sixth is computed.

## LEVELS ARE MISSING

### HXFlux — immersed tube bundle without a level reading

- **Block type**: HXFlux (`AREA_OPT=IMM-BUNDLE`)
- **Cause**: `LEVEL_MEAS\#0` has no value; its rows only appear once `NUM_BUNDLES` is set.
- **Fix**: Set `Data.Blocks.{name}.Input.NUM_BUNDLES`, then one reading per bundle in `LEVEL_MEAS\#n`, plus one of `LEVEL_TOP` / `LEVEL_BOT`.

## SPEC VALUE READ IN THE WRONG UNIT

### HeatX — the unit of VALUE given to VALUE itself (raw COM)

- **Block type**: HeatX (also MHeatX `VALUE\{inlet}` with `SPECUN\{inlet}`)
- **Symptom**: No message; the outlet temperature or duty is off by a unit factor (176 meant as F runs as 176 C, 1 MW runs as 1 cal/sec).
- **Cause**: `VALUE` has no unit row; the engine reads it in the unit `SPECUN` holds, whose default follows `SPEC` (C for a temperature spec, cal/sec for DUTY, not the unit set's). A unit passed with a raw `SetValueAndUnit` on `VALUE` is dropped without an error.
- **Fix**: Use set_value with `unit=` (it writes `SPECUN`), or write `Data.Blocks.{name}.Input.SPECUN` first, then `VALUE` without a unit.

# Reactors

## DOES NOT SATISFY MASS BALANCE

### RStoic — reaction coefficients not mass-balanced

- **Block type**: RStoic
- **Cause**: The coefficients in `COEF\{id}` / `COEF1\{id}` do not balance in mass (e.g. ETOH + HAC -> 1.5 ETAC + H2O); the run stops before the block, with no BLKSTAT and no results.
- **Fix**: Correct `Data.Blocks.{name}.Input.COEF1` / `COEF` so that coefficient x molecular weight sums to zero for each reaction.

## CONVERSION FRACTIONS

### RStoic — conversion or extent needs more of a reactant than the feed holds

- **Block type**: RStoic
- **Cause**: A reaction's conversion of its key, or its fixed extent, uses more of some reactant than enters (e.g. a key component in excess, or a conversion inside a recycle that scales with the recycle flow). Aspen cuts the reaction back until that reactant is used up; BLKSTAT 2.
- **Fix**: Make the limiting reactant `Data.Blocks.{name}.Input.KEY_CID`, lower `CONV` or `EXTENT`, or use `OPT_EXT_CONV=EXTENT` for a fixed rate inside a recycle.

## SPECIFIED YIELDS HAVE BEEN NORMALIZED

### RYield — yields do not account for exactly the feed mass

- **Block type**: RYield
- **Cause**: Yields count against the non-inert feed mass; when mass yields do not add up to 1, or mole yields x molecular weight do not, the block rescales them (BLKSTAT 2). Mole yields rounded to 6 decimals already trigger it.
- **Fix**: Enter mass yields (`Data.Blocks.{name}.Input.BASIS.{comp}.MIXED` = MASS) that add up to 1, or compute mole yields at full precision with Aspen's own molecular weights (see `blocks/ryield.md`).

## ELEMENTS ARE NOT IN ATOM BALANCE

### RYield — yields do not conserve elements, or a feed component is consumed

- **Block type**: RYield
- **Cause**: The yields do not balance the elements, or a feed component has no yield and is not listed as inert, so it is used up and its mass goes to the other products (BLKSTAT 2).
- **Fix**: List pass-through components in `Data.Blocks.{name}.Input.COMP_LIST` and correct the yields; if the imbalance is intended, set `ATOM_BAL_CHK` NO.

## SPECIFIED TEMPERATURE APPROACH

### REquil — temperature approach with the sign that raises the equilibrium constant

- **Block type**: REquil
- **Cause**: `TAPP_CHK` checks a reaction's `DELT`. On an exothermic reaction DELT -20 C (which raises K) gave a warning under WARNING (BLKSTAT 2) and an error under ERROR (BLKSTAT 1); DELT +20 C passed.
- **Fix**: Check the sign of DELT against the reaction's heat effect, or set `Data.Blocks.{name}.Input.TAPP_CHK` to NONE or INFORMATION when the approach is intended.

## FAILURE TO SOLVE 2-PHASE ADIABATIC PROBLEM AS TP SUBPROBLEMS

### REquil — temperature and duty both fixed with a reaction at equilibrium

- **Block type**: REquil (`SPEC_OPT=TD`)
- **Cause**: With temperature and duty fixed the pressure is solved in an outer loop. With a reaction held at chemical equilibrium (`OPT_EXT_DELT` DELT) that loop ran down to about 0.1 bar (all vapor) on a liquid esterification mixture and stopped (EQULK2.14, then URE05.9 "equilibrium calculation not converged", BLKSTAT 1), whatever the duty, `P_EST` or `MAXIT`.
- **Fix**: Put the reaction on a fixed extent (`Data.Blocks.{name}.Input.OPT_EXT_DELT` EXTENT with `EXT_SPEC`), or give the pressure instead (`SPEC_OPT` PD, or PV / TV with a vapor fraction) and solve the duty or temperature.
- **Diagnostic note**: Earlier runs of this case were filed under FLASH DID NOT CONVERGE.

## NUMBER OF REACTIONS IS NOT EQUAL

### RGibbs — too few individual restricted reactions

- **Block type**: RGibbs (`RESTR_TYPE=INDIVIDUAL`)
- **Cause**: With a fixed extent there were fewer reactions than species minus elements, e.g. steam reforming alone for CH4/H2O/CO/CO2/H2 (BLKSTAT 1).
- **Fix**: Add the missing independent reactions (here water-gas shift) with DELT or EXTENT specs.

## P-LOOP NOT CONVERGED

### RGibbs — pressure left empty

- **Block type**: RGibbs
- **Cause**: No `PRES` was given; the input is not flagged incomplete, the run starts and the block ends with BLKSTAT 1.
- **Fix**: Set `Data.Blocks.{name}.Input.PRES` (a value, or zero or negative for a drop from the feed).

## PHASE VOL/VOL-FRAC SPEC IS INCONSISTENT

### RCSTR — phase volume-fraction sizing without a volume estimate

- **Block type**: RCSTR (`NPHASE` 2, `SPEC_TYPE=RES-TIME-PH-VOL-FRAC`)
- **Cause**: With no starting volume the solver reaches an outlet with no vapor, where a phase volume fraction cannot apply; Aspen also warns that no vapor is present (BLKSTAT 2).
- **Fix**: Set `Data.Blocks.{name}.Input.VOL_EST` to a volume of the right order (1.5 m3 converged) and rerun.

## KOH COMPONENT IS REQUIRED

### Electrolyzer — rigorous alkaline model without KOH

- **Block type**: Electrolyzer (`CELL_TYPE=ALKALINE`, `MODEL_TYPE=RIGOROUS`)
- **Cause**: The rigorous alkaline model needs KOH, but the component list held only water, hydrogen and oxygen. The shortcut and curve models run without it.
- **Fix**: Add KOH (POTASSIUM-HYDROXIDE) as a component and feed some with the water (50 kmol/hr water + 5 kmol/hr KOH ran).

## ANODE PRESSURE DROP SPECIFICATION IS MISSING

### Electrolyzer — correlation pressure drop with the shortcut model

- **Block type**: Electrolyzer (SHORTCUT)
- **Cause**: `PDROP_SPEC=CORRELATION` needs the cell geometry of the rigorous model, so with SHORTCUT the run stops (BLKSTAT 1).
- **Fix**: With SHORTCUT use `Data.Blocks.{name}.Input.PDROP_SPEC` FIXED (`PRES_ANODE` / `PRES_CATH`) or CELL-PRESS (`PRES_CELL`), or switch to RIGOROUS.

## FAILED TO FIND THE UPPER BOUNDARY

### Electrolyzer — adiabatic module scope

- **Block type**: Electrolyzer (`MODEL_SCOPE=MODULE`)
- **Cause**: With `TQ_SPEC=DUTY` and `HEAT_DUTY` 0 no outlet temperature closes the energy balance for the dry high-purity products, and the shortcut calculation fails after it.
- **Fix**: Set `Data.Blocks.{name}.Input.TQ_SPEC` to TEMPERATURE with `TEMPERATURE` (80 C converged); the duty becomes a result.

## WATER CROSSING-OVER IS GREATER

### Electrolyzer — drag moves more water than reaches the anode

- **Block type**: Electrolyzer (shortcut, `W_CROSS_METH=W-PERM-COEF`)
- **Cause**: The default `H2O_PERM_C` of 6 per proton exceeds the anode-side water (a small feed, or a stack feed split by `AN_FD_RATIO` 0.5); Aspen sets the crossover to zero and continues with a warning.
- **Fix**: Feed more water (50 kmol/hr per 100 kW was clean), lower `Data.Blocks.{name}.Input.H2O_PERM_C`, or use W-CROSS-FRAC with `H2O_CROSS_F`.

## M-BAL LOOP DID NOT CONVERGE

### RCSTR — Ziegler-Natta reaction set solved from a fresh start
- **Block type**: RCSTR
- **Cause**: with site-based Ziegler-Natta kinetics and no estimate, the mass-balance loop needs more than the default 50 iterations. Seen on a liquid RCSTR at 69 C, 40 atm, 2 m3 (polypropylene example components): BLKSTAT 1.
- **Fix**: raise Input\MB_MAXIT (500 converged, and so did 200) or set Input\ALGORITHM INTEGRATOR. Both gave BLKSTAT 0 (blocks/rcstr-convergence.md).

## RPLUG EXITED BECAUSE INTEGRATION FAILED

### RPlug — emulsion reaction set
- **Block type**: RPLUG
- **Cause**: an EMULSION set (styrene in water, APS, SLS, TDM; liquid, 70 C) does not integrate along the tube; the block ends with BLKSTAT 1.
- **Fix**: run the emulsion set in a batch reactor (RBatch); the same set converged there with BLKSTAT 0.

# Pressure changers and pipes

## VAPOR EXISTS IN THE FEED STREAM

### Pump — vapor in the feed with the default vapor check

- **Block type**: Pump
- **Cause**: The feed is partly vapor (too hot, or too low a pressure for a liquid). With `VFRAC_CHK=ERROR` (the default) the block stops with BLKSTAT 1; with WARNING it finishes with BLKSTAT 2.
- **Fix**: Subcool the feed or raise its pressure upstream, and use Compr for a gas. Set `Data.Blocks.{name}.Input.VFRAC_CHK` to WARNING or NONE only when a little vapor is intended.

## VAPOR EXISTS IN THE OUTLET STREAM

### Pump — near-boiling liquid let down below its bubble point

- **Block type**: Pump
- **Cause**: With an outlet pressure below the bubble pressure and `NPHASE` 2 the outlet flashes (95 C benzene/toluene taken to 0.5 atm gave 0.44 vapor and BLKSTAT 1).
- **Fix**: Keep `Data.Blocks.{name}.Input.PRES` above the bubble pressure, or use a Valve or Flash for a let-down that vaporizes.

## KNOCKOUT STREAM PER STAGE

### MCompr — fewer knockout streams than stages minus one

- **Block type**: MCompr
- **Cause**: Fewer `LK(OUT)` streams than `NSTAGE`-1 and none marked global stops input translation (ZUPC03.13).
- **Fix**: Connect one knockout stream per stage 1 to NSTAGE-1 with `PROD_STAGE` set, or one with `Data.Blocks.{name}.Input.GLOBAL.{stream}` = Y.

## PHASE STREAMS MUST BE SPECIFIED TOGETHER

### MCompr — free water with only water knockouts

- **Block type**: MCompr
- **Cause**: With free water on, each knockout stage needs both an L1 and a W stream (ZUPC03.27).
- **Fix**: Per knockout stage, connect one stream with `Data.Blocks.{name}.Input.PROD_PHASE.{stream}` = L1 and one with W.

## LIQUD PHASE PRESENT AT OUTLET

### MCompr — wet gas condenses in the intercoolers without knockouts

- **Block type**: MCompr
- **Cause**: Liquid forms at the outlet or intermediate conditions and there is no `LK(OUT)` stream to take it (BLKSTAT 1).
- **Fix**: Add knockout streams on `LK(OUT)`, each with its stage and `Data.Blocks.{name}.Input.PROD_PHASE.{stream}` (see `blocks/mcompr-feeds-knockout.md`).

## TEMPERATURE SPEC WAS USED INSTEAD OF PRESSURE SPEC

### MCompr — stage temperature override left on

- **Block type**: MCompr
- **Cause**: `OPT_TEMP\{stage}=YES` with `TEMP` overrides the stage pressure spec (BLKSTAT 2).
- **Fix**: Remove `Data.Blocks.{name}.Input.OPT_TEMP` / `TEMP` unless the override is intended.

## STABILITY CRITERION NOT SATISFIED

### MCompr — free water YES with an equation-of-state method

- **Block type**: MCompr (`BLKOPFREWAT=YES`)
- **Property method**: PENG-ROB (also PR-BM, RKS-BM)
- **Cause**: Each cooler leaves the gas water-saturated by the steam-table free-water model, and the next stage's flash, tested with the equation of state, calls that vapor unstable (CMSTIN.10 for H2O; BLKSTAT 1, BLKMSG "PROBLEM(S) ENCOUNTERED DURING STABILITY CHECK"). `GSOLU_WATER` and the global free-water switch do not change it.
- **Fix**: Use `Data.Blocks.{name}.Input.BLKOPFREWAT` DIRTY with the equation of state, keep YES with a method such as GRAYSON or CHAO-SEA, or use no free water with knockout phase L.

### Heater — water-rich feed flashed with two phases

- **Block type**: Heater
- **Cause**: The Heater stays at `NPHASE` 2 on benzene/toluene/water (UHE01.4); the feed stream's own `NPHASE` 3 does not carry into the block.
- **Fix**: Set `Data.Blocks.{name}.Input.NPHASE` to 3 (see `blocks/heater-phases.md`).

## FLOW IN THE VALVE IS CHOKED

### Valve — outlet pressure below the choked-flow limit

- **Block type**: Valve (SET-PRESSURE)
- **Cause**: The specified outlet pressure is below `Output\CHOKE_POUT` (0.5 bar against 0.91 bar for an 80 C BTX liquid in a 2-IN globe valve); the run warns (BLKSTAT 2, `CHOK_STAT` 2).
- **Fix**: Raise `Data.Blocks.{name}.Input.P_OUT` above CHOKE_POUT or use a valve with a higher FL; if a choked let-down is intended, set `CHECK_CHOKE` NO.

## OUTLET PRES IS LOWER THAN THE MIN PRES SPEC

### Valve — rating opening too small to pass the feed

- **Block type**: Valve (CALC-PRESSURE)
- **Cause**: At the given opening or Cv the valve cannot pass the feed above the lowest allowed outlet pressure set by `CH_SET_PMIN` (the simulation's lower limit, `MIN_POUT` or `CHOKE_POUT`); the block errors (BLKSTAT 1) with the outlet at that bound (seen at 10 % opening).
- **Fix**: Open the valve further (`Data.Blocks.{name}.Input.VAL_POSN`), give a larger Cv or SIZE, or lower the bound.

## NO VALID SOLUTION FOR VALVE

### Valve — required flow coefficient beyond the fully open valve

- **Block type**: Valve (SET-PRESSURE)
- **Cause**: The Cv needed for the specified drop is above the valve's fully open Cv (a 5 atm BTX vapor through a 2-IN globe valve with a 1 atm drop reported 99.6 % open).
- **Fix**: Choose a larger `Data.Blocks.{name}.Input.SIZE` (or a larger maximum or table Cv), or allow a larger drop.

### Valve — rated valve too small for a gas feed

- **Block type**: Valve (CALC-PRESSURE)
- **Cause**: No valid pressure drop: the opening or Cv is too small for the vapor flow even at the lowest allowed outlet pressure (seen at 10-20 % opening).
- **Fix**: Increase the opening (`Data.Blocks.{name}.Input.VAL_POSN`) or the valve size.

## NON-THERMAL OPTION SPECIFIED

### Pipe — pure-component feed with a temperature profile

- **Block type**: Pipe
- **Cause**: A one-component feed with `TYPE` T-CONST (the default) or T-SPEC and a two-phase flash ends with BLKSTAT 2.
- **Fix**: Use `NPHASE=1` with a PHASE, or `Data.Blocks.{name}.Input.TYPE` ADIABATIC or THERMAL.

## BLOCK IS IN MASS IMBALANCE

### Pipe — inlet pressure calculated without an outlet temperature

- **Block type**: Pipe
- **Cause**: `PRES_CALC=INLET` with `P_OUT` but no `T_OUT` (`OPT_OUTLET=VALUES`) fails with BLKSTAT 1.
- **Fix**: Give `Data.Blocks.{name}.Input.T_OUT` too, or use `OPT_OUTLET=STREAM` with the product stream's conditions given.

### ChargeBal — rescaling the ions changes the mass flow

- **Block type**: ChargeBal
- **Cause**: The block scales cation and anion flows by different factors, so outlet mass differs from inlet mass, and with the global mass-balance check on (the default) the block ends at BLKSTAT 1.
- **Fix**: Set `Data.Setup.Sim-Options.Input.MASS_BAL_CHE` to NO; a wider `MASS_BAL_TOL` (0.5) also cleared it (see `blocks/chargebal.md`).

### User2 — no model subroutine named

- **Block type**: User2
- **Cause**: `USRMODEL` and `EXCEL_FILE` are both empty, so nothing is called and the outlets stay at zero flow (BLKSTAT 2, BALMAS.1, with a hint to check the user subroutine).
- **Fix**: Set `Data.Blocks.{name}.Input.USRMODEL` to the exported name, or `EXCEL_FILE` for an Excel model.

## MAXIMUM NUMBER OF STEPS REACHED

### Pipe — packed bed too long for the inlet pressure

- **Block type**: Pipe (`PACKED_BED=YES`)
- **Cause**: The bed drop over 100 m x 0.1 m with 5 mm particles exceeds the inlet pressure, and the integration gives up (BLKSTAT 1).
- **Fix**: Shorten the bed (`Data.Blocks.{name}.Input.LENGTH`) or enlarge the diameter or particles (1-2 m beds converged).

## PRESSURE BELOW 0

### Pipeline — the line uses up the inlet pressure

- **Block type**: Pipeline (seen in solids conveying, a 100 m lift at 2 atm inlet)
- **Cause**: Friction, elevation and acceleration drops add up to more than the inlet pressure partway along a segment (BLKSTAT 1).
- **Fix**: Raise the inlet pressure (feed or `Data.Blocks.{name}.Input.P_INLET`), shorten the lift or segment, widen `INNERD`, or lower the flow or solids loading.

## DIED WHILE CALCULATING FLUID PROPERTIES

### Pipeline — Hazen-Williams with the efficiency left at its default

- **Block type**: Pipeline (`INTEGRATION=NO`, `CL_FORM_METH=HAZEN-WILL`)
- **Cause**: `EFFICIENCY` is read as the Hazen-Williams C factor; its default of 1 makes the friction drop thousands of times too large, so the pressure goes negative and the property call fails.
- **Fix**: Set `Data.Blocks.{name}.Input.EFFICIENCY.{seg}` to the pipe's C factor (about 100-150) on every segment.

## SPECIFIED STREAM PRESSURE IS LESS THAN THE LOWER LIMIT

### Pump — positive power on a WS(IN) work stream
- **Block type**: Pump
- **Cause**: +2 kW on the work stream into `WS(IN)` counts as power taken out (brake power -2 kW). The outlet pressure goes below zero (UPC01I.2) and the block ends with BLKSTAT 1.
- **Fix**: Give the work stream's `\Data\Streams\{id}\Input\POWER` negative: -2 kW drives the pump with 2 kW (see `blocks/pump.md`, `streams/streams-heat-work.md`).

# Mixers, splitters, separators and manipulators

## INLET FLOW OF KEY IS ZERO

### FSplit — key group with no components

- **Block type**: FSplit
- **Cause**: `BASIS_KEYNO\{stream}` points at a key group whose list `COMPS\{n}\MIXED` is empty, usually because the component was written as a row label (refused as not a valid value) or the substream row is missing; BLKSTAT 1 and the outlet gets 0.
- **Fix**: Insert a row on `Data.Blocks.{name}.Input.COMPS.{n}` labelled MIXED, then a row on `COMPS\{n}\MIXED`, and write the component ID as that row's value (see `blocks/fsplit-key-components.md`).

## SUM OF SPLITS SPECIFIED IS ILLEGAL

### SSplit — specified flows exceed the substream's feed

- **Block type**: SSplit
- **Cause**: One substream's specified flows add up to more than its feed (BLKSTAT 1). A common way in: only the `FLOW_BASIS` keyword was set to MASS, so 500 meant as kg/hr ran as 500 kmol/hr.
- **Fix**: Write `Data.Blocks.{name}.Input.BASIS_FLOW` with set_value `basis='MASS'` and a mass unit (it sets `FLOW_BASIS` too), and keep each substream's specified flows below its feed.

## UNABLE TO CONVERGE THE MATERIAL BALANCE EQUATIONS

### Sep2 — outlet flow in the wrong basis, or specs larger than the feed

- **Block type**: Sep2
- **Cause**: A stream `FLOW` meant as kg/hr or cum/hr ran as kmol/hr, because the engine follows `FLOW_BASIS` beside it; or a stream flow is smaller than what its component specs already send to that outlet.
- **Fix**: Write `Data.Blocks.{name}.Input.FLOW.MIXED.{stream}` with set_value, a unit and `basis='MASS'` (or `'STDVOL'`): the reply should end with `FLOW_BASIS` = that basis "as well". Check that the specs fit inside the feed.

## CMPT FLOW SPECIFICATION EXCEEDS FEED FLOW

### Sep2 — component flow larger than that component's feed

- **Block type**: Sep2
- **Cause**: A `FLOWS` value is above the component's feed flow (BLKSTAT 2), typically a mass number run as molar because only the `FLOWBASIS` keyword was set to MASS.
- **Fix**: Write `Data.Blocks.{name}.Input.FLOWS` with set_value, a mass unit and `basis='MASS'` (it sets `FLOWBASIS` too), and keep it below the component's feed.

## OUTLET AT -173.15 C

### Swash — NPHASE 1 PHASE V left adiabatic

- **Block type**: Swash (`NPHASE` 1, `PHASE` V)
- **Symptom**: The outlets read -173.15 C (the lower temperature limit) with vapor fraction 1, and the block fails (BLKSTAT 1).
- **Cause**: With every phase forced to vapor and no `TEMP` or `DUTY`, the adiabatic balance on liquid feeds drives the outlet down to the temperature floor.
- **Fix**: Give `Data.Blocks.{name}.Input.TEMP` at which the stream really is vapor (150 C at 1 atm ran for water/methanol); a temperature below the dew point (25 C) still ends in BLKSTAT 2.

## IN CHARGE IMBALANCE

### Sep — component fractions split the ions unevenly

- **Block type**: Sep (any block that splits ions by component)
- **Cause**: Giving one ion its own split fraction leaves the outlets with unequal positive and negative charge; BLKSTAT 2.
- **Fix**: Split counter-ions together (the same `Data.Blocks.{name}.Input.FRACS` for both), or follow the outlet with a ChargeBal block (see `blocks/chargebal.md`).

## FEED NOT IN CHARGE BALANCE

### ChargeBal — inlet imbalance above the tolerance

- **Block type**: ChargeBal
- **Cause**: The inlet imbalance exceeds `TOL` with `MESSAGE` WARNING (BLKSTAT 2) or ERROR (BLKSTAT 1); it is judged relative, or absolute when the charge flow is below `CUTOFF`. The outlet is balanced either way.
- **Fix**: Raise `Data.Blocks.{name}.Input.TOL`, raise `CUTOFF` so small flows are judged absolutely, or use MESSAGE NONE or INFORMATION.

## NOT IN MASS BALANCE

### ClChng — feed substream missing from the outlet class

- **Block type**: ClChng
- **Cause**: The outlet's stream class lacks a substream that carries flow in the feed (e.g. calcite in CISOLID, outlet class CONVEN). The block drops it with a warning, then reports the block out of mass balance (BLKSTAT 1).
- **Fix**: Give the outlet a class with every substream that has flow (a `Data.Flowsheet.Def-Streams.Input.SCLASS` row, or `\Data\Setup\Global\Input\SCLASS`; see `blocks/clchng.md`), or separate the solids before the class change.

## CANNOT MEET SPECIFICATIONS

### Makeup — no outlet total given

- **Block type**: Makeup
- **Cause**: Composition targets were set without `OUTMLFL` or `OUTMAFL` (or with OUTMAFL while `BASIS` is MOLE), so there is no total to aim for; Aspen reports insufficient makeup material and then a zero total flow (UMKU01.1010).
- **Fix**: Set the outlet total and make `BASIS` match it: MOLE with `Data.Blocks.{name}.Input.OUTMLFL`, MASS with `OUTMAFL`.

### Makeup — more varied flows than targets, or a purge asked to fix composition

- **Block type**: Makeup
- **Cause**: With `VARY_PURGE=YES` the purge counts as one more varied flow, so two makeups plus the purge against a total and one composition is one unknown too many (BLKSTAT 2, UMKU01.1000). The purge leaves at the outlet composition, so it can only trim the total.
- **Fix**: Give one independent target per varied flow (the total plus fractions for all components but one); drop a makeup feed from `FM(IN)` or set `Data.Blocks.{name}.Input.VARY_PURGE` to NO.

## EXCEEDS BOUND

### Makeup — bound below the makeup the targets need

- **Block type**: Makeup
- **Cause**: A `MOLEFLOW` or `MASSFLOW` bound on an SID row, or the purge bound, is lower than the flow the targets need. The flow is not capped; the run only warns (BLKSTAT 2, UMKU01.2000 or .2010).
- **Fix**: Raise the bound (`Data.Blocks.{name}.Input.MOLEFLOW`) or remove the row, or change the targets if they are wrong.

## REQUESTED ALLOCATION WITH LENGTH LE ZERO

### QTVec — load-port streams left in the heat class

- **Block type**: QTVec
- **Cause**: The streams on `LS(IN)` / `LS(OUT)` are plain heat streams, so the load vector has no points (ALLOCR.1 in the history file); no block gets results.
- **Fix**: Put those streams in the LOAD class: insert a row on `Data.Flowsheet.Def-Streams.Input.H_SCLASS` set to LOAD, then add each stream ID as a row of `H_SLIST\#0`. The stream's own `H_SCLASS` is not enough (see `blocks/qtvec.md`).

### STEP-GROWTH — set with no functional groups

- **Block type**: Reaction set (STEP-GROWTH)
- **Cause**: Only `POLYMER` was given: with no groups (`Input\TYPE`), group counts (`Input\NUMBER`), rate-constant sets and reaction sets, input translation stops on the reactions paragraph.
- **Fix**: Enter the groups, counts, rate-constant sets and reaction sets (see `reactions/reactions-step-growth.md`).

## NO PHASE SPLITTING OCCURS AT GIVEN SPECIFICATIONS

### Decanter — the feed forms only one liquid at the block's T and P
- **Block type**: DECANTER
- **Cause**: no second liquid exists at the block's temperature and pressure (seen: benzene/toluene without water at 25 C, 1 atm). The block warns and ends with BLKSTAT 2: the whole feed leaves on L1(OUT), L2(OUT) is empty and LIQ_RATIO is 1. L2_COMPS / L2_CUTOFF do not change it.
- **Fix**: check the feed for a second liquid first: a Flash3 at the same T and P ends with BLKSTAT 0, and LIQ_RATIO 1 with an empty L2(OUT) means one liquid. Change the feed (e.g. enough water), T/P or the property method, or use a Flash2 / Heater when one liquid is expected.

# Solids

## SIZE REDUCTION RATIO

### Crusher — impact or hammer mill breaks nothing

- **Block type**: Crusher (IMPACT-MILL, HAMMER-MILL, Vogel models)
- **Cause**: The Vogel inputs let no particle break: `VOGEL_WMIN` written without a unit is read in cal/gm (4184 times too high, also warning that the impact velocity is too low), or `VOGEL_C` is so large that fragments stay at their parent size.
- **Fix**: Write `Data.Blocks.{name}.Input.VOGEL_WMIN` in J/kg and `VOGEL_FMAT` in kg/J-m, and lower `VOGEL_C` (0.01 sec/m with `VOGEL_D` 0.1 gave a ratio of about 4 at 20 m/s).

## FAILED TO FIND OUTLET DIAMETER

### Crusher — BOM type sized by specific power

- **Block type**: Crusher (BOM types, `BREAKFN_OPT1=POWER`)
- **Cause**: The search for the product size matching `MASS_POWER` failed (0.8-1 kWhr/ton on about 1 t/hr of calcite in a gyratory, BLKSTAT 1; 0.3 converged).
- **Fix**: Lower `Data.Blocks.{name}.Input.MASS_POWER`, give `POWER_SPEC` with `BREAKFN_OPT1=SPEC`, or size the product by DIAM.

## GGS PARAMETER 'N' MUST BE GREATER

### Crusher — GGS distribution left at its default

- **Block type**: Crusher (`PSD_CALC_MET=POWER`, `DISTR_FUN=GGS`)
- **Cause**: `GGS_N` keeps its default of 1e-7, and the run stops with BLKSTAT 1.
- **Fix**: Set `Data.Blocks.{name}.Input.GGS_N` (0.5 ran) or choose another `PW_GGSINP` input (DIAM, D50 or D63).

## STANDARD DEVIATION MUST BE BETWEEN

### Crusher — normal distribution with a spread out of range

- **Block type**: Crusher (`PSD_CALC_MET=POWER`, `DISTR_FUN=NORMAL`)
- **Cause**: `STDDEV` is outside the range the block can fit for the median it derives from the power (1 mm failed where the range was 2.7-6.1 mm).
- **Fix**: Use a `Data.Blocks.{name}.Input.STDDEV` inside the range the message gives.

## WITHIN THE SMALLEST SIZE INTERVAL

### Crusher — product finer than the mesh

- **Block type**: Crusher (POWER method, BALL-MILL, ROD-MILL)
- **Cause**: Too much power for the throughput (50 kW on 1 t/hr) puts the whole product in the first mesh interval (BLKSTAT 2).
- **Fix**: Lower the power (`Data.Blocks.{name}.Input.POWER_SPEC`), or give the stream-class PSD mesh finer intervals at small sizes.

## PRESSURE DROP IS ZERO

### Classifier — sifter left at the default pressure drop

- **Block type**: Classifier (METHOD SIFTER)
- **Cause**: `PDROP` defaults to 0, and every sifter type then ends with a warning (BLKSTAT 2).
- **Fix**: Set `Data.Blocks.{name}.Input.PDROP` above 0 (e.g. 0.01 bar), or `PDROP_OPT=VEL-FUNCTION` with its coefficients.

## IMPELLER WHEEL HEIGHT TO RADIUS

### Classifier — impeller wheel out of proportion

- **Block type**: Classifier (TYPE IMP-SHORTCUT)
- **Cause**: Wheel height over radius outside 1 to 2 gives a warning (BLKSTAT 2); a cut velocity far from what the wheel can reach pushes a computed geometry out of that range.
- **Fix**: Keep `Data.Blocks.{name}.Input.WHEEL_HEIGHT` / `WHEEL_RADIUS` between 1 and 2; with CVHE-SPED or CVRA-SPED pick a cut velocity close to the one HERA-SPED gives for that wheel.

## CRYSTALLIZATION STOICHIOMETRY IS NOT AVAILABLE

### Crystallizer — no stoichiometry row

- **Block type**: Crystallizer (`SOL_METHOD` SOLUBILITY or SOLUB-FUN)
- **Cause**: Row 1 of the stoichiometry is empty; the block does not derive the crystallization reaction from the solubility data.
- **Fix**: Set `Data.Blocks.{name}.Input.STOIC_CID1.1` to the solute, `STOIC_SSID1\1` to CISOLID or CIPSD and `COEF1\1` = 1; insert a row on `COEF\1` labelled with the solute and set `COEF\1\{solute}\MIXED` = -1.

## NEITHER CHEMISTRY NOR SOLUBILITY DATA

### Crystallizer — empty solubility table

- **Block type**: Crystallizer (`SOL_METHOD=SOLUBILITY`)
- **Cause**: There are no `SOLUB_TEMP` / `SOLUB_CONCEN` rows, and the block is also flagged incomplete.
- **Fix**: Insert rows on `Data.Blocks.{name}.Input.SOLUB_TEMP` (this adds the SOLUB_CONCEN rows) and fill both.

## PROBLEM IN PSD CALCULATION

### Crystallizer — PSD copied from a feed without crystals

- **Block type**: Crystallizer (stream class with CIPSD)
- **Cause**: `OPT_PSD=COPY` (the default) takes the outlet distribution from the crystals in the feed; a clear feed has none (BLKSTAT 2).
- **Fix**: Use `Data.Blocks.{name}.Input.OPT_PSD` SPEC (a distribution) or GROWTH (`VOL` + `KBO`) on the first crystallizer of a train.

### Crystallizer — distribution parameter that does not belong to the function

- **Block type**: Crystallizer (`OPT_PSD=SPEC`)
- **Cause**: `SPEC_OVOPT` accepts every code with every `OV_DISTFUN`, but the parameter families belong to their functions: NORMAL with a `GMV` code (e.g. D50GMV) and LOG-NORMAL with an `SV` code (e.g. D50SV) each ended in a block error (BLKSTAT 1).
- **Fix**: Pair the `SV` codes (`OV_STDDEV`) with NORMAL and the `GMV` codes (`OV_GMDEV`) with LOG-NORMAL in `Data.Blocks.{name}.Input.SPEC_OVOPT`.
- **Diagnostic note**: The block error's own message was not recorded; this entry sits with the other PSD-specification failures.

### Crystallizer — tabular outlet PSD on the global mesh

- **Block type**: Crystallizer (`OPT_OVERALL=TABULAR`)
- **Cause**: With `OV_MESHOPT=PREDEF` the block stays incomplete and warns that the outlet PSD reference is missing.
- **Fix**: Set `Data.Blocks.{name}.Input.OV_MESHOPT` LOCAL with rows on `USER_OVLOWER` (which adds the `USER_OVUPPER` and `USER_OVVALUE` rows).

## GROWTH RATE CALCULATION FAILED

### Crystallizer — nucleation constant far too small

- **Block type**: Crystallizer (`OPT_PSD=GROWTH`)
- **Cause**: `KBO` 1e10 (1 m3, `BNI` = `BNJ` = 1, adipic acid) failed the growth-rate solve together with the PSD calculation; 1e14 converged.
- **Fix**: Change `Data.Blocks.{name}.Input.KBO` by orders of magnitude; in the nucleation law the magma density is in kg/l and the agitator speed in rev/s.

## CRYSTAL PRODUCT FLOW RATE WAS NOT MET

### Crystallizer — product rate with no way to reach it

- **Block type**: Crystallizer
- **Cause**: `PROD_RATE` is met by evaporating solvent: at 1 atm a cooling case could not boil, and with `TEMP` fixed a target below the cooling yield cannot be met either.
- **Fix**: Pair `Data.Blocks.{name}.Input.PROD_RATE` with a vacuum pressure (0.1 atm ran), or with TEMP and a target above the cooling yield.

## CRYSTALS FORMED FOR A DISSOLVING MODE

### Crystallizer — MODE DISSOLVE

- **Block type**: Crystallizer
- **Cause**: `MODE=DISSOLVE` ends with this warning (BLKSTAT 2) even when the crystals do dissolve; `SALT_IN` NO makes no difference.
- **Fix**: Use `Data.Blocks.{name}.Input.MODE` EITHER, which gives the same result with BLKSTAT 0.

## FLASH FAILURE DURING CALCULATION

### Crystallizer — only one operating spec

- **Block type**: Crystallizer
- **Cause**: Only `TEMP` was given; the block is flagged incomplete and the flash fails.
- **Fix**: Give two of `TEMP`, `PRES`, `DUTY`, `BASIS_FLOWV`, `PROD_RATE` (e.g. add `Data.Blocks.{name}.Input.PRES`).

## SOLUTION OF POPULATION BALANCE FAILED

### Granulator — Litster exponent above 4

- **Block type**: Granulator (AGGLOMERATIO)
- **Cause**: `LITSTER_Q` 5 or 6 makes the agglomeration solver fail; the outlets fall back and the block ends with BLKSTAT 1.
- **Fix**: Keep `Data.Blocks.{name}.Input.LITSTER_Q` at the default 4 or lower.

## SAUTER-DIAMETER AT OUTLET IS SMALLER

### Granulator — given outlet PSD finer than the seeds

- **Block type**: Granulator (USER-SPEC)
- **Cause**: The given distribution has a Sauter mean below the seeds' (e.g. GGS with `OV_DIAM` 1500 um and a small exponent); BLKSTAT 2.
- **Fix**: Choose parameters that give a coarser product (adjust `Data.Blocks.{name}.Input.OV_DIAM` or a larger exponent).

## HEIGHT OF FREEBOARD SMALLER

### FluidBed — vessel shorter than the transport disengaging height

- **Block type**: FluidBed
- **Cause**: The freeboard is shorter than the TDH, from the solids profile or from the chosen `TDH_MODEL` (seen at 3 m height with ERGUN or GELDART-D, and with FOURNOL at 30 kmol/hr gas in a 0.6 m bed); BLKSTAT 2.
- **Fix**: Raise `Data.Blocks.{name}.Input.HEIGHT` above `Output\TDH_FROM_PROF` / `TDH_FOM_CORR`, lower the gas rate, or choose another TDH_MODEL.

## TYPE OTHER THAN ISOTHERMAL NOT SUPPORTED

### FluidBed — temperature profile option

- **Block type**: FluidBed (V15)
- **Cause**: `TYPE=TEMP-PROF` can be written, but the engine copies the inlets to the outlets and stops (BLKSTAT 1).
- **Fix**: Use `Data.Blocks.{name}.Input.TYPE` ISOTHERMAL with `TEMP_OPT` SPETEMP or INLETTEMP plus DUTY.

## NEGATIVE EVAPORATION RATE

### Dryer — feed water not in the solid substream

- **Block type**: Dryer (SHORTCUT)
- **Cause**: The feed water is in MIXED, or no moisture component is defined, so the solids carry no moisture and the outlet moisture spec makes the block add water (BLKSTAT 2).
- **Fix**: Insert H2O into `Data.Components.Moisture-Comps.Input.COMP` and give the feed water as `FLOW\CIPSD\H2O`.

## FILL GRADE IS NOT SPECIFIED

### Dryer — volume-based geometry without a fill grade

- **Block type**: Dryer (CONVECTIVE, `SPEC_OPT=VL`)
- **Cause**: `VOLUME` and `LENGTH` were given but `FILL_GRADE` is empty, so input translation stops and the run never starts.
- **Fix**: Set `Data.Blocks.{name}.Input.FILL_GRADE` (a percentage of the volume).

## INVALID GEOMETRY INPUT SPECIFIED

### Dryer — counter- or co-current dryer without a length-based spec

- **Block type**: Dryer (CONVECTIVE, `FLOW_DIR` COUNTERCURRE or COCURRENT)
- **Cause**: `SPEC_OPT` ST, SH, AST or VST; these flow directions need `LENGTH` plus one of volume, area, solids residence time or solids velocity.
- **Fix**: Use `Data.Blocks.{name}.Input.SPEC_OPT` VL, LA, LST or LSV, or `FLOW_DIR=CROSSFLOW`, which accepts ST, SH and AST.

## INLET PRESSURE OF THE SPRAY TOO LOW

### Dryer — spray feed at the dryer pressure

- **Block type**: Dryer (SPRAY)
- **Cause**: The liquid feed is no higher than the gas inlet pressure, so the nozzle has no driving pressure; the droplet size calculation fails next (BLKSTAT 1).
- **Fix**: Raise the liquid feed pressure upstream (5 atm into a 1 atm dryer ran).

## LIQUID FLOW AT SPRAY INLET IS ZERO

### Dryer — spray fed with wet solids instead of a liquid

- **Block type**: Dryer (SPRAY)
- **Cause**: All the water is moisture in the solid substream, but the spray model needs liquid in MIXED; the calculation is bypassed with a warning.
- **Fix**: Feed the water as liquid in MIXED (a slurry or solution).

## ERROR SOLVING DIFFERENTIAL EQUATION SYSTEM

### Dryer — user droplet distribution without a start velocity

- **Block type**: Dryer (SPRAY, `DSD_CALC_MET=USER-SPEC`)
- **Cause**: `DROP_VEL_INI` is empty; a drag-coefficient extrapolation warning comes first, then the mass and energy balance fails.
- **Fix**: Set `Data.Blocks.{name}.Input.DROP_VEL_INI` (1e-5 m/s ran).

## TWO FLUID NOZZLE MODEL REQUIRES ATOMIZATION AIR

### Dryer — two-fluid atomizer without atomizing gas

- **Block type**: Dryer (SPRAY, `ATOMIZER=TWO-FLUID`)
- **Cause**: No stream on `G2(IN)`, so input translation stops.
- **Fix**: Connect an atomizing gas stream to `G2(IN)`.

## ROTARY ATOMIZER MODEL NOT WITHIN MODEL SCOPE

### Dryer — wheel rim speed outside 180-300 m/s

- **Block type**: Dryer (SPRAY, `ATOMIZER=ROTARY`)
- **Cause**: pi x `WHEEL_DIAM` x `WHEEL_SPEED` is below the valid range (a 0.2 m wheel at 10000 rpm gives 105 m/s); warning only (BLKSTAT 2).
- **Fix**: Raise `Data.Blocks.{name}.Input.WHEEL_SPEED` or `WHEEL_DIAM` (0.2 m at 24000 rpm ran clean).

## EQUILIBRIUM BETWEEN GAS AND SOLID

### Dryer — contact dryer at equilibrium with a gas inlet

- **Block type**: Dryer (CONTACT, `OPT_HEATTRAN=EQUIL`)
- **Cause**: The equilibrium option is allowed only while `GAS(IN)` is empty; the block is bypassed (BLKSTAT 1).
- **Fix**: Disconnect `GAS(IN)`, or use `Data.Blocks.{name}.Input.OPT_HEATTRAN` COEFF with `ALPHAG`.

## UNKNOWN OR UNDEFINED BEAD NUMBER

### Dryer — batch operation

- **Block type**: Dryer (`BATCH_OP=YES`, V15)
- **Cause**: Every batch setup tried (crossflow, counter-current, batch feed or charge, with discharge and down times) raises a system error (ATLOOK.1); the cause inside the engine is unknown.
- **Fix**: None found; model the batch as a continuous crossflow dryer with `Data.Blocks.{name}.Input.SPEC_OPT` SH, as the V15 batch drying example does.

## INLET VELOCITY IS HIGHER THAN CORRELATION LIMITATION

### Cyclone — inlet velocity above 30 m/s

- **Block type**: Cyclone (any METHOD except MUSCHELKNAUT)
- **Cause**: The gas flow per cyclone over the inlet area of the chosen `TYPE` and `DIAM` gives more than 30 m/s (69 m/s at 0.5 m); the run warns (BLKSTAT 2).
- **Fix**: Raise `Data.Blocks.{name}.Input.DIAM` (0.8 m gave 27 m/s) or `NCYCLONE`, or pick a type with a larger inlet; check `Output\IN_VELOC`.

## PRESSURE DROP IS ABOVE MAXIMUM

### Cyclone — design target needs more drop than allowed

- **Block type**: Cyclone (`MODE=DESIGN`)
- **Cause**: The target `EFF` (0.99) needs a drop above `MAX_PDROP` (0.005 bar); the block errors (BLKSTAT 1) and does not add parallel cyclones.
- **Fix**: Raise `Data.Blocks.{name}.Input.MAX_PDROP` or lower `EFF`.

## BELOW THE LOWER PRESSURE LIMIT

### HyCyc — Nageswararao pressure-drop constant too small

- **Block type**: HyCyc (METHOD NAGESWARARAO)
- **Cause**: The KQ constant sets the drop for the given flow; a small value (1) gave a drop of thousands of bar, above the feed pressure, and the block errors (BLKSTAT 1) and falls back to an ideal split.
- **Fix**: Raise `Data.Blocks.{name}.Input.CONST_KQ0` (300 gave about 0.15 bar for 0.25 L/s in a 0.1 m cyclone), add cyclones in parallel (`NCYCLONE`), or change the geometry.

## VOLUME FLOW OF OVERFLOW IS 0

### HyCyc — Doheim flow split sends all liquid to the underflow

- **Block type**: HyCyc (METHOD MOD-BRAUN, `FSPLT_MODE=DOHEIM`)
- **Cause**: On a concentrated slurry (about 50 wt % solids) the Doheim correlation gives no overflow (BLKSTAT 2).
- **Fix**: Use another `Data.Blocks.{name}.Input.FSPLT_MODE`; MODER-DAHL (the default), YOSHIOKA, ABBOTT, TARJAN and PLITT converged.

## WASH FLUID PRESSURE NEEDS TO BE LARGER

### VScrub — spray liquid not above the gas pressure

- **Block type**: VScrub (SPRAY)
- **Cause**: The nozzles atomize the `L(IN)` liquid, so liquid at the gas pressure gives BLKSTAT 1.
- **Fix**: Feed the liquid above the gas pressure (3 against 1.2 atm ran).

## INVALID OPERATION OPTIONS

### VScrub — Yung design throat limits impossible for the gas flow

- **Block type**: VScrub (VENTURI, DESIGN, YUNG)
- **Cause**: The largest reachable throat velocity is below `MIN_VEL` because the default `MIN_DIAM` of 0.15 m is too big for a small gas flow; the block is bypassed (BLKSTAT 2).
- **Fix**: Lower `Data.Blocks.{name}.Input.MIN_DIAM` (0.05 m ran) or `MIN_VEL`.

## DESIRED SEPARATION EFFICIENCY CANNOT BE REACHED

### VScrub — spray design target out of reach at the given relative velocity

- **Block type**: VScrub (SPRAY, DESIGN, `SAUDIAM_OPT=SPEREGAVE`)
- **Cause**: At a fixed `REL_GAS_VEL` the efficiency has a ceiling (0.15 at 3 m/s).
- **Fix**: Raise `Data.Blocks.{name}.Input.REL_GAS_VEL`, lower `EFF`, or use CALSAUDIAM or SPESAUDIAM.

## DESIGN DROPLET DIAMETER IS HIGHER

### VScrub — design droplet larger than one nozzle gives

- **Block type**: VScrub (SPRAY, DESIGN, `CALC_NOZZLES=YES`)
- **Cause**: `DROP_DIA` is above the single-nozzle droplet (about 290 um).
- **Fix**: Use a smaller `Data.Blocks.{name}.Input.DROP_DIA` (200 um gave 3 nozzles).

## GAS VELOCITY IS OUTSIDE ITS TYPICAL RANGE

### ESP — lane gas velocity outside 0.15-5 m/s

- **Block type**: ESP
- **Cause**: Flow over `HT_PLATE` x pack width (2 x `PLATE_WIRE` x (`NPLATE` - 1)) gives a lane velocity outside 0.15-5 m/s.
- **Fix**: Change `Data.Blocks.{name}.Input.NPLATE`, `HT_PLATE` or `PLATE_WIRE`.

## PLATE HEIGHT IS NOT WITHIN USUAL RANGE

### ESP — plate height out of proportion to the pack width

- **Block type**: ESP
- **Cause**: `HT_PLATE` is outside 0.3-3 times the pack width.
- **Fix**: Add plates (`Data.Blocks.{name}.Input.NPLATE`) or lower `HT_PLATE`.

## GAS VELOCITY IS LESS THAN MINIMUM

### ESP — Crawford lane velocity below the minimum

- **Block type**: ESP (CRAWFORD)
- **Cause**: The lane velocity is below `MIN_VEL` (default 0.5 m/s); DEUTSCH does not check it.
- **Fix**: Use fewer or lower plates, or lower `Data.Blocks.{name}.Input.MIN_VEL`.

## INITIAL GUESS FOR GAS VELOCITY

### ESP — Crawford design start velocity outside its bounds

- **Block type**: ESP (CRAWFORD, DESIGN)
- **Cause**: `GAS_VEL` (default 2) is outside `MIN_VEL` to `MAX_VEL`.
- **Fix**: Set `Data.Blocks.{name}.Input.GAS_VEL` inside that range.

## GAS VELOCITY BOUNDS ARE NOT REASONABLE

### ESP — Crawford design size limits too small for the flow

- **Block type**: ESP (CRAWFORD, DESIGN)
- **Cause**: `MAX_HT` x `MAX_WIDTH` is too small to pass the flow at `MAX_VEL`.
- **Fix**: Loosen `Data.Blocks.{name}.Input.MAX_HT` / `MAX_WIDTH` or raise `MAX_VEL`.

## GAS VELOCITY IS OUTSIDE THE MINIMUM/MAXIMUM RANGE

### FabFl — cloth velocity outside its limits

- **Block type**: FabFl (SIMULATION, or DESIGN FROM-BAGHOUS)
- **Cause**: Gas volume over the area in service ((`NCELLS` - `NCLEAN`) x `NBAGS` x `AREA`) gives a velocity below `MIN_VEL` (0.00254 m/s) or above `MAX_VEL` (0.0254 m/s); BLKSTAT 2.
- **Fix**: Change `Data.Blocks.{name}.Input.NCELLS`, `NBAGS` or `AREA` (or `VEL_OPT=FROM-AREA` with `FILTER_AREA`) until `Output\VELOCITY` is in range, or widen the limits.

## FILTER MEDIUM SELECTION INVALID

### FabFl — filter system and medium do not go together

- **Block type**: FabFl (DESIGN, `AREA_OPT=FROM-ACRATIO`)
- **Cause**: The coefficient model has only SHAKER or JET-VENTURI with BAGS / POCKETS, and DIRECT-PULSE with SINGLE-BAG / MULTI-BAG; other pairs stop with BLKSTAT 1.
- **Fix**: Pick a `Data.Blocks.{name}.Input.FILTER_MED` that matches `FILTER_SYS`.

## FILTRATION VELOCITY HIGHER THAN MAXIMUM

### FabFl — pressure-drop design solved for the filtering time

- **Block type**: FabFl (DESIGN, `AREA_OPT=FROM-PDROP`)
- **Cause**: With `CALCULATE=TIME` both area and filtering time are free, and the design returned under 1 m2 at tens of m/s.
- **Fix**: Use `Data.Blocks.{name}.Input.CALCULATE` PRESSURE with `FILT_TIME` (30-10000 s) and `AVG_PDROP` (0.005-0.05 bar); a lower AVG_PDROP or longer FILT_TIME lowers the velocity.

## ELEMENTS IN THE REFERENCE VECTOR ARE MISSING

### FabFl — tabular efficiency without table rows

- **Block type**: FabFl (`EFF_OPT=TABULAR`)
- **Cause**: No `DIAM_PART` / `EFFIC` rows; the run still reports BLKSTAT 0 but catches nothing (all dust in `G(OUT)`).
- **Fix**: Insert rows on `Data.Blocks.{name}.Input.DIAM_PART` and fill `DIAM_PART\#i` and `EFFIC\#i` across the feed size range.

## EFFICIENCY EVALUATED IS OUT OF BOUND

### FabFl — efficiency table does not span the feed sizes

- **Block type**: FabFl (`EFF_OPT=TABULAR`, LINEAR)
- **Cause**: Points only from 1 to 10 um on a 0-20 um feed; the extrapolated efficiencies left 0 to 1 and were clipped (BLKSTAT 2).
- **Fix**: Add `Data.Blocks.{name}.Input.DIAM_PART` points down to the smallest and up to the largest feed size.

## FITTING OF SEPARATION FUNCTION FAILED

### FabFl — fitting interpolation with no model chosen

- **Block type**: FabFl (`EFF_OPT=TABULAR`, `INTERPOLATE=FITTING`)
- **Cause**: All of `OPT_PLITT`, `OPT_ROGERS`, `OPT_WHITEN`, `OPT_MOLERUS`, `OPT_FABFLEXP` were left NO; the block falls back to linear and warns.
- **Fix**: Set at least one of them (e.g. `Data.Blocks.{name}.Input.OPT_PLITT`) to YES; `Output\BESTFIT` gives the one used.

## SOLIDS VOLUME CONCENTRATION AT INLET

### CFuge — pusher fed a thin slurry

- **Block type**: CFuge (`TYPE=PUSHER`)
- **Cause**: The inlet solids volume fraction is below 0.3 (0.29 for calcite at 10 kmol/hr in 50 kmol/hr water); BLKSTAT 2.
- **Fix**: Thicken the feed upstream (30 kmol/hr water ran clean), or use a decanter or disc-stack type (`Data.Blocks.{name}.Input.TYPE`) for dilute slurries.

## MAXIMUM FLOWRATE IS LESS THAN THE FILTRATE

### CFuge — basket cake resistance estimated from defaults

- **Block type**: CFuge (`TYPE=PERF-BASKET`)
- **Cause**: With only `MEDIUM_RES` given, the estimated cake passes too little filtrate for every basket row; the block continues with the best row and also warns of zero total flow (BLKSTAT 2).
- **Fix**: Set `Data.Blocks.{name}.Input.CAKE_RES` and `DIAM_PART` (1e9 m/kg and 30 micron ran clean), or add larger or faster basket rows.

## RESIDENCE TIME IS ZERO

### CFuge — decanter with Redeker deliquoring

- **Block type**: CFuge (`TYPE=DECANTER`, `DEC_DELIQ=REDEKER`)
- **Cause**: The smallest complete input set gives no beach residence time (BLKSTAT 1); adding `BEACH_RESTIM` and the other screw fields made the run return no status at all.
- **Fix**: Not resolved for REDEKER; use `Data.Blocks.{name}.Input.DEC_DELIQ` STADAGER (it converges once the screw and beach fields are set) or STAHL.

## CALCULATED CAKE THICKNESS UNUSUAL

### Filter — drum too large or too fast for the solids load

- **Block type**: Filter (`TYPE=DRUM`, SIMULATION)
- **Cause**: 1 t/h of solids on a 2 m x 2 m drum at 1 rpm gave a 0.9 mm cake, below the usual 3-15 mm (BLKSTAT 2).
- **Fix**: Size the drum to the load (`Data.Blocks.{name}.Input.DIAM` 1 m, `WIDTH` 1 m, `REVS` 0.5 rpm gave 7 mm and BLKSTAT 0).

## AREA FILTRATION TOO SMALL

### Filter — compressible-cake resistance factor too high

- **Block type**: Filter (`COMP_MODEL=COMP-A`)
- **Cause**: `COMPA_KA` 1e10 (with `COMPA_NA` 0.3) failed the filtration simulation (BLKSTAT 1).
- **Fix**: Lower `Data.Blocks.{name}.Input.COMPA_KA` (1e9 with COMPA_NA 0.2 converged); `COMPA_NE` must stay below 1 or the write is refused.

## WASH LIQUID FLOW TOO LOW

### Filter — design washing target with no dissolved contaminant

- **Block type**: Filter (`MODE=DESIGN`, DRUM or BELT)
- **Cause**: The feed liquid was pure water, so the `CONTAM_REDFA` washing target can never be reached.
- **Fix**: Put a dissolved component in the feed liquid and use a reachable target (`Data.Blocks.{name}.Input.CONTAM_REDFA` 0.1 ran; 0.5 still warned).

## CAKE SATURATION REDUCED DUE TO EVAPORATION

### Filter — drum washing without a gas inlet

- **Block type**: Filter (`TYPE=DRUM` with wash streams)
- **Cause**: With wash streams only, the deliquoring step dried the cake by evaporation (BLKSTAT 2).
- **Fix**: Also connect a gas inlet and a deliquoring outlet and set `Data.Blocks.{name}.Input.DELIQ_ANGLE` (60 deg ran). For `TYPE=BELT` see the next entry.

### Filter — belt washing at the deliquoring pressure difference

- **Block type**: Filter (`TYPE=BELT`, wash stream on `F2(IN)`)
- **Cause**: `WASH_PDROP` equal to `DELIQ_PDROP`: the cake drains fully in the wash zone, no liquid leaves in deliquoring and only evaporation lowers the saturation (FILTER.339, BLKSTAT 2, "no liquid output from dewatering").
- **Fix**: Set `Data.Blocks.{name}.Input.WASH_PDROP` below `DELIQ_PDROP` (0.2 against 0.6 bar converged).

## LIQUID PHASE IN CAKE COMPLETELY VAPORIZED

### Filter — disc in DESIGN mode

- **Block type**: Filter (`TYPE=DISC`, `MODE=DESIGN`, gas on `F2(IN)`)
- **Cause**: Not found: the designed disc dries the cake completely (`CAKE_SFRAC` 1, FILTER.537) for every target saturation, thickness, geometry, deliquoring model and gas humidity tried; the same disc in SIMULATION mode converges.
- **Fix**: None known; rate a given disc (`Data.Blocks.{name}.Input.MODE` SIMULATION) and adjust its size by hand.

## CALCULATED FILTERAREA LOWER THAN 0.5 M2

### Filter — design with the computed cake resistance

- **Block type**: Filter (`MODE=DESIGN`)
- **Cause**: Without `CAKE_RES_H` the computed resistance gave a 0.15 m2 drum, often with a drum-speed warning too.
- **Fix**: Give `Data.Blocks.{name}.Input.CAKE_RES_H` (1e14 1/m2 with `CAKE_THICK` 8 mm gave 5 m2 at 0.28 rpm, BLKSTAT 0).

## TOTAL AREA LOWER THAN 5 M2

### Filter — disc filter with too few discs

- **Block type**: Filter (`TYPE=DISC`)
- **Cause**: `NDISC` 2 with a 1 m outer radius (BLKSTAT 2).
- **Fix**: Raise `Data.Blocks.{name}.Input.NDISC` (4 ran).

## DID NOT SPECIFY % SOLID IN CAKE

### Filter — Brownell model without the cake solids fraction

- **Block type**: Filter (`MODEL=BROWNELL`)
- **Cause**: `SOLID_FRAC` is blank, so it is computed and the run warns (BLKSTAT 2).
- **Fix**: Set `Data.Blocks.{name}.Input.SOLID_FRAC` (0.8 ran).

## PERMEATE OUTLET PRESSURE BELOW AMBIENT

### CFFilter — feed pressure not above the drop plus ambient

- **Block type**: CFFilter (TYPE PLATE or CAPILLARY)
- **Cause**: The permeate leaves at the feed pressure minus `PDROP`; with a 1 atm feed and a 1 bar drop it would fall below ambient (BLKSTAT 2). The block's `PRES` does not change this.
- **Fix**: Raise the feed pressure (3 bar ran), or lower `Data.Blocks.{name}.Input.PDROP` so feed pressure minus PDROP stays above 1 atm.

## PERMEATE FLOW GREATER THAN LIQUID FLOW

### CFFilter — membrane flux times area exceeds the feed liquid

- **Block type**: CFFilter (`MODEL=ALTMANN`, SIMULATION)
- **Cause**: The computed flux times the membrane area is larger than the feed liquid (`FILTER_RES` 1e11 1/m on 0.63 m2 for 900 kg/hr water); the block caps the permeate and warns.
- **Fix**: Raise `Data.Blocks.{name}.Input.FILTER_RES` (1e12 converged) or reduce the area (`MODULE_NUM`, `NUM_CHANNEL`, `CAP_NUM`), or use `MODE=DESIGN` with `CONC_FACTOR` so the block sizes the module count.

# Batch blocks

## INTEGRATION FAILED

### BatchOp — rigorous heat transfer without a vessel size or a medium

- **Block type**: BatchOp
- **Cause**: `HTRANMODE=RIGOROUS` without `GEOMETRYSPEC` and the pot size, or a jacket or coil that is on without its medium; the cooling jacket is on by default (`JKCOLMODE` 1) with no `JKCOLMEDT`.
- **Fix**: Give the vessel size (`Data.Blocks.{name}.Input.POTVOL` or `POTDIAM` / `POTLENGTAN`), and set `JKCOLMEDT` (or `JKCOLMODE` 0) and the medium of every device that is on.

## LIQUID VOLUME HAS REACHED

### BatchOp — vessel too small for the charge

- **Block type**: BatchOp
- **Cause**: The vessel from the geometry (e.g. 10 cum) cannot hold the charged liquid (100 kmol benzene/toluene is about 10 cum at 25 C).
- **Fix**: Enlarge `Data.Blocks.{name}.Input.POTVOL` (or `POTDIAM` / `POTLENGTAN`), or charge less.

## BUBBLE POINT CALCULATIONS CANNOT BE PERFORMED

### BatchSep — inert-filled start with a total condenser

- **Block type**: BatchSep
- **Cause**: `INITIALCOND` CHARGE or EMPTY fills the column with the inert gas (e.g. N2), above its critical temperature; with a TOTAL condenser the initialization tries to condense it and fails, followed by an internal error.
- **Fix**: Use `Data.Blocks.{name}.Input.CONDENSER` PARTIAL (checked with T 50 C), or start with `INITIALCOND=TOTAL`.

## BLOCK IS UNDER SPECIFIED

### BatchSep — shortcut heat transfer

- **Block type**: BatchSep
- **Cause**: `H_TRANS_MODE=SHORTCUT` with `HT_SPEC=DUTY` and `HT_DUTY` set still leaves the block under-specified by 2, and it is bypassed (UDL15I.1), with or without a pot duty changed variable.
- **Fix**: Use the default DETAILED mode (`Data.Blocks.{name}.Input.H_TRANS_MODE`) with jacket heating (`JH_OPT`) and a heating changed variable in each step.

## INTERNAL ERROR

### BatchSep — pot size missing

- **Block type**: BatchSep
- **Cause**: The pot diameter `D` and length `L` are empty on a fresh block; the run ends with an internal error and the block not converged, with nothing pointing to the cause.
- **Fix**: Set `Data.Blocks.{name}.Input.D` and `L` (or `V` with `GEOMETRYSPEC` DV or LV).

# Setup, utilities and streams

## COMPONENT WATER MUST BE SELECTED

### Utility — steam or water utility in FLASH mode without WATER

- **Block type**: Utility (used by any block: e.g. RadFrac, MultiFrac, PetroFrac `COND_UTIL` / `REB_UTIL`, `UTILITY_ID`)
- **Cause**: A STEAM or WATER utility with `CALOPT` FLASH is evaluated with the component WATER; without it in the components list input translation stops (UTLCHK.1), no block runs and Run-Status never appears. No stream has to carry water.
- **Fix**: Add WATER to the components, or use `CALOPT` DUTY with `COOLING_VALU` (see `utilities/utilities.md`).

## EITHER CO2 EMISSION FACTOR OR FUEL COMPOSITION MUST

### Utility — CO2 tracking left on without a factor

- **Block type**: Utility (used by any block: seen on RadFrac and PetroFrac condenser and reboiler utilities)
- **Cause**: A new utility starts with `CALCCO2` YES; without `CO2FACTOR` or a fuel composition input translation stops (UTLCHK.2) and the run does not start.
- **Fix**: Write `\Data\Utilities\{id}\Input\CALCCO2` NO, or give `CO2FACTOR`.

## VAPOR FRACTION IS MISSING

### Utility — FLASH mode with only a temperature at an end

- **Block type**: Utility
- **Cause**: Each end of a FLASH-mode utility needs two state values; `TIN` / `TOUT` without `PRES` / `PRES_OUT` leave the flash under-specified. The utility ends with errors and the block gets no utility rate.
- **Fix**: Give `\Data\Utilities\{id}\Input\PRES` and `PRES_OUT` (for steam, a pressure plus a vapor fraction at each end).

## HEATING/COOLING VALUE NOT SPECIFIED IN UTILITY

### Utility — DUTY mode without a heating value

- **Block type**: Utility
- **Cause**: DUTY mode (the default `CALOPT`) sizes the utility from its heating or cooling value; with only `TIN` / `TOUT` and no value the block that uses it warns (BLKSTAT 2, also "UTILITY RATE NOT CALCULATED") and computes no rate or cost. A MultiFrac condenser or reboiler utility left this way lost all the column's results, duties included.
- **Fix**: Give `\Data\Utilities\{id}\Input\COOLING_VALU` (positive for heating, negative for cooling), or use `CALOPT` FLASH with both end states (water: `TIN`, `PRES`, `TOUT`, `PRES_OUT`; steam: `PRES` + `VFRAC` 1, `PRES_OUT` + `VFRAC_OUT` 0).

## CONSISTENCY PROBLEM WITH UTILITY

### Utility — heating value sign does not match the duty

- **Block type**: Utility
- **Cause**: A positive `COOLING_VALU` marks a heating utility; on a cooler the block warns that the utility can only heat (BLKSTAT 2).
- **Fix**: Give a cooling utility a negative `\Data\Utilities\{id}\Input\COOLING_VALU`.

## TEMPERATURES CROSS WITH UTILITY

### Heater — outlet hotter than the utility

- **Block type**: Heater (any block with `UTILITY_ID`)
- **Cause**: The block's temperatures cross the utility's (a heater to 180 C on 4 bar steam at 143.6 C); the block ends with an error (BLKSTAT 1, UOSSTAT2 9).
- **Fix**: Assign a hotter utility in `Data.Blocks.{name}.Input.UTILITY_ID`, or lower the outlet temperature.

## MUST EITHER INCLUDE "NC-COMPS" FOR NC-TYPE SUBSTREAMS

### Setup — stream class with an NC substream but no nonconventional component

- **Block type**: Setup (`Global\Input\SCLASS`)
- **Cause**: `SCLASS` MIXNC, MIXNCPSD, MIXCINC or MCINCPSD adds an NC substream; with no nonconventional component the run does not start.
- **Fix**: Use CONVEN, MIXCISLD or MIXCIPSD in `\Data\Setup\Global\Input\SCLASS`, or add a nonconventional component.

## VALUE IS REQUIRED FOR TERTIARY KEYWORD: PARTICLESIZE

### Setup — generated PSD mesh without GMESH

- **Block type**: Setup (PSD mesh)
- **Cause**: `TYPE` EQUIDISTANT, GEOMETRIC or LOGARITHMIC with `LOWER` / `UPPER` leaves the interval rows empty; the run does not start.
- **Fix**: Write `\Data\Setup\Stream-Class\Subs-Attr\PSD\Input\GMESH` YES (see `setup/setup-streams.md`).

## HAS TWO DESTINATIONS

### Streams — IDs longer than 8 characters or with `_`

- **Block type**: Stream
- **Cause**: The input file cuts stream IDs to 8 characters (and at a `_`). IDs that cut to the same text, or to a keyword such as IN, break the flowsheet and the run does not start; a cut ID that stays unique runs, but that stream gets no results.
- **Fix**: Rename the streams to at most 8 letters, digits or `-` (see `setup/setup.md`, IDs).

## SOLVENT ID SHOULD BE SPECIFIED

### Stream — concentrations entered without the BASIS code

- **Block type**: Stream
- **Cause**: The values were written with basis MOLE-CONC or MASS-CONC, but `Input\BASIS\MIXED` still reads MOLE-FLOW, so `SOLVENT` is not written to the input file (STSTRM.21) and input translation stops.
- **Fix**: Write `\Data\Streams\{id}\Input\BASIS\MIXED` with the same concentration code, and `Input\SOLVENT\MIXED` with the solvent (see `streams/streams.md`).

## ARE NORMALIZED TO THE TOTAL

### Stream — TOTFLOW given with component flows

- **Block type**: Stream
- **Cause**: `TOTFLOW` is set while the component values are flows, so the flows are scaled to the total (STSTRM.29 warning).
- **Fix**: Give fractions with `\Data\Streams\{id}\Input\TOTFLOW\MIXED`, or clear `TOTFLOW` so the flows count as entered.

## STREAM ATTRIBUTE "LOAD" HAS NOT BEEN DEFINED

### Heat stream — class LOAD set on the stream alone

- **Block type**: Stream (HEAT)
- **Cause**: `H_SCLASS` LOAD is set on the stream, but the problem defines no LOAD attribute (GTKWT5.1); translation stops.
- **Fix**: Keep the stream's `H_SCLASS` at HEAT. A load stream for QTVec is set through `\Data\Flowsheet\Def-Streams` instead (see REQUESTED ALLOCATION WITH LENGTH LE ZERO and `blocks/qtvec.md`).

## INCONSISTENT FREE WATER SETTING DETECTED

### Stream — free water on a stream into a block without it

- **Block type**: Stream
- **Cause**: Input-check warning PRPCHK.2: the stream says `FREE_WATER` YES and the block it feeds says NO.
- **Fix**: Set the block's free-water option too, or leave `\Data\Streams\{id}\Input\FREE_WATER\MIXED` at NO (see `streams/streams-options.md`).

### Any block — free water on in the block, feed stream left at the global NO

- **Block type**: any block with `BLKOPFREWAT` YES or DIRTY (seen on DSTWU and MCompr)
- **Cause**: Input-check warning PRPCHK.2: the feed stream takes the global setting (NO) and is flashed without free water while the block uses it. The run still goes ahead and BLKSTAT does not change.
- **Fix**: Set the feed stream's `\Data\Streams\{id}\Input\FREE_WATER\MIXED` to the block's value, or turn free water on globally (`\Data\Setup\Main\Input\FREE_WATER`); when only the block needs free water the warning can be ignored.

## UTLCHK.2

### MultiFrac — a utility left with CALCCO2 at its default
- **Block type**: MultiFrac (seen also on PetroFrac and RadFrac)
- **Cause**: a new utility starts with CALCCO2 YES and no CO2 factor, so input translation stops ("... must be specified when calculating CO2 emissions") and the run never starts.
- **Fix**: write `\Data\Utilities\{id}\Input\CALCCO2` = `NO` (or give `CO2FACTOR`).

## HEATING/COOLING VALUE NOT SUPPLIED BY UTILITY

### MultiFrac — utility on COND_UTIL / REB_UTIL with CALOPT left at its default
- **Block type**: MultiFrac
- **Cause**: CALOPT defaults to DUTY, which needs a heating value; none was given, so the block ends with BLKSTAT 2 and no utility cost or duty.
- **Fix**: set `CALOPT` `FLASH` with both end states (water TIN/PRES and TOUT/PRES_OUT; steam PRES + VFRAC 1 and PRES_OUT + VFRAC_OUT 0), or give `COOLING_VALU` in DUTY mode.

# Properties, chemistry and reaction sets

## CHEMISTRY NOT CONVERGED

### Chemistry — only A of an equilibrium constant written

- **Block type**: Chemistry
- **Cause**: After `create_chemistry`, set_value wrote `Input\A\{n}` alone; B, C and D stayed empty, so ln K = A and the reaction ran far to one side. Water ionized almost completely, the flash failed ("flash calculations failed to converge") and the streams went out of charge balance.
- **Fix**: Write `A`, `B`, `C` and `D` of `\Data\Reactions\Chemistry\{id}\Input` together, give `keq` in `create_chemistry`, or leave all four empty for the Gibbs route (see `properties/properties-chemistry.md`).

## UNABLE CREATE OBJECT

### Reaction set — type EQUILIBRIUM

- **Block type**: Reaction set
- **Cause**: EQUILIBRIUM is not a reaction-set type; `add_element` / `add_reaction_set` with it fails.
- **Fix**: Create a POWERLAW, LHHW or REAC-DIST set and set the reaction's `REACTYPE` to EQUIL, or use a GENERAL set (see `reactions/reactions-equilibrium.md`).

## "STOIC" SENTENCE NOT COMPLETE

### SEGMENT-BAS — products entered with the reactants

- **Block type**: Reaction set (SEGMENT-BAS)
- **Cause**: `Input\COEF\{n}` holds reactants only and stores every coefficient negative, so a product written there becomes a reactant; the reaction then also fails its mass balance ("does not satisfy mass balance").
- **Fix**: Put products on `\Data\Reactions\Reactions\{id}\Input\COEF1\{n}\{comp}` (see `reactions/reactions-segment-based.md`).

# Convergence and sequencing

## WILL NOT RUN BECAUSE OF ERRORS FOUND DURING FLOWSHEET ANALYSIS

### Sequence — a user sequence leaves out a block of the loop

- **Block type**: Sequence
- **Cause**: The sequence holds the convergence block but not every block that computes its tear stream (AF2MER.3); the tear stream is then computed outside the loop (AFLSPC.29) and the run does not start (IAPFAN.1).
- **Fix**: Add the missing block between the BEGIN and RETURNTO rows of `\Data\Convergence\Sequence\{id}\Input\BLOCK_ID`, or delete the sequence. `Conv-Options\Input\CHECKSEQ` NO only silences the check (see `convergence/convergence-sequence.md`).

## NOT CONVERGED IN 60 ITERATIONS

### Convergence (COMPLEX) — evaluation limit too low for the optimization

- **Block type**: Convergence block (COMPLEX)
- **Cause**: The default 60 flowsheet evaluations ran out before the tolerances were met; the block ends with BLKSTAT 1 and the optimization with status 1.
- **Fix**: Give the optimization its own COMPLEX block and raise `\Data\Convergence\Convergence\{id}\Input\MAXIT` (300 converged in 114), or use SQP or BOBYQA (`Conv-Options\Input\OPT_METHOD`; see `convergence/convergence-optimization.md`).

# Flowsheeting options and model analysis

## COMPLETED WITH WARNINGS

### Design-Spec — target outside what the varied input can reach

- **Block type**: Design-Spec
- **Cause**: The target cannot be met within the vary limits; the spec, its convergence block (`$OLVER02`) and the block downstream all end with BLKSTAT 2.
- **Fix**: Give a reachable target, or widen `\Data\Flowsheeting Options\Design-Spec\{id}\Input\LOWER` / `UPPER` (see `flowsheeting/design-spec.md`).

## ILLEGAL EXECUTABLE STATEMENT IN CALCULATOR BLOCK

### Calculator — a Fortran line it cannot parse

- **Block type**: Calculator
- **Cause**: A `FORTRAN_EXEC` row such as `      FLT = 80.0 + * X` stops input translation (EXECMP.3); the run does not start.
- **Fix**: Correct the statement: one statement per row, starting in column 7 (see `flowsheeting/calculator.md`).

## UNKNOWN PKW - INPUT IGNORED TO NEXT PKW

### Calculator — Fortran line starting in column 1

- **Block type**: Calculator
- **Cause**: A `FORTRAN_EXEC` row without its six leading spaces is read as an input keyword (ITSORT.1); the run does not start.
- **Fix**: Begin every Fortran line after six spaces.

## NOT FOUND IN SEQUENCE

### Calculator — no read/write lists and no WHEN

- **Block type**: Calculator
- **Cause**: With neither `READ_VAR` / `WRITE_VAR` nor `WHEN`, flowsheet analysis cannot place the calculator (AMONIT.4) and the run does not start.
- **Fix**: List the variables it reads and writes, or set `WHEN` (with `BLOCK_TYPE` and `BLK_ID` for BEFORE / AFTER).

## MUST BE FOLLOWED BY A VARIABLE TYPE

### Transfer — source written in the field of another copy mode

- **Block type**: Transfer
- **Cause**: With `OPT_COPY` ENTSTRM the source went into `EQ_STREAM` (the SUBSTRM source), so the EQUAL-TO sentence is empty (BLDSNT.11; AISEN.3/.5/.6); the run does not start.
- **Fix**: ENTSTRM: `EQ_STRM1` -> `SET_STRM1` rows; STRM: `EQ_FLOWS` -> `SET_FLOWS` rows; SUBSTRM: `EQ_STREAM` + `EQ_SUB` -> `SUB_SUB` rows labelled with the target stream (see `flowsheeting/transfer.md`).

## NOT ENOUGH SENTENCES FOR BLOCK

### Transfer — SUBSTRM target put in SET_STRM1

- **Block type**: Transfer
- **Cause**: A SUBSTRM transfer with its target in `SET_STRM1` has no SET sentence (AISEN.6).
- **Fix**: One `SUB_SUB` row per target: insert_row + set_label with the target stream, value = its substream.

## YOU NEED TO SPECIFY EITHER BLOCKS OR (INLETS AND OUTLETS)

### Balance — stream written on the list's row instead of an entry

- **Block type**: Balance
- **Cause**: `INLETS\#0` / `OUTLETS\#0` refuse a value (AE_UNDERSPEC), so the lists stay empty (BALSM1.1, then BALSM1.3).
- **Fix**: insert_row on `Input\INLETS\#0`, then write `Input\INLETS\#0\#0`; the same for `OUTLETS`, `BLOCKS` and `COMPS` (see `flowsheeting/balance.md`).

## COMPS IS REQUIRED WITH FLOW = COMPS

### Balance — FLOW COMPS without CALC_COMPS

- **Block type**: Balance
- **Cause**: A calculate row with `FLOW` COMPS and no `CALC_COMPS` entry (BALCAL.4).
- **Fix**: insert_row on `Input\CALC_COMPS\#0` and write `CALC_COMPS\#0\#0` (ALL or a component).

## NUMBER OF VARIABLES AND EQUATIONS ARE DIFFERENT

### Balance — component flows computed from a total mass balance

- **Block type**: Balance
- **Cause**: `FLOW` COMPS with `CALC_COMPS` ALL gives one unknown per component, but a mass balance without `COMPS` gives one total equation (BALSM1.3).
- **Fix**: Add `COMPS\#0\#0` = ALL to the mass balance.

## A STREAM FLOW MAY HAVE BEEN CHANGED BY A CALCULATOR, TRANSFER, BALANCE

### Balance — computed stream feeds a block that already ran

- **Block type**: Balance
- **Cause**: The balance set a makeup stream after the block using it had run (that block ordered first, or the balance left at its default and run at the start of a loop whose stream it reads); that block ends with BLKSTAT 1 (mass balance error).
- **Fix**: Place the balance after the block that makes the streams it reads and before the blocks that use the stream it computes: `WHEN` AFTER with `BL_TYPE` BLOCK and `BLOCK_ID`.

## CONVERGED TO WITHIN SPECIFIED ABSOLUTE FUNCTION

### Data-Fit regression — absolute tolerance larger than the sum of squares near the fit

- **Block type**: Data-Fit regression
- **Cause**: With the default `AFCTOL` 0.01 the fit stops on that tolerance; the regression ends with BLKSTAT 2 and Run-Status lists it as completed with warnings (seen on a point fit and a profile fit, with the estimate already right).
- **Fix**: Set `\Data\Model Analysis Tools\Data-Fit\Regression\{id}\Input\AFCTOL` well below the expected sum of squares (1e-10 converged clean), or make the `STD-DEV` rows match the measurement scale (see `analysis/data-fit-regression.md`).

## CONVERGENCE BLOCKS WERE COMPLETED WITH ERRORS

### Optimization — objective badly scaled

- **Block type**: Optimization
- **Cause**: The objective `(VF-40)**2` (about 14 at the start) stopped Aspen's default SQP block with errors (BLKSTAT 1, optimization status 1).
- **Fix**: Scale the objective to order 1, e.g. `(VF-40)**2/100`, which converged (see `analysis/optimization.md`).

# Server tools (elements, optimize, pinch, workbench)

## NODE NOT FOUND

### set_value — the node is not created yet

- **Block type**: any (set_value)
- **Cause**: set_value only writes a node that exists; a list row, a block subobject or a new object must be created first.
- **Fix**: insert_row (then set_label for a labelled list), add_element on the folder or `Subobjects\<collection>`, or the object's own tool; then set_value. list_elements on the parent shows what exists (see `mcp/elements.md`).

## ALREADY EXISTS

### add_element — the name is taken

- **Block type**: any (add_element, place_block, place_stream)
- **Cause**: The folder already holds that name in any case (block and stream names are upper-cased), or a block is named like an existing Design-Spec, Calculator, Transfer or Measurement.
- **Fix**: Use another name, or remove_element the old one first.

### Workbench proposal — steps of a partly applied run run again

- **Block type**: Workbench proposal
- **Cause**: A proposal that ended partly applied or failed is approved again with its finished place / connect steps still on; the check refuses them (`exists`).
- **Fix**: Revise it (applied steps start turned off, `proposal.ran`), use Continue from step N, or turn those steps off (see `mcp/workbench/proposals.md`).

## ASPEN CRASHES ON A BLOCK NAMED LIKE

### Flowsheet — block named like a Design-Spec, Calculator, Transfer or Measurement

- **Block type**: any block
- **Cause**: A block that takes the name of an existing flowsheeting object crashes Aspen; place_block refuses it and the workbench check reports `clash`.
- **Fix**: Pick another block name.

## REFUSES A STREAM INTO ITS OWN BLOCK

### connect_stream — refused loop connect already detached the stream end

- **Block type**: any block
- **Cause**: In V15 connecting a stream to a port of the block its other end is on is refused, but the end has already been taken off its old port; the workbench check reports `loop` and the journal records the detach.
- **Fix**: Connect the stream to the intended port again, or use the recorded undo.

## NOT FOUND ON BLOCK

### connect_stream, disconnect_stream — wrong port name

- **Block type**: any block
- **Cause**: "Port '<port>' not found on block '<block>'": the name is not a port of that block type (case is ignored).
- **Fix**: discover_ports(session, block_types=['<Type>']).

## IT IS NOT ON

### disconnect_stream — the stream is not on the named port

- **Block type**: any block
- **Cause**: The stream is on another port; the reply lists what is on the named one.
- **Fix**: Name the right port, or give stream_name alone.

## OUT OF RANGE (COUNT=

### remove_row — the index is past the end

- **Block type**: any list (remove_row)
- **Cause**: The index is not one of the current rows (0-based).
- **Fix**: list_elements on the list, then remove_row with a listed index.

## AE_UNKERR

### insert_row — two-index table fails at the third row (aspen-mcp before the insert_row fix)

- **Block type**: insert_row on RYield `Input\MOLE_YIELD` (RStoic `COEF\{id}` the same)
- **Cause**: The older insert_row inserted at `Elements.Count`, which on a two-index table is rows x columns (4 after two components), so the third insert ran past the end.
- **Fix**: Update aspen-mcp: insert_row now inserts at the row count of the dimension and returns that index. On an old version, after one insert_row use set_label at the next index, which adds the row.

## SNAPSHOT(S) NOT FOUND

### diff_snapshot — the server restarted

- **Block type**: snapshot_tree / diff_snapshot
- **Cause**: Snapshots live only in the running server's memory.
- **Fix**: Take both snapshots again with snapshot_tree.

## GUI RULES: UNAVAILABLE

### check_inputs — rule texts could not be read from Aspen

- **Block type**: check_inputs
- **Cause**: Extracting the localization DLL of the Aspen that COM starts failed.
- **Fix**: `aspen-mcp --check` shows why; `aspen-mcp --extract-strings` retries; `ASPEN_LOCALIZATION_DLL` names the DLL by hand (see `mcp/check-inputs.md`).

## ISOTHERMAL NEEDS TYPE

### pinch_analysis, pinch_matches — an isothermal stream without a direction

- **Block type**: pinch_analysis
- **Cause**: `t_supply` equals `t_target` (a condenser or reboiler duty) and nothing says whether it gives or takes heat.
- **Fix**: Add `"type": "hot"` for a condenser, `"cold"` for a reboiler (see `mcp/pinch-analysis.md`).

## NO PINCH BACKEND AVAILABLE

### pinch_analysis, pinch_matches — neither uv nor the pinch venv

- **Block type**: pinch_analysis
- **Cause**: OpenPinch runs in a Python 3.14 subprocess that uv provides on first use; uv is not found.
- **Fix**: `winget install --id=astral-sh.uv -e`, then restart the MCP client.

## SLSQP OPTIMIZATION FAILED: 'ASPEN_PATH'

### optimize (gradient) — constraint given with aspen_paths

- **Block type**: optimize
- **Cause**: gradient reads each constraint by its `aspen_path`; a constraint given as `aspen_paths` + expression has none, so the call stops at the first evaluation.
- **Fix**: Give gradient constraints a single `aspen_path`, or use another method; all others take `aspen_paths` constraints (see `mcp/optimize/gradient.md`).

## RESUME CSV MISSING COLUMNS

### optimize (bo, cbo, afmcbo) — resume_from does not match the problem

- **Block type**: optimize
- **Cause**: CSV columns are named from the variables' last path segments (block-prefixed when two share one) and the objectives' labels; other variables or objectives, or a renamed column, leave names missing.
- **Fix**: Resume from the run folder and leave variables, objectives and constraints out so its config.json restores them; for a checkpoint folder (no config.json) pass exactly the original ones (see `mcp/optimize/bayesian.md`).

## CANCELLED BY USER

### optimize — progress window closed or Cancel pressed

- **Block type**: optimize
- **Cause**: Closing the progress window counts as Cancel; the run stops and keeps what it has.
- **Fix**: Run it again, or for bo / cbo / afmcbo resume from the run's folder or its checkpoint CSV.

## CONSECUTIVE COM ERRORS

### optimize — Aspen stopped answering

- **Block type**: optimize
- **Cause**: Three evaluations in a row failed with a COM error ("Aspen session may have crashed"); the run aborts with the points done so far.
- **Fix**: Close and reopen the model (open_aspen_plus), then run again or resume.

## QLOGNEHVI OPTIMIZATION FAILED

### optimize (bo, 2+ objectives) — the acquisition step raised

- **Block type**: optimize
- **Cause**: The BoTorch proposal failed; bo ends the call there and writes no files.
- **Fix**: Use cbo, which falls back to a random point when a proposal fails, or narrow the bounds.

## EXCEEDING MAX_POINTS

### optimize (grid) — grid too large

- **Block type**: optimize
- **Cause**: The product of the axis counts exceeds `max_points` (default 20000).
- **Fix**: Lower `points_per_dim` or a variable's points, or pass a larger `max_points` in options (see `mcp/optimize/grid.md`).

## FAILURE RATE > 30%

### optimize — many evaluations fail

- **Block type**: optimize
- **Cause**: The bounds reach regions where the flowsheet does not solve or a constraint cannot be met.
- **Fix**: Read `reason` / `error_detail` in evaluations.csv, narrow the bounds, and follow aspen-error-troubleshooting for the named blocks; with the optimum near the failing region use cbo or afmcbo.

## USER CANCELLED MCP TOOL CALL

### Codex — non-interactive exec cannot ask for a tool approval

- **Block type**: Codex client
- **Cause**: `codex exec` cancels an MCP call its approval policy would ask about ("requires approval, but approval policy is never").
- **Fix**: Give the server `default_tools_approval_mode = "approve"` under `[plugins."aspen-plus@aspen-mcp".mcp_servers.aspen-plus]` for the plugin's server; a server added by hand keeps `[mcp_servers.<name>]`.

## INVALID BLOCK/MODEL/LIBRARY SPECIFICATION

### place_block — block ID over 8 characters

- **Block type**: any (place_block)
- **Cause**: The block ID is longer than 8 characters or holds a character other than letters, digits and `-`. The block type is not the problem, although the reply's hint names the type.
- **Fix**: Use an ID of at most 8 letters, digits or `-` (see `setup/setup.md#ids`).
