# RBatch (Batch Reactor)

Batch reactor with kinetic reactions. Models time-dependent reactions with stop criteria.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| P | OUT | Product |
| HS | OUT | Heat stream out |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\PRES` | float | Reactor pressure |
| `\Data\Blocks\{name}\Input\CYCLE_TIME` | float | Total cycle time |
| `\Data\Blocks\{name}\Input\FEED_TIME` | float | Batch feed time |
| `\Data\Blocks\{name}\Input\DOWN_TIME` | float | Down time between batches |

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\STOP-CRIT` | int | Stop criterion number that was triggered |
| `\Data\Blocks\{name}\Output\STOP-TIME` | float | Reaction time at stop |
| `\Data\Blocks\{name}\Output\QCALC` | float | Heat load per cycle |
| `\Data\Blocks\{name}\Output\TMIN` | float | Minimum reactor temperature |
| `\Data\Blocks\{name}\Output\TMAX` | float | Maximum reactor temperature |
| `\Data\Blocks\{name}\Output\VOLUME_OUT` | float | Maximum volume deviation |
| `\Data\Blocks\{name}\Output\VOL_TIME` | float | Time of maximum volume deviation |

## Typical Setup

1. Place: `place_block(session, 'R1', 'RBatch')`
2. Pressure: `set_value(session, aspen_path='\Data\Blocks\R1\Input\PRES', value='1', unit='atm')`
3. Cycle time: `set_value(session, aspen_path='\Data\Blocks\R1\Input\CYCLE_TIME', value='3600', unit='sec')`
4. Create and assign reaction set (same workflow as RCSTR).

## Gotchas

- Requires kinetic reaction set (POWERLAW or LHHW), same as RCSTR/RPlug.
- Must define stop criteria (time, conversion, or temperature).
- Results are per-cycle — multiply by cycles for continuous production estimates.
