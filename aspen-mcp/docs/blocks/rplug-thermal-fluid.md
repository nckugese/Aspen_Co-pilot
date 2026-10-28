# RPlug thermal fluid

Paths are under `\Data\Blocks\{name}\`. A second stream flows along the tube outside it and exchanges heat with the process stream, in the same direction or against it.

1. Connect the thermal-fluid feed to `C(IN)` and a stream to `C(OUT)`; without them the input is incomplete.
2. Set `TYPE` = `CO-COOL` or `COUNTER-COOL`, and `U`.
3. With `COUNTER-COOL` also give the fluid outlet: `TEMP` or `CVFRAC`. The block then works out the fluid inlet temperature itself; the temperature in the `C(IN)` stream is not kept.

`CPHASE` is open only with `CNPHASE` = `1`.

## Setup | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\TYPE` | `CO-COOL`, `COUNTER-COOL` | Fluid flows with the process stream, or against it |
| `Input\U` | HEAT-TRANS-C | U between the fluid and the process stream |
| `Input\TEMP` | TEMPERATURE | Fluid outlet temperature (`COUNTER-COOL`) |
| `Input\CVFRAC` | fraction | Vapor share of the leaving fluid (`COUNTER-COOL`) |

## Setup | Configuration and Pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\CNPHASE` | `1`, `2` | Phases in the fluid: one, or vapor-liquid |
| `Input\CPHASE` | `L`, `V` | Fluid phase when `CNPHASE` is 1 |
| `Input\CPRES` | PRESSURE | Fluid inlet pressure (> 0) or inlet drop (<= 0) |
| `Input\CPDROP` | PDROP | Fluid pressure drop along the tube |

## Block Options | Properties (thermal fluid)

| Path | Type | Purpose |
|---|---|---|
| `Input\COPSETNAME` | method name | Property method for the fluid only (the `C...` twins of the process-stream property fields: `CHENRY_COMPS`, `CCHEMISTRY`, `CTRUE_COMPS`, `CFRWATEROPSE`, `CSOLU_WATER`) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\COOLANT_TEMP\{id}` | TEMPERATURE | Fluid temperature profile (point 1 at the process inlet) |
| `Output\COOLANT_TIN` | TEMPERATURE | Fluid inlet temperature |
| `Output\COOLANT_VIN` | fraction | Vapor share of the entering fluid |
| `Output\COOL_PIN` | PRESSURE | Fluid inlet pressure |
| `Output\QCALC` | ENTHALPY-FLO | Heat removed from the process stream |
