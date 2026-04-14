# Sensitivity Analysis

Configure sensitivity analysis via `\Data\Model Analysis Tools\Sensitivity`.

## Setup Steps

### 1. Create Sensitivity block
```
add_element(session, '\Data\Model Analysis Tools\Sensitivity', 'S1')
```

### 2. Vary (manipulated variable)

Insert a row in the VARY table, then set values **in order**:
```
insert_row(session, '\Data\Model Analysis Tools\Sensitivity\S1\Input\VARY_VARTYPE')

set_value(session, aspen_path='\Data\...\VARY_VARTYPE\#0', value='BLOCK-VAR')
set_value(session, aspen_path='\Data\...\VARYBLOCK\#0', value='COL1')
set_value(session, aspen_path='\Data\...\VARYVARIABLE\#0', value='MOLE-RR')
set_value(session, aspen_path='\Data\...\LOWER\#0', value='0.1')
set_value(session, aspen_path='\Data\...\UPPER\#0', value='3')
set_value(session, aspen_path='\Data\...\NPOINT\#0', value='9')
```

One `insert_row` on any VARY field auto-expands all related VARY fields (VARYBLOCK, VARYVARIABLE, VARYSENTENCE, LOWER, UPPER, NPOINT, etc.).

#### VARY_VARTYPE values
| Value | Description |
|-------|-------------|
| BLOCK-VAR | Block variable |
| STREAM-VAR | Stream variable |
| PARAM-VAR | Parameter variable |

#### VARYVARIABLE examples (BLOCK-VAR)
| Variable | Description |
|----------|-------------|
| MOLE-RR | Mole reflux ratio |
| NSTAGE | Number of stages |
| FEED-STAGE | Feed stage |

**Note:** VARYSENTENCE is auto-set by Aspen after VARYVARIABLE is chosen (e.g. `COL-SPECS`). You typically do not need to set it manually.

### 3. Define (observed variable)

Insert a row in the FVN table, set label for variable name, then set values:
```
insert_row(session, '\Data\...\FVN_VARTYPE')

set_label(session, '\Data\...\FVN_ID1', 0, 'AAA')

set_value(session, aspen_path='\Data\...\FVN_VARTYPE\#0', value='MOLE-FLOW')
set_value(session, aspen_path='\Data\...\FVN_STREAM\#0', value='BOTTOMS')
set_value(session, aspen_path='\Data\...\FVN_SUBS\#0', value='MIXED')
set_value(session, aspen_path='\Data\...\FVN_COMPONEN\#0', value='ETHANOL')
```

#### FVN_VARTYPE values
| Value | Description |
|-------|-------------|
| MOLE-FLOW | Mole flow |
| MASS-FLOW | Mass flow |
| MOLE-FRAC | Mole fraction |
| MASS-FRAC | Mass fraction |
| TEMP | Temperature |
| PRES | Pressure |

#### FVN key fields
| Field | Description |
|-------|-------------|
| FVN_ID1 | Variable name (set via `set_label`, not `set_value`) |
| FVN_VARTYPE | Variable type |
| FVN_STREAM | Stream name |
| FVN_BLOCK | Block name (for block variables) |
| FVN_SUBS | Substream (e.g. `MIXED`) |
| FVN_COMPONEN | Component name |

### 4. Tabulate

Insert a row in EXPR, set its label to a column number, then set value to the define variable name:
```
insert_row(session, '\Data\...\EXPR')
set_label(session, '\Data\...\EXPR', 0, '1')
set_value(session, aspen_path='\Data\...\EXPR\1', value='AAA')
```

For multiple columns, repeat with label `'2'`, `'3'`, etc.

## Gotchas

- **VARY tables have no labels** — only use `insert_row`, do NOT call `set_label` on VARY fields.
- **FVN_ID1 uses labels** — the variable name is set via `set_label`, not `set_value`.
- **EXPR uses labels** — column number is the label (e.g. `'1'`), value is the define variable name.
- **Set VARY values in order** — `VARY_VARTYPE` first, then `VARYBLOCK`/`VARYSTREAM`, then `VARYVARIABLE`. Aspen validates each field against the previous ones.
- **One `insert_row` expands all** — inserting on one VARY field auto-creates `#0` in all sibling VARY fields. Same for FVN fields.
- **VARYSENTENCE auto-populates** — after setting VARYVARIABLE, Aspen fills VARYSENTENCE automatically.

## Full Path Reference

All paths below are under `\Data\Model Analysis Tools\Sensitivity\{name}\Input\`.

### Vary fields (indexed by `#0`, `#1`, ...)
`VARY_VARTYPE`, `VARYBLOCK`, `VARYSTREAM`, `VARYVARIABLE`, `VARYSENTENCE`, `VARYCOMPONEN`, `VARYSUBS`, `LOWER`, `UPPER`, `NPOINT`, `INCR`

### Define fields (indexed by `#0`, `#1`, ...)
`FVN_VARTYPE`, `FVN_BLOCK`, `FVN_STREAM`, `FVN_VARIABLE`, `FVN_SUBS`, `FVN_COMPONEN`, `FVN_ID1`

### Tabulate
`EXPR` (indexed by label `1`, `2`, ...)

## Reading Results

All output paths are under `\Data\Model Analysis Tools\Sensitivity\{name}\Output\`.

### Key output nodes
| Node | Description |
|------|-------------|
| `BLKSTAT` | 0 = success |
| `ROWSTAT\{case}` | 0 = converged, non-zero = failed |
| `SENSVAR\{case}\{col}` | 2D table with vary values and tabulated results |
| `VALUE\{var_index}` | Base case value for each defined variable |
| `VARID\{var_index}` | Variable name (e.g. `AAA`) |

### SENSVAR structure

`SENSVAR` is a 2D table indexed by `\{case}\{column}`:
- **Column 1** = value of the varied variable for that case
- **Column 2** = value of the first tabulated expression (EXPR\1)
- **Column 3** = value of the second tabulated expression (EXPR\2), etc.

Cases are numbered `1` to `NPOINT + 1` (base case is included).

### Reading all results
```
# Loop over cases 1..10
for case in range(1, 11):
    get_value(session, aspen_path='\Data\...\Output\SENSVAR\{case}\1')  # vary value
    get_value(session, aspen_path='\Data\...\Output\SENSVAR\{case}\2')  # tabulated result
```

Or use `list_node_children` on `SENSVAR\{case}` to get all columns at once.
