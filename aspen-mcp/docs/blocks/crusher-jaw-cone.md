# Crusher: jaw and cone crushers

`TYPE` `JAW` or `CONE`: the gap settings and a selection model decide which particles break, a breakage model how they break. Paths are under `\Data\Blocks\{name}\`; basics in [crusher.md](crusher.md).

Selection is fixed by the type: `JAW` uses `WHITEN`, `CONE` uses `KING`. `BREAK_FUN` is `VOGEL` (default) or `AUSTIN`.

`JAW` needs `CSS` and `OSS`; `CONE` needs `CSS` and the three King parameters (`OSS` is optional).

`CSS` must stay below `OSS`: a write that breaks this is refused.

`KING_ALPHA2` must be above `KING_ALPHA1`: a write that breaks this is refused.

On these types, Vogel breakage needs `VOGEL_Q` and `VOGEL_MINSIZ`; Austin breakage needs `AUSTIN_BETA`, `AUSTIN_GAMMA` and `AUSTIN_PHI`.

`DIAM` has no effect on these types: the gaps set the product.

## Selection and gaps

| Path | Type | Purpose |
|---|---|---|
| `Input\SEL_FUN` | `WHITEN`, `KING` | Selection model: Whiten (`JAW`) or King (`CONE`) |
| `Input\CSS` | LENGTH | Closed-side setting (narrowest gap) |
| `Input\OSS` | LENGTH | Open-side setting (widest gap) |
| `Input\KING_ALPHA1` | real | King: lower size parameter |
| `Input\KING_ALPHA2` | real | King: upper size parameter |
| `Input\KING_N` | real | King: exponent |

## Breakage

| Path | Type | Purpose |
|---|---|---|
| `Input\BREAK_FUN` | `VOGEL`, `AUSTIN` | Breakage model |
| `Input\VOGEL_Q` | real | Vogel: exponent of the fragment size distribution |
| `Input\VOGEL_MINSIZ` | LENGTH | Vogel: smallest fragment size |
| `Input\AUSTIN_BETA` | real | Austin breakage: beta |
| `Input\AUSTIN_GAMMA` | real | Austin breakage: gamma |
| `Input\AUSTIN_PHI` | real | Austin breakage: phi |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\POWER` | POWER | Grinding power |
| `Output\OUTLET_D80` | LENGTH | Size that 80 % of the product solids pass |
