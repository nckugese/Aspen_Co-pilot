# Pump shaft speed and curve scaling

Paths are under `\Data\Blocks\{name}\`. Fields of Performance Curves | Operating, for `OPT_SPEC=USE-CURVE` ([pump-curves.md](pump-curves.md)).

`SINGLE-REFE`: the curve holds at `REF_SH_SPEED` and is moved to `ACT_SH_SPEED` with r = actual / reference speed: flow x r, head x r^`AFFEXPH`, power x r^`AFFEXPP`, efficiency x r^`AFFEXPE`.

`MULTIP`: give `SHAFT_SPEED\{k}` and the tables of each curve k; the block interpolates between curves at `ACT_SH_SPEED`.

Each `*_FACTOR` multiplies its curve's value: `HEAD_FACTOR` the head, `EFF_FACTOR` the efficiency.

## Performance Curves | Operating

| Path | Type | Purpose |
|---|---|---|
| `Input\ACT_SH_SPEED` | FREQUENCY | Speed the pump runs at |
| `Input\REF_SH_SPEED` | FREQUENCY | Speed of a `SINGLE-REFE` curve |
| `Input\SHAFT_SPEED\{k}` | FREQUENCY | Speed of curve k (`MULTIP`) |
| `Input\IMPELLER_DIA` | LENGTH | Impeller diameter (head and flow coefficients) |
| `Input\AFFEXPH` | real | Head exponent, default 2 |
| `Input\AFFEXPP` | real | Power exponent, default 3 |
| `Input\AFFEXPE` | real | Efficiency exponent, default 1 |
| `Input\HEAD_FACTOR` | real | Factor on the head curve |
| `Input\EFF_FACTOR` | real | Factor on the efficiency curve |
| `Input\POWER_FACTOR` | real | Factor on a power curve (`PRES_FACTOR`, `PRAT_FACTOR`, `DELP_FACTOR`, `HEADC_FACTOR`, `NPSHR_FACTOR` alike) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\ACT_SS` | FREQUENCY | Speed used |
| `Output\REF_SPEED` | FREQUENCY | Reference speed |
| `Output\HEAD_FAC` | real | Head factor used |
