# Compr power loss

Paths are under `\Data\Blocks\{name}\`. A mechanical loss added to the net work.

Loss = `PLOSS_FACTOR` x (c1 + c2·Q·N² + c3·Q²·N²) + `PLOSS_OFFSET`. Q: inlet volume flow (`PL_FLOW_UNIT`); N: `ACT_SH_SPEED` (`PL_SP_UNIT`); loss in `PLOSS_UNITS`. `WNET` = fluid power + loss.

Writing `PLOSS_COEF2` or `PLOSS_COEF3`, even 0, makes `ACT_SH_SPEED` required.

## Setup | Power Loss

| Path | Type | Purpose |
|---|---|---|
| `Input\PLOSS_COEF1` | real | c1, constant loss |
| `Input\PLOSS_COEF2` | real | c2, multiplies Q N^2 |
| `Input\PLOSS_COEF3` | real | c3, multiplies (Q N)^2 |
| `Input\PLOSS_UNITS` | power unit (e.g. `KW`, `HP`, `WATT`) | Unit of the loss and of c1 |
| `Input\PL_FLOW_UNIT` | flow unit (e.g. `cum/hr`) | Unit of Q |
| `Input\PL_SP_UNIT` | speed unit (e.g. `RPM`) | Unit of N |
| `Input\ACT_SH_SPEED` | FREQUENCY | Shaft speed N |
| `Input\PLOSS_FACTOR` | real | Factor on the correlation |
| `Input\PLOSS_OFFSET` | real | Added to the loss, in `PLOSS_UNITS` |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\POWER_LOSS` | POWER | Power loss |
