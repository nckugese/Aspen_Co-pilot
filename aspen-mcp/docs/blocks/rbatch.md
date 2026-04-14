# RBatch (Batch Reactor)

Batch reactor with kinetic reactions. Models time-dependent reactions with stop criteria.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| BC | IN | Batch charge (required) |
| CF | IN | Continuous feed (optional) |
| RP | OUT | Reactor product |
| VP | OUT | Vapor product |
| HS | OUT | Heat stream out |

> **Note:** BC(IN) is required — the simulation will not run without a stream connected to the batch charge port. CF(IN) is for continuous feed during reaction (optional).

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TYPE` | string | Temperature specification type |
| `\Data\Blocks\{name}\Input\TEMP` | float | Specified temperature (for T-SPEC) |
| `\Data\Blocks\{name}\Input\PRES` | float | Reactor pressure |
| `\Data\Blocks\{name}\Input\PHASE` | string | Valid phases: `V`, `L`, `V-L` |
| `\Data\Blocks\{name}\Input\CYCLE_TIME` | float | Total cycle time |
| `\Data\Blocks\{name}\Input\FEED_TIME` | float | Batch feed time |
| `\Data\Blocks\{name}\Input\DOWN_TIME` | float | Down time between batches |
| `\Data\Blocks\{name}\Input\MAX_TIME` | float | Upper limit on reaction time |
| `\Data\Blocks\{name}\Input\PRINT_TIME` | float | Time interval between profile points (required) |
| `\Data\Blocks\{name}\Input\CATWT` | float | Catalyst loading (kg) |

### TYPE Values (Temperature specification)

| GUI Option | TYPE Value |
|-----------|-----------|
| Constant temperature | `T-SPEC` |
| Temperature profile | `T-PROFILE` |
| Constant heat duty | `DUTY-SPEC` |
| Heat duty profile | `DUTY-PROF` |
| Constant thermal fluid temperature | `TCOOL-SPEC` |
| Heat transfer user subroutine | `USER-DUTY` |

## Stop Criteria

Stop criteria determine when the batch reaction ends. Must insert rows first.

### Setup:
```
# Insert a stop criterion row
insert_row(session, '\Data\Blocks\R6\Input\VARIABLE')
set_label(session, '\Data\Blocks\R6\Input\VARIABLE', index=0, label='1')

# Set location (REACTOR, VENT, or ACCUMULATOR)
set_value(session, aspen_path='\Data\Blocks\R6\Input\LOCATION\1', value='REACTOR')

# Set variable type (e.g. TIME, TEMP, CONV, MOLE-FLOW, etc.)
set_value(session, aspen_path='\Data\Blocks\R6\Input\VARIABLE\1', value='TIME')

# Set stop value
set_value(session, aspen_path='\Data\Blocks\R6\Input\VALUE\1', value='1', unit='hr')
```

> **Note:** LOCATION must be set before VARIABLE — VARIABLE is not enterable until LOCATION is specified.

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

## Assigning a Reaction Set

Same as RPlug/RCSTR — insert_row into RXN_ID then set value:
```
insert_row(session, '\Data\Blocks\R6\Input\RXN_ID')
set_value(session, aspen_path='\Data\Blocks\R6\Input\RXN_ID\#0', value='RXN1')
```

## Typical Setup

1. Place: `place_block(session, 'R6', 'RBatch')`
2. Set type: `set_value(session, aspen_path='\Data\Blocks\R6\Input\TYPE', value='T-SPEC')`
3. Temperature: `set_value(session, aspen_path='\Data\Blocks\R6\Input\TEMP', value='80', unit='C')`
4. Pressure: `set_value(session, aspen_path='\Data\Blocks\R6\Input\PRES', value='1', unit='atm')`
5. Phase: `set_value(session, aspen_path='\Data\Blocks\R6\Input\PHASE', value='L')`
6. Cycle time: `set_value(session, aspen_path='\Data\Blocks\R6\Input\CYCLE_TIME', value='2', unit='hr')`
7. Max time: `set_value(session, aspen_path='\Data\Blocks\R6\Input\MAX_TIME', value='1', unit='hr')`
8. Print time: `set_value(session, aspen_path='\Data\Blocks\R6\Input\PRINT_TIME', value='0.1', unit='hr')`
9. Set stop criteria (see above).
10. Create and assign reaction set (same as RPlug/RCSTR).

## Gotchas

- **BC(IN) port is required** — must have a batch charge stream connected, or the flowsheet section will be incomplete.
- Ports are BC/CF/RP/VP, NOT F/P like other reactors.
- **TYPE must be set** — unlike RPlug which uses ADIABATIC/CONSTANT-T, RBatch uses T-SPEC/DUTY-SPEC/etc.
- **LOCATION must be set before VARIABLE** in stop criteria — VARIABLE is not enterable otherwise.
- **PRINT_TIME is required** — time interval between profile points must be specified.
- Requires kinetic reaction set (POWERLAW or LHHW), same as RCSTR/RPlug.
- Results are per-cycle — multiply by cycles for continuous production estimates.
