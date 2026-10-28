# Crusher: impact and hammer mills

`TYPE` `IMPACT-MILL` or `HAMMER-MILL`: particles break on impact; a selection model gives the share that breaks, a breakage model the fragments. Paths are under `\Data\Blocks\{name}\`; basics in [crusher.md](crusher.md).

On both types `SEL_FUN` is `VOGEL` (default) or `AUSTIN`, and `BREAK_FUN` is `VOGEL` (default), `AUSTIN` or `KERLIN`.

The impact mill takes its stress from `IMPACT_VEL`. The hammer mill takes it from the rotor: `ROTOR_VEL`, or with `BREAKFN_OPT2` `FREQ`, `ROT_FREQ` and `ROTOR_DIAM`.

Vogel selection needs `VOGEL_FMAT` and `VOGEL_WMIN`; Austin selection `AUSTIN_A`, `AUSTIN_S1` and `AUSTIN_X1`. Vogel breakage needs `VOGEL_C`, `VOGEL_D` and `VOGEL_MINSIZ` (`VOGEL_Q` is for jaw and cone); Austin breakage the three parameters in [jaw and cone](crusher-jaw-cone.md); Kerlin breakage `KERLIN_A`, `KERLIN_N` and `MIN_IMP_VEL`.

Write `VOGEL_WMIN` with its unit: the default unit is cal/gm, so a 20 meant as J/kg stops all breakage and the run ends with a warning (reduction ratio 1).

## Models and stress

| Path | Type | Purpose |
|---|---|---|
| `Input\SEL_FUN` | `VOGEL`, `AUSTIN` | Selection model |
| `Input\BREAK_FUN` | `VOGEL`, `AUSTIN`, `KERLIN` | Breakage model |
| `Input\IMPACT_VEL` | VELOCITY | Impact mill: impact velocity |
| `Input\BREAKFN_OPT2` | `VEL`, `FREQ` | Hammer mill: rotor given by tip speed or by rotation rate |
| `Input\ROTOR_VEL` | VELOCITY | Rotor tip speed (`VEL`) |
| `Input\ROT_FREQ` | FREQUENCY | Rotation rate (`FREQ`) |
| `Input\ROTOR_DIAM` | LENGTH | Rotor diameter (`FREQ`) |
| `Input\VOGEL_FMAT` | SPEC-MAT-RES | Vogel: material strength factor (e.g. in `kg/J-m`) |
| `Input\VOGEL_WMIN` | MASS-ENTHALP | Vogel: specific energy below which no particle breaks |
| `Input\AUSTIN_A` | real | Austin selection: a |
| `Input\AUSTIN_S1` | real | Austin selection: S1 |
| `Input\AUSTIN_X1` | LENGTH | Austin selection: reference size d1 |
| `Input\VOGEL_C` | INVERSE-VEL | Vogel breakage: c |
| `Input\VOGEL_D` | real | Vogel breakage: d |
| `Input\VOGEL_MINSIZ` | LENGTH | Vogel breakage: smallest fragment size |
| `Input\KERLIN_A` | real | Kerlin breakage: a |
| `Input\KERLIN_N` | real | Kerlin breakage: n |
| `Input\MIN_IMP_VEL` | VELOCITY | Smallest impact velocity that breaks a particle |

## Options

| Path | Type | Purpose |
|---|---|---|
| `Input\NUM_STRESS` | int | Number of stress events per particle (default 1) |
| `Input\FATIGUE` | `NO`, `YES` | Account for weakening over repeated stress events |
| `Input\IMP_VEL_DIST` | `NO`, `YES` | Spread of impact velocities instead of one value |
| `Input\IMP_VEL_KV` | INVERSE-VEL | Spread parameter of the velocity distribution |
| `Input\WSCALE` | real | Scale factor on the impact energy (default 1) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\POWER` | POWER | Grinding power |
| `Output\OUTLET_D50` | LENGTH | Median size of the product solids |
