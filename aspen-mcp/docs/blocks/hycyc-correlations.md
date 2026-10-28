# HyCyc: correlations

Parameters of each `METHOD` (`USER` is in [hycyc-user-efficiency.md](hycyc-user-efficiency.md)). Paths are under `\Data\Blocks\{name}\`; basics in [hycyc.md](hycyc.md).

`BRADLEY` and `PLITT` run on their defaults. `MOD-BRAUN` needs `ROUGHNESS`.

`NAGESWARARAO` needs `ALPHA`, `BETA`, `CONST_KW1`, `CONST_KV1`, plus the KD and KQ constant that `KD_OPT` and `KQ_OPT` pick.

The KQ constant sets the pressure drop: too small a `CONST_KQ0` (such as 1) can give a drop above the feed pressure (block error, ideal split), while a few hundred gives a drop of the order of 0.1 bar.

## Bradley

| Path | Type | Purpose |
|---|---|---|
| `Input\VEL_COEF` | real | Loss factor on the inlet velocity (default 0.45) |
| `Input\VEL_EXP` | real | Exponent of the radial velocity profile (default 0.8) |
| `Input\VOL_RATIO` | real | Liquid split parameter (default 6.13) |

## Plitt

| Path | Type | Purpose |
|---|---|---|
| `Input\PLITT_F1` | real | Tuning factor on the cut size (default 1) |
| `Input\PLITT_F2` | real | Tuning factor on the sharpness (default 1) |
| `Input\PLITT_F3` | real | Tuning factor on the pressure drop (default 1) |
| `Input\PLITT_F4` | real | Tuning factor on the liquid split (default 1) |

## Nageswararao

| Path | Type | Purpose |
|---|---|---|
| `Input\ALPHA` | real | Sharpness of the efficiency curve |
| `Input\BETA` | real | Fish-hook term of the efficiency curve (0 for none) |
| `Input\KD_OPT` | `VKD0`, `VKD1` | Which cut-size constant is given |
| `Input\CONST_KD0` | real | Cut-size constant KD0 |
| `Input\CONST_KD1` | real | Cut-size constant KD1 |
| `Input\KQ_OPT` | `VKQ0`, `VKQ1` | Which pressure-drop constant is given |
| `Input\CONST_KQ0` | real | Pressure-drop constant KQ0 |
| `Input\CONST_KQ1` | real | Pressure-drop constant KQ1 |
| `Input\CONST_KW1` | real | Liquid split constant KW1 |
| `Input\CONST_KV1` | real | Slurry volume split constant KV1 |

## Modified Braun

| Path | Type | Purpose |
|---|---|---|
| `Input\ROUGHNESS` | LENGTH | Wall roughness |
| `Input\EXP_N` | real | Exponent of the density correction (default 0.5) |
| `Input\PDROP_MODE` | `MOD-BRAUN`, `PLITT` | Pressure-drop submodel (default `MOD-BRAUN`) |
| `Input\FSPLT_MODE` | `MODER-DAHL`, `YOSHIOKA`, `ABBOTT`, `TARJAN`, `PLITT` | Flow-split submodel (default `MODER-DAHL`) |
| `Input\RMV_KA` | real | Coefficient Ka of the `TARJAN` flow split (default 0) |
| `Input\RMV_KB` | real | Coefficient Kb of the `TARJAN` flow split (default 0) |
