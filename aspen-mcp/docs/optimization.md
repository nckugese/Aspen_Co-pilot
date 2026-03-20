# Built-in Optimization

Configure Aspen Plus built-in SQP optimization via `\Data\Model Analysis Tools\Optimization`.

## Overview

The built-in optimization uses:
- **Define** — variables read from the simulation (block outputs, stream properties)
- **Fortran** — compute the objective expression from defined variables
- **Vary** — manipulated variables with bounds
- **Constraints** — separate Constraint blocks linked to the optimization
- **Objective** — minimize or maximize a Fortran expression

## Setup Steps

### 1. Create Optimization block
```
add_element(session, '\Data\Model Analysis Tools\Optimization', 'O1')
```

### 2. Define (observed variables)

Insert a row on `FVN_VARIABLE` (auto-expands all FVN fields), then set label and values.

**Important:** Use `set_node_attribute(... attribute='VALUE')` for most FVN fields — `set_value` only works for `FVN_VARTYPE`.

#### BLOCK-VAR example (reboiler duty)
```
insert_row(session, '\Data\...\O1\Input\FVN_VARIABLE')
set_label(session, '\Data\...\O1\Input\FVN_VARIABLE', 0, 'DUTY')

set_value(session,      aspen_path='\Data\...\FVN_VARTYPE\DUTY', value='BLOCK-VAR')
set_node_attribute(session, '\Data\...\FVN_BLOCK\DUTY',    'VALUE', 'COL1')
set_node_attribute(session, '\Data\...\FVN_SENTENCE\DUTY', 'VALUE', 'RESULTS')
set_node_attribute(session, '\Data\...\FVN_VARIABLE\DUTY', 'VALUE', 'REB-DUTY')
```

**Order matters for BLOCK-VAR:** VARTYPE → BLOCK → SENTENCE → VARIABLE. Each field's option list depends on the previous fields.

#### FVN_VARTYPE values

| Value | Description | Key fields |
|-------|-------------|------------|
| BLOCK-VAR | Block variable | FVN_BLOCK, FVN_SENTENCE, FVN_VARIABLE |
| STREAM-VAR | Stream variable (mixture-level only) | FVN_STREAM, FVN_SUBS, FVN_VARIABLE |
| MOLE-FRAC | Stream component mole fraction | FVN_STREAM, FVN_SUBS, FVN_COMPONEN |
| MASS-FRAC | Stream component mass fraction | FVN_STREAM, FVN_SUBS, FVN_COMPONEN |
| MOLE-FLOW | Stream component mole flow | FVN_STREAM, FVN_SUBS, FVN_COMPONEN |
| MASS-FLOW | Stream component mass flow | FVN_STREAM, FVN_SUBS, FVN_COMPONEN |

> **MOLE-FRAC / MASS-FRAC** are the simplest way to access component purities. They do NOT require Fortran to compute ratios.

> **STREAM-VAR** only gives mixture-level properties (TEMP, PRES, MOLE-FLOW total, etc.) — no component selection available.

### 3. Fortran

Insert rows in `FORTRAN_EXEC` to compute the objective expression:
```
insert_row(session, '\Data\...\O1\Input\FORTRAN_EXEC')
set_value(session, aspen_path='\Data\...\FORTRAN_EXEC\#0',
          value='      TOTAL = DUTY + DUTY2')
```

Fortran code must start with 6 spaces (column 7) per Fortran 77 format.

Optional: `FORTRAN_DEC` for variable declarations.

### 4. Objective

```
set_node_attribute(session, '\Data\...\O1\Input\EXPR1', 'VALUE', 'TOTAL')
set_node_attribute(session, '\Data\...\O1\Input\MAX_MIN', 'VALUE', 'MINIMIZE')
```

| Field | Values |
|-------|--------|
| EXPR1 | Fortran variable name to optimize |
| MAX_MIN | `MINIMIZE` or `MAXIMIZE` |

### 5. Vary (manipulated variables)

Insert a row on any VARY field (auto-expands all). Use `set_node_attribute` for values:
```
insert_row(session, '\Data\...\O1\Input\VARYVARIABLE')

set_node_attribute(session, '\Data\...\VARY_VARTYPE\#0', 'VALUE', 'BLOCK-VAR')
set_node_attribute(session, '\Data\...\VARYBLOCK\#0',    'VALUE', 'COL1')
set_node_attribute(session, '\Data\...\VARYVARIABLE\#0', 'VALUE', 'MOLE-RR')
set_node_attribute(session, '\Data\...\LOWER\#0',        'VALUE', '0.5')
set_node_attribute(session, '\Data\...\UPPER\#0',        'VALUE', '5')
```

VARYSENTENCE auto-populates after VARYVARIABLE is set.

### 6. Constraints

Constraints are separate blocks under `\Data\Model Analysis Tools\Constraint`.

#### Create a Constraint block
```
add_element(session, '\Data\Model Analysis Tools\Constraint', 'C-1')
```

#### Define a constraint variable (e.g. purity)
```
insert_row(session, '\Data\...\C-1\Input\FVN_VARIABLE')
set_label(session, '\Data\...\C-1\Input\FVN_VARIABLE', 0, 'PURBZ')

set_value(session,      aspen_path='\Data\...\C-1\Input\FVN_VARTYPE\PURBZ', value='MOLE-FRAC')
set_node_attribute(session, '\Data\...\C-1\Input\FVN_STREAM\PURBZ',   'VALUE', 'BENZ')
set_node_attribute(session, '\Data\...\C-1\Input\FVN_SUBS\PURBZ',     'VALUE', 'MIXED')
set_node_attribute(session, '\Data\...\C-1\Input\FVN_COMPONEN\PURBZ',  'VALUE', 'BENZENE')
```

#### Set constraint spec
```
set_node_attribute(session, '\Data\...\C-1\Input\EXPR1', 'VALUE', 'PURBZ')
set_node_attribute(session, '\Data\...\C-1\Input\OPER',  'VALUE', 'GE')
set_node_attribute(session, '\Data\...\C-1\Input\EXPR2', 'VALUE', '0.9')
set_node_attribute(session, '\Data\...\C-1\Input\TOL',   'VALUE', '0.001')
```

| OPER values | Description |
|-------------|-------------|
| GE | Greater than or equal (≥) |
| LE | Less than or equal (≤) |
| EQ | Equal (=) |

#### Link constraints to optimization

Use `insert_row` on CONID, then `set_value`:
```
insert_row(session, '\Data\...\O1\Input\CONID')
set_value(session, aspen_path='\Data\...\O1\Input\CONID\#0', value='C-1')

insert_row(session, '\Data\...\O1\Input\CONID')
set_value(session, aspen_path='\Data\...\O1\Input\CONID\#1', value='C-2')
```

### 7. Run

```
run_simulation(session)
```

The optimization runs automatically when the simulation is executed.

## Reading Results

All output paths under `\Data\Model Analysis Tools\Optimization\{name}\Output\`.

| Node | Description |
|------|-------------|
| `BLKSTAT` | 0 = success |
| `OPTMETH` | Optimization method used (e.g. `SQP`) |
| `FINAL_VAL\{index}` | Final values of defined variables |
| `INIT_VAL\{index}` | Initial values of defined variables |

After optimization, block/stream outputs reflect the optimized state. Read results with `get_value` on the usual output paths.

## Gotchas

- **FVN fields require `set_node_attribute`** — most FVN fields reject `set_value` ("not enterable"). Only `FVN_VARTYPE` accepts `set_value`.
- **BLOCK-VAR order matters** — set VARTYPE → BLOCK → SENTENCE → VARIABLE. Each field's option list depends on the previous ones being set first.
- **MOLE-FRAC for purity** — use `MOLE-FRAC` type (not `STREAM-VAR`) to access component mole fractions directly. `STREAM-VAR` only provides mixture-level properties.
- **One `insert_row` expands all** — inserting on one FVN field auto-creates the row in all sibling FVN fields. Same for VARY fields. Do NOT insert on multiple FVN/VARY fields separately.
- **CONID needs `insert_row` first** — the constraint link table starts empty. Use `insert_row` then `set_value` to add constraint IDs.
- **Fortran column 7** — all Fortran code must start at column 7 (6 leading spaces).
- **VARYSENTENCE auto-populates** — do not set it manually.

## Full Path Reference

All paths below under `\Data\Model Analysis Tools\Optimization\{name}\Input\`.

### Objective
`EXPR1`, `MAX_MIN`

### Fortran
`FORTRAN_DEC` (declarations), `FORTRAN_EXEC` (executable code)

### Define fields (indexed by label)
`FVN_VARTYPE`, `FVN_BLOCK`, `FVN_STREAM`, `FVN_VARIABLE`, `FVN_SENTENCE`, `FVN_SUBS`, `FVN_COMPONEN`, `FVN_ATTRIB`, `FVN_ID1`, `FVN_ID2`, `FVN_ID3`, `FVN_PHYS_QTY`, `FVN_UOM`, `OPT_CATEG`

### Vary fields (indexed by `#0`, `#1`, ...)
`VARY_VARTYPE`, `VARYBLOCK`, `VARYSTREAM`, `VARYVARIABLE`, `VARYSENTENCE`, `VARYCOMPONEN`, `VARYSUBS`, `LOWER`, `UPPER`, `STEP_SIZE`, `MAX_STEP_SIZ`

### Constraint link
`CONID` (table of constraint block IDs)

### Constraint block paths
Under `\Data\Model Analysis Tools\Constraint\{name}\Input\`:
`EXPR1`, `OPER`, `EXPR2`, `TOL`, `FVN_VARTYPE`, `FVN_STREAM`, `FVN_SUBS`, `FVN_COMPONEN`, `FVN_BLOCK`, `FVN_VARIABLE`, `FORTRAN_DEC`, `FORTRAN_EXEC`
