# Heat and work streams

A heat stream carries a duty and a work stream a power from one block to another.

Root: `\Data\Streams\{id}`

`place_stream` with `stream_type='HEAT'` or `'WORK'`; it goes on a block's `HS` or `WS` ports.

## Heat stream | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\DUTY` | ENTHALPY-FLO | Duty carried into the block it feeds; positive adds heat |
| `Input\TEMP` | TEMPERATURE | Start temperature, reported back; the block's balance does not use it |
| `Input\TEND` | TEMPERATURE | End temperature, as `TEMP` |

On `HS(IN)` the block takes the duty: the Heater's own duty equalled the stream's, and the outlet was the same with or without `TEMP` and `TEND`.

## Work stream | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\POWER` | POWER | Power carried into the block it feeds; negative gives work to the block |
| `Input\SPEED` | FREQUENCY | Shaft speed passed on with the power |

The sign is the block's: -2 kW on a Pump's `WS(IN)` gave it 2 kW of brake power.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\QCALC` | ENTHALPY-FLO | Duty carried; on `HS(OUT)` the block's duty with the sign reversed |
| `Output\TBEGIN` | TEMPERATURE | On `HS(OUT)`: the block's inlet temperature |
| `Output\TEND` | TEMPERATURE | On `HS(OUT)`: the block's outlet temperature |
| `Output\SOURCE` | ID | Block the stream leaves |
| `Output\POWER_OUT` | POWER | Power carried; on `WS(OUT)` the block's net work, same sign |
| `Output\SPEED_OUT` | FREQUENCY | Speed carried |
| `Output\DESTINATION` | ID | Block the stream feeds |

On `HS(OUT)` the stream carried minus the Heater's duty and its 25 to 80 C; on `WS(OUT)`, the Pump's net work.
