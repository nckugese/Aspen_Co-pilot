# Compr piecewise integration

Paths are under `\Data\Blocks\{name}\`. Only for `TYPE=INT-POLYTROP` or `INT-POS-DISP`; left blank, the defaults are used.

Once `INT_METHOD` is written the block also needs `INT_STEP` and its parameter: `INTERVALS` for `EQUAL-DELP`, `PRAT_STEP` for `EQUAL-PRATIO`.

`EQUAL-PRATIO` is refused while `INT_METHOD=DIRECT`.

## Setup | Integration Parameters

| Path | Type | Purpose |
|---|---|---|
| `Input\INT_METHOD` | `DIRECT`, `N-METHOD` | Integrate the work directly, or with p v^n = constant per step |
| `Input\INT_STEP` | `EQUAL-DELP`, `EQUAL-PRATIO` | Steps of equal pressure change or of equal pressure ratio |
| `Input\INTERVALS` | int | Number of steps (`EQUAL-DELP`) |
| `Input\PRAT_STEP` | ratio | Pressure ratio of each step (`EQUAL-PRATIO`) |
| `Input\PRAT_FINAL` | ratio | Pressure ratio of the last step (`EQUAL-PRATIO`) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP_INT\{id}` | TEMPERATURE | Temperature at each step boundary (1 = inlet) |
| `Output\B_VFRAC_INT\{id}` | fraction | Vapor fraction at each step boundary |
