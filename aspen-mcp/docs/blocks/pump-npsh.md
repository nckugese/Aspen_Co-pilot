# Pump NPSH and specific speeds

Paths are under `\Data\Blocks\{name}\`. Fields of Setup | Calculation Options and Performance Curves | NPSHR.

`NPSH-AVAIL` comes with every run: the inlet pressure above the vapor pressure as head, plus `HEAD_STATIC` and the velocity head of the inlet flow through `SUCT_AREA`.

`NPSH_REQ` needs an NPSHR curve, which belongs to the performance curves (`OPT_SPEC=USE-CURVE`); its table `HR_FLOW` / `NPSHR_DATA` fills like the head table ([pump-curves.md](pump-curves.md)).

Given `ACT_SH_SPEED`, a run also reports `SP-SPEED` and `SUCT_SPEED` (units by `SPEED_UNITS`); `HEAD-COF` and `FLOW-COF` need `IMPELLER_DIA` as well.

## Setup | Calculation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\HEAD_STATIC` | HEAD | Static head of liquid above the suction, added to NPSH available |
| `Input\SUCT_AREA` | AREA | Suction area, for the velocity head |
| `Input\SPEED_UNITS` | `US`, `METRIC` | Units convention of the specific speeds |
| `Input\SP_SPEED` | real | Your Ns at the design (peak-efficiency) flow; echoed as `SP_SPEED_BEP` |
| `Input\SUCT_SPEED` | real | Your Nss at the design (peak-efficiency) flow; echoed as `SU_SPEED_BEP` |

## Performance Curves | NPSHR

| Path | Type | Purpose |
|---|---|---|
| `Input\HR_FLOW_UNIT` | flow unit | Unit of the NPSHR-curve flow |
| `Input\NPSHR_UNITS` | `METER`, `FT`, `J/KG`, ... | Unit of NPSH required |
| `Input\HR_FLOW\{k}\#i` | real | Flow of each point |
| `Input\NPSHR_DATA\{k}\<i+1>` | HEAD | NPSH required of each point |
| `Input\NPSHR_COEF1\{k}` | real | c1 of the NPSHR polynomial (`OPT_CFORMAT=POLY`; `NPSHR_COEF2`..`4` alike) |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\NPSH-AVAIL` | HEAD | NPSH available |
| `Output\HEAD_STAT` | HEAD | Static head used |
| `Output\NPSH_REQ` | HEAD | NPSH required |
| `Output\SP-SPEED` | real | Ns at the actual flow and speed |
| `Output\SUCT_SPEED` | real | Nss at the actual flow and speed |
| `Output\HEAD-COF` | real | Head coefficient |
| `Output\FLOW-COF` | real | Flow coefficient |
| `Output\SP_SPEED_BEP` | real | Echo of `SP_SPEED` |
