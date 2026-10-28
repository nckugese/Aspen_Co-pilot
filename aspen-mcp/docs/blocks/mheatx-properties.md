# MHeatX per-stream properties

Paths are under `\Data\Blocks\{name}\`. MHeatX takes property settings per inlet stream in place of the block-wide ones in common.md.

## Block Options | Properties

| Path | Type | Purpose |
|---|---|---|
| `Input\SOPSETNAME\{stream}` | method name | Property method of the stream |
| `Input\SHENRY_COMPS\{stream}` | ID | Henry-components list |
| `Input\SCHEMISTRY\{stream}` | ID | Chemistry |
| `Input\SFREE_WATER\{stream}` | `STEAM-TA`, `IAPWS-95`, `IF97`, `IDEAL` | Water-phase method |
| `Input\SSOLU_WATER\{stream}` | `0`, `1`, `2`, `3`, `4`, `5` | Water solubility method |
