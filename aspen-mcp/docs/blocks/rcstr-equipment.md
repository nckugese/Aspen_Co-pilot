# RCSTR equipment-based vessel

Paths are under `\Data\Blocks\{name}\`. `EQUIP_MODE` = `EQUIP-BASED` describes the vessel and its agitator; the shape feeds the jacket and coil heat transfer ([rcstr-heat-transfer.md](rcstr-heat-transfer.md)).

With `DV` the reactor volume stays the `VOL` entered.

## Setup | Vessel

| Path | Type | Purpose |
|---|---|---|
| `Input\GEOMETRYSPEC` | `DV`, `LV`, `DL` | Which pair sets the shape: diameter and volume, length and volume, diameter and length |
| `Input\POTDIAM` | LENGTH | Vessel diameter |
| `Input\POTLENGTAN` | LENGTH | Straight-side length between the heads |
| `Input\POTORIENT` | `VERTICAL`, `HORIZONTAL` | Orientation |
| `Input\POTTOPHEAD` | `ELLIPTICAL`, `HEMISPHERICAL`, `TORISPHERICAL`, `CONICAL`, `FLAT` | Top head shape |
| `Input\POTBTMHEAD` | `ELLIPTICAL`, `HEMISPHERICAL`, `TORISPHERICAL`, `CONICAL`, `FLAT` | Bottom head shape |

## Agitator and baffles

| Path | Type | Purpose |
|---|---|---|
| `Input\POT_AGITATOR` | `YES`, `NO` | Vessel has an agitator |
| `Input\AGIT_TYPE` | `DISC`, `3-BLADE`, `FLAT`, `ANCHOR`, `BAFFLED`, `PITCHED`, `RIBBON` | Impeller type |
| `Input\IMPELLER_NUM` | int | Number of impellers |
| `Input\IMPELLER_DIA` | LENGTH | Impeller diameter |
| `Input\IMPELLER_RAT` | FREQUENCY | Impeller speed |
| `Input\BAFFLES` | `YES`, `NO` | Vessel has baffles |
| `Input\BAFFL_NUMBER` | int | Number of baffles |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\TOT_VOL` | VOLUME | Reactor volume |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
