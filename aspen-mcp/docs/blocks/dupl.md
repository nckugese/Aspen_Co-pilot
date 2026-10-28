# Dupl

Duplicator: copies one inlet stream, unchanged, to every outlet, e.g. to feed the same stream to alternative trains side by side. Paths are under `\Data\Blocks\{name}\`. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)`/`P(OUT)` for material, `HS(IN)`/`HS(OUT)` for heat, `WS(IN)`/`WS(OUT)` for work.

One inlet and any number of outlets, all of one class: a second inlet, or a stream of another class next to the first, is refused.

There is nothing to specify: connecting the inlet and the outlets is the whole setup.

Over COM, look the block's `Input` folder up once (`FindNode` on `\Data\Blocks\{name}\Input`) before the first run; while it was never looked up, the run computes nothing at all (no stream results, `UOSSTAT2` empty).

Aspen keeps the block's input-incomplete flag (COMPSTATUS bit 0x40) set even when it is ready and after it solved, so a completeness scan lists it.

Every outlet is a full copy of the inlet: the same flow, temperature, pressure and composition.

Mass is not conserved: three outlets of a 100 kmol/hr feed carry 300 kmol/hr in all.

A heat stream is copied the same way: 100 kW in, 100 kW on each outlet.

A work stream too: 10 kW in, 10 kW on each outlet.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BLKSTAT` | int | Block status, 0 when solved |

The block has no result fields of its own; read the copies on the outlet streams: `\Data\Streams\<out>\Output\MOLEFLMX\MIXED` (material), `...\QCALC` (heat), `...\POWER_OUT` (work).

Not covered: EO Options (equation-oriented settings, not checked).
