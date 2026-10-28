# BatchOp vent and pressure

Paths are under `\Data\Blocks\{name}\`. Vapor out of `VP(OUT)`, a pressure computed from the vessel volume, and a pad gas (Setup | Specifications).

With `NPHASE` 2 or 3 the vapor leaves by `VP(OUT)`; the stream gives the vent rate at the final time, not an average (ventq: 22 kmol/hr at 2 hr, while 9 kmol left over the whole batch).

## Computed pressure (`PRES_TYPE` `CALCULATE`)

| Path | Type | Purpose |
|---|---|---|
| `Input\VOLUME_SPEC` | `SPECIFY`, `GEOMETRY` | Vessel volume given here, or from the vessel size ([batchop-geometry.md](batchop-geometry.md)) |
| `Input\VOLUME` | VOLUME | Vessel volume (`SPECIFY`) |
| `Input\P_OPEN` | PRESSURE | Pressure at which the vent opens |
| `Input\P_CLOSE` | PRESSURE | Pressure at which it closes again |

At 110 C the closed 20 cum pot vented about half of the 100 kmol charge between `P_OPEN` and `P_CLOSE`.

## Pad gas (`CALCULATE`)

| Path | Type | Purpose |
|---|---|---|
| `Input\USE_PADGAS` | `NO`, `YES` | Inert gas in the headspace when the batch begins |
| `Input\PAD_COMP` | component | The inert component |
| `Input\INIT_PRES` | PRESSURE | Pad gas pressure at time 0 |
| `Input\PAD_TEMP` | TEMPERATURE | Pad gas temperature at time 0 |

The pad gas stays in the pot and leaves with `RP(OUT)` (0.12 kmol of nitrogen in the pad run).

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\MO_FLOW_VENT\{pt}` | MOLE-FLOW | Profile: vent rate |
| `Output\MO_FRAC_VENT\{pt}\{comp}` | fraction | Profile: vent mole fraction |
| `Output\PRES_REAC\{pt}` | PRESSURE | Profile: pot pressure |
