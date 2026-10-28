# BatchOp vessel geometry

Paths are under `\Data\Blocks\{name}\`. Vessel size, heads and agitator (Setup | Pot Geometry); needed with `HTRANMODE` `RIGOROUS` or `VOLUME_SPEC` `GEOMETRY`.

| Path | Type | Purpose |
|---|---|---|
| `Input\GEOMETRYSPEC` | `DL`, `DV` | Size from diameter + length, or diameter + volume |
| `Input\POTDIAM` | LENGTH | Diameter |
| `Input\POTLENGTAN` | LENGTH | Straight-side length between the heads (`DL`) |
| `Input\POTVOL` | VOLUME | Volume (`DV`) |

The size must hold the charge: 10 cum for 100 kmol of liquid stopped with the liquid at 99.5 % of the volume, 20 cum ran.

| Path | Type | Purpose |
|---|---|---|
| `Input\POTORIENT` | `VERTICAL`, `HORIZONTAL` | Orientation |

A `HORIZONTAL` pot with the default jacket kept the jacket duty at 0: check `QCALC` after the switch.

| Path | Type | Purpose |
|---|---|---|
| `Input\POTBTMHEAD` | `ELLIPTICAL`, `CONICAL`, `FLAT`, `HEMISPHERICAL`, `TORISPHERICAL` | Bottom head |
| `Input\POTTOPHEAD` | `ELLIPTICAL`, `CONICAL`, `FLAT`, `HEMISPHERICAL`, `TORISPHERICAL` | Top head |

## Agitator (for `FILMHTCOPT` `CORRELATION`)

| Path | Type | Purpose |
|---|---|---|
| `Input\POT_AGITATOR` | `NO`, `YES` | Agitated pot |
| `Input\AGIT_TYPE` | `DISC`, `3-BLADE`, `FLAT`, `ANCHOR`, `BAFFLED`, `PITCHED`, `RIBBON` | Impeller type |
| `Input\IMPELLER_DIA` | LENGTH | Impeller diameter |
| `Input\IMPELLER_RAT` | FREQUENCY | Impeller speed |
| `Input\IMPELLER_NUM` | int | Number of impellers |
