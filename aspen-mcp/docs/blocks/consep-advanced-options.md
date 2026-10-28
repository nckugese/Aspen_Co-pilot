# ConSep advanced options

Paths are under `\Data\Blocks\{name}\`. The Advanced sheet: flash, curve and design settings; the defaults solve ordinary cases.

| Path | Type | Purpose |
|---|---|---|
| `Input\FLASH_MAXIT` | int | Iterations per flash (default 30) |
| `Input\FLASHTOL` | real | Flash tolerance (default 1e-4) |
| `Input\CURVEALG` | `STANDARD`, `AZEOTROPIC` | Method for the residue and distillation curves |
| `Input\CURVESTEP` | real | Step along the residue and distillation curves (default 0.3) |
| `Input\ENVSTEP` | real | Step along the two-liquid envelopes (default 0.1) |
| `Input\DESIGNALG` | `STANDARD`, `ADVANCED` | Method for the design calculation |
| `Input\MAXSTAGE` | int | Most stages the design may use (default 200) |
