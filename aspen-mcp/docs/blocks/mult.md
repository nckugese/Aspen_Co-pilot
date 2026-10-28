# Mult

Stream multiplier: scales one material, heat or work stream by a factor, e.g. to stand one train in for several parallel ones. Paths are under `\Data\Blocks\{name}\`. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)`/`P(OUT)` for a material stream, `HS(IN)`/`HS(OUT)` for a heat stream, `WS(IN)`/`WS(OUT)` for a work stream.

One stream in, one out, of one class: a second feed or outlet, or a stream of another class next to the first, is refused.

`FACTOR` is the only input; left unset, the run gives the block no results.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\FACTOR` | real | Multiplier on the flow (material), the duty (heat) or the power (work) |

`FACTOR` 0 is accepted and gives an outlet with zero flow.

Only the flow scales: the outlet keeps the inlet's temperature, pressure and composition.

A heat stream's duty is multiplied: 100 kW in, FACTOR 3, 300 kW out.

A work stream's power is multiplied the same way: 10 kW in, FACTOR 0.5, 5 kW out.

A negative `FACTOR` is refused while a material stream is connected; on a heat or work stream it reverses the sign (100 kW in, -1, -100 kW out).

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\R_FACTOR` | real | Factor applied |

Scaled values are on the outlet stream: `\Data\Streams\<out>\Output\MOLEFLMX\MIXED` (material), `...\QCALC` (heat duty), `...\POWER_OUT` (work).

Not covered: none.
