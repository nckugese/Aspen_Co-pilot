# Aspen Plus Blocks Index

Each block doc contains: ports, key input paths, configuration steps, and gotchas.

## Reactors
- [rcstr.md](rcstr.md) — RCSTR (Continuous Stirred Tank Reactor)
- [rstoic.md](rstoic.md) — RStoic (Stoichiometric Reactor)
- [rplug.md](rplug.md) — RPlug (Plug Flow Reactor)
- [rgibbs.md](rgibbs.md) — RGibbs (Gibbs Free Energy Minimization Reactor)
- [requil.md](requil.md) — REquil (Equilibrium Reactor)
- [ryield.md](ryield.md) — RYield (Yield Reactor)

## Separators
- [radfrac.md](radfrac.md) — RadFrac (Rigorous Distillation)
- [dstwu.md](dstwu.md) — DSTWU (Shortcut Distillation)
- [flash2.md](flash2.md) — Flash2 (Two-phase Flash)
- [flash3.md](flash3.md) — Flash3 (Three-phase Flash)
- [decanter.md](decanter.md) — Decanter (Liquid-Liquid Separator)

## Heat Exchangers
- [heater.md](heater.md) — Heater/Cooler
- [heatx.md](heatx.md) — HeatX (Two-stream Heat Exchanger)

## Pressure Changers
- [compr.md](compr.md) — Compr (Compressor/Turbine)
- [mcompr.md](mcompr.md) — MCompr (Multi-stage Compressor)
- [pump.md](pump.md) — Pump
- [valve.md](valve.md) — Valve

## Mixers / Splitters
- [mixer.md](mixer.md) — Mixer
- [fsplit.md](fsplit.md) — FSplit (Stream Splitter)

## How to Place a Block

```
place_block(session, block_name='B1', block_type='RadFrac')
```
Or with generic tool:
```
add_element(session, '\Data\Blocks', 'B1!RadFrac')
```
