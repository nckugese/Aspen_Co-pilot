# Analyzer

A stream analyzer: it flashes a copy of one stream at the state you give and reports that state and chosen properties; the stream itself passes through unchanged. Paths are under `\Data\Blocks\{name}\`. Rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` and `P(OUT)`, one material stream each; Aspen refuses a second.

Nothing is required. When nothing at all has been written to its input, the run returns no results; any write (even `DESCRIPTION`) is enough.

The outlet always equals the inlet. The specifications below only set where the analysed copy is flashed, and they show up only in the block's results.

## Input | Specifications

Leave `TEMP`, `VFRAC` and `PRES1` empty to analyse the stream at its own temperature and pressure.

| Path | Type | Purpose |
|---|---|---|
| `Input\TEMP` | TEMPERATURE | Flash temperature for the analysed copy |
| `Input\VFRAC` | fraction | Molar vapor fraction instead of a temperature |

`TEMP` and `VFRAC` exclude each other: once one is set, writing the other is refused.

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES1` | PRESSURE | Flash pressure; zero or negative means a drop from the inlet pressure |

`PRES1` -0.1 bar on a 1 atm inlet gives 0.913 bar in the results.

| Path | Type | Purpose |
|---|---|---|
| `Input\NPHASE` | `1`, `2`, `3` | Phases the flash may form (default 2) |
| `Input\PHASE` | `V`, `L` | The single phase when `NPHASE` is 1 |

Write `NPHASE` 1 before `PHASE`; with 2 or 3 phases `PHASE` is not enterable.

## Analysing a stream without connecting it

| Path | Type | Purpose |
|---|---|---|
| `Input\STREAM` | stream ID | Stream to analyse when the block has no ports |

Leave both ports empty and name any stream of the flowsheet; the results show that stream's state.

With ports connected the block analyses its inlet and ignores `STREAM`.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Temperature the copy was flashed at |
| `Output\B_PRES` | PRESSURE | Its pressure |
| `Output\B_VFRAC` | fraction | Vapor share after the flash, molar |
| `Output\QCALC` | ENTHALPY-FLO | Duty needed to bring the stream to that state (not applied) |
| `Output\Y\{comp}` | fraction | Vapor composition, one value per component (mole basis) |
| `Output\X1\{comp}` | fraction | First-liquid mole fraction per component |
| `Output\X2\{comp}` | fraction | Second-liquid mole fraction per component |
| `Output\LIQ_RATIO` | fraction | First liquid's share of all liquid |

More: [property sets](analyzer-property-sets.md).

Not covered: EO variables (the SPC_* switches and extra EO specification rows act only in equation-oriented runs; not run); EO Options and EO input (equation-oriented solver settings, scripts and spec groups; not run).
