# RadFrac — Advanced

See [common-advanced.md](common-advanced.md) for property method override, electrolyte, free-water, EO, utility, and CO2e tracking paths shared by all blocks.

## 3-Phase Setup

When the system contains immiscible liquids (e.g., water + organic), enable 3-phase mode:

1. Set number of phases: `set_value(session, aspen_path='\Data\Blocks\COL1\Input\NO_PHASE', value='3')`
2. Set stage range to test for two liquid phases (table node):
   ```
   insert_row(session, '\Data\Blocks\COL1\Input\TRAY2')
   set_label(session, '\Data\Blocks\COL1\Input\TRAY2', index=0, label='{starting_stage}')
   set_value(session, aspen_path='\Data\Blocks\COL1\Input\TRAY2\{starting_stage}', value='{ending_stage}')
   ```
3. Set key component to identify 2nd liquid phase (list node):
   ```
   insert_row(session, '\Data\Blocks\COL1\Input\COMP_LIST')
   set_value(session, aspen_path='\Data\Blocks\COL1\Input\COMP_LIST\#0', value='WATER')
   ```

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\NO_PHASE` | int | Number of phases (2 or 3) |
| `\Data\Blocks\{name}\Input\TRAY2\{starting_stage}` | int | Ending stage for LL test range (table node, key = starting stage) |
| `\Data\Blocks\{name}\Input\COMP_LIST\#0` | string | Key component for 2nd liquid phase (list node, use `insert_row` first) |

> **Note:** `TRAY2` is a table node. To create a row: `insert_row` → `set_label` (starting stage) → `set_value` (ending stage). Reading back: `get_value` on `\...\TRAY2\{starting_stage}` returns the ending stage.

> **Note:** `COMP_LIST` is a list node. Use `insert_row` to create a slot, then `set_value` on `#0` to assign the component. To read back: `list_elements` on `COMP_LIST`. Multiple key components can be added with additional `insert_row` calls.

## 3-Phase Convergence Tips

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\MAXOL` | int | Max outer loop iterations (default 25, increase to 100+ for 3-phase) |
| `\Data\Blocks\{name}\Input\DAMPING` | string | Damping: `NONE`, `MODERATE`, `SEVERE` |

- 3-phase columns are harder to converge than 2-phase. If "COLUMN NOT CONVERGED", try increasing `MAXOL` and setting `DAMPING=SEVERE`.
- "LIQUID-LIQUID PHASE SPLIT CALC. FAILED TO CONVERGE" often means the stage range (`TRAY2`) is too narrow — expand to cover the full column (1 to NSTAGE).
- Unreasonable distillate/bottoms rates can prevent convergence. Adjust operating specs to physically realistic values.

## Block-Specific Advanced Inputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\BLKOPFREWAT` | string | Free-water option for the column |
| `\Data\Blocks\{name}\Input\COND_UTIL` | string | Condenser utility ID |
| `\Data\Blocks\{name}\Input\REB_UTIL` | string | Reboiler utility ID |

> RadFrac has separate utility assignments for condenser and reboiler, instead of a single `UTILITY_ID`.

## Advanced Outputs

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\COND_USAGE` | float | Condenser utility usage |
| `\Data\Blocks\{name}\Output\COND_COST` | float | Condenser utility cost |
| `\Data\Blocks\{name}\Output\REB_USAGE` | float | Reboiler utility usage |
| `\Data\Blocks\{name}\Output\REB_COST` | float | Reboiler utility cost |
