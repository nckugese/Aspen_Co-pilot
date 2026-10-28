# Dryer

Removes moisture from wet solids: a shortcut balance, or a convective, spray or contact dryer model. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `FEED(IN)` wet solids, `GAS(IN)` drying gas, `G2(IN)` atomizing gas ([spray](dryer-spray.md)), `Q-IN(IN)`, `Q-OUT(OUT)` heat streams, `PRODUCT(OUT)` dried solids, `EXHAUST(OUT)` gas and vapor.

The water to remove must be a moisture component sitting in the solid substream: insert a row into `\Data\Components\Moisture-Comps\Input\COMP`, write `H2O` to it, and give the feed water as `FLOW\CIPSD\H2O`. Water in `MIXED` is not moisture: the shortcut then warns of a negative evaporation rate.

`SHORTCUT` needs only the outlet moisture and one thermal spec; it runs with or without `GAS(IN)`.

check_inputs lists `LENGTH` and `FRACTION` as required on every dryer; the shortcut runs without either.

The shortcut leaves solids and exhaust at one temperature.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\DRYER_TYPE` | `SHORTCUT`, `CONVECTIVE`, `SPRAY`, `CONTACT` | Model: moisture balance only, convective ([convective](dryer-convective.md)), spray ([spray](dryer-spray.md)), heated surface ([contact](dryer-contact.md)) |
| `Input\EX_MASSFRAC\{comp}\{substream}` | fraction | `SHORTCUT`: moisture left in the product, per moisture component and solid substream |
| `Input\MOIST_BASIS` | `WET`, `DRY` | `EX_MASSFRAC` per kg of wet or of dry solids |
| `Input\OPT_OPERATE` | `OPT-TEMP`, `OPT-DELT`, `OPT-HEATDU`, `OPT-SUPERH` | `SHORTCUT` thermal spec: outlet temperature, temperature change, heat duty, or exhaust margin above its dew point |
| `Input\TEMP` | TEMPERATURE | `OPT-TEMP`: outlet temperature |
| `Input\DELT` | DELTA-T | `OPT-DELT`: outlet minus inlet temperature |
| `Input\HEATIN` | ENTHALPY-FLO | `OPT-HEATDU`: heat added (negative: lost); default 0 |
| `Input\DEWPTDT` | DELTA-T | `OPT-SUPERH`: exhaust temperature minus its dew point |
| `Input\PRES_OPT` | `AIR-PRES`, `SPEC-PRES` | Take the gas inlet's pressure, or use `PRES` |
| `Input\PRES` | PRESSURE | `SPEC-PRES`: outlet pressure above 0, a drop at 0 or below |

`MOIST_BASIS` `WET`: 0.01 left 10.1 kg water in 1011 kg product; `DRY`: 10.0 kg on 1001 kg calcite.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\EXGT` | TEMPERATURE | Exhaust temperature |
| `Output\EX_SOL_TEMP` | TEMPERATURE | Product solids temperature |
| `Output\EXDEW` | TEMPERATURE | Exhaust dew point |
| `Output\ADQ` | ENTHALPY-FLO | Heat duty |

More: [convective](dryer-convective.md), [drying curve](dryer-curve.md), [mass and heat transfer](dryer-transfer.md), [contact](dryer-contact.md), [spray](dryer-spray.md), [convergence](dryer-convergence.md).

Not covered: Batch operation (`BATCH_OP` `YES`, `INIT_METHOD`, `CHARGE_MASS`, `FEED_TIME`, `DISCHARGE_T`, `DTMAX`, `DTCUTOFF`, `DTADBREC`) (did not converge: every setup tried ended in an engine system error); Entrainment sheet (`ENTRN_OPT`, `SENTRN_OPT`, `TOTENTRAIN`, entrainment curve) (its per-substream rows could not be created through the tree); PSD sheet (`PART_MODEL`, `FIT_TYPE`, `FIT_DISTR`, `INFLATION`, `SHRINKAGE`, `MV_SATTSUB`) (runs converge but no effect seen on the calcite case); Heat loss to ambient (`HEAT_LOSS`, `UAMB`, `TAMB`) (no effect seen); Spray zone corrections (`JETZO_MODEL`, `JET_LENGTH`, `HEAT_FACT`, `MASS_FACT`, `LEN_FRAC`), droplet tables (`DISTR_FUN` `TABULAR`, `DROVEL_OPT`), `NPHASE`, heat-stream ports (not checked).
