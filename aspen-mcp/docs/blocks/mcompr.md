# MCompr

Multistage gas compressor: compression stages in series, each followed by a cooler that can drop liquid into a knockout stream. Paths are under `\Data\Blocks\{name}\`; `{stage}` is a stage number. Rules shared by all blocks: [common.md](common.md).

Ports: `S1F(IN)` feed to stage 1, `IF(IN)` feeds entering later stages, `FLS(OUT)` product of the last stage, `LK(OUT)` liquid knocked out by the coolers ([mcompr-feeds-knockout.md](mcompr-feeds-knockout.md)), `WD(OUT)` total work; `WS`/`HS` in and out for work and heat streams.

1. Set `NSTAGE`, `TYPE` and `OPT_SPEC`.
2. Create the stage rows: `insert_row` on `Input\OPT_CSPEC` with labels `1` to `NSTAGE`. Each row appears in every per-stage table below (`SEFF`, `CL_TEMP`, `PDROP`, ...); until then they are empty.
3. Give the outlet spec (`PRES`, or a spec per stage) and a cooler spec at least on stage 1.

A stage without a cooler spec takes the one of the stage before it: 40 C on stage 1 alone cools all three stages to 40 C.

`OPT_SPEC=PRES` spreads the given final pressure over the stages with the same pressure ratio each (`TYPE_STG=HEAD`: the same head each).

`OPT_SPEC=SPEC` needs a spec on every stage, all of the same kind: once stage 1 has a code, another code on a later stage is refused.

Blank efficiencies default to 0.72.

## Setup | Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\NSTAGE` | int | Number of stages |
| `Input\TYPE` | `ISENTROPIC`, `GPSA-POLYTROPIC`, `GPSA-ISENTROPIC`, `ASME-POLYTROPIC`, `ASME-ISENTROPIC`, `POS-DISP` | Compression model: isentropic (Mollier), GPSA or ASME polytropic/isentropic methods, positive displacement |
| `Input\OPT_SPEC` | `PRES`, `SPEC`, `NCURVES` | Outlet spec: final pressure of the last stage, a spec for each stage, or performance curves ([mcompr-curves.md](mcompr-curves.md)) |
| `Input\PRES` | PRESSURE | Final pressure after the last stage (`OPT_SPEC=PRES`) |
| `Input\TYPE_STG` | `P-RATIO`, `HEAD` | How `OPT_SPEC=PRES` splits the work: equal pressure ratios or equal heads |
| `Input\GPSA_BASIS` | `SUCTION`, `AVERAGE` | GPSA types: properties at suction or averaged over the stage |

## Setup | Specs (per stage)

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_CSPEC\{stage}` | `PRES`, `DELP`, `PRATIO`, `POWER` | Spec of the stage (`OPT_SPEC=SPEC`): discharge pressure, pressure rise, ratio or brake power |
| `Input\C_S_PRES\{stage}` | PRESSURE | Stage discharge pressure (absolute) |
| `Input\DELP\{stage}` | PDROP | Rise from stage inlet to stage outlet |
| `Input\PRATIO\{stage}` | ratio | Outlet over inlet pressure for this stage |
| `Input\POWER\{stage}` | POWER | Brake power of the stage |
| `Input\SEFF\{stage}` | fraction | Isentropic efficiency (isentropic types) |
| `Input\PEFF\{stage}` | fraction | Polytropic efficiency (polytropic types) |
| `Input\MEFF\{stage}` | fraction | Mechanical efficiency (brake power = fluid power / MEFF) |

## Setup | Cooler (per stage)

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_CLSPEC\{stage}` | `TEMP`, `DUTY`, `TRATIO` | Cooler spec: outlet temperature, duty, or outlet/inlet temperature ratio |
| `Input\CL_TEMP\{stage}` | TEMPERATURE | Cooler outlet temperature |
| `Input\DUTY\{stage}` | ENTHALPY-FLO | Cooler duty (negative removes heat) |
| `Input\TRATIO\{stage}` | ratio | Cooler outlet over inlet temperature (absolute) |
| `Input\PDROP\{stage}` | PDROP | Pressure drop over the cooler (default 0) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\WNET` | POWER | Total brake power |
| `Output\QNET` | ENTHALPY-FLO | Total cooler duty |
| `Output\B_PRES2` | PRESSURE | Final discharge pressure |
| `Output\B_PRES\{stage}` | PRESSURE | Outlet pressure, per stage |
| `Output\B_TEMP\{stage}` | TEMPERATURE | Compressor outlet temperature of each stage |
| `Output\BRAKE_POWER\{stage}` | POWER | Brake power of each stage |
| `Output\EFFICIENCY\{stage}` | fraction | Efficiency used for each stage |
| `Output\COOL_TEMP\{stage}` | TEMPERATURE | Cooler outlet temperature |

More: [performance curves](mcompr-curves.md), [side feeds and knockout liquids](mcompr-feeds-knockout.md), [convergence and phases](mcompr-convergence.md), [cooler heating curves](mcompr-hcurves.md).

Not covered: Dynamics (Aspen Dynamics only); User subroutines (user Fortran subroutines); Stage outlet temperature (a stage outlet temperature (`OPT_TEMP`, `TEMP`) replaces the pressure spec and the block always ends with a warning); Heat and work streams (heat and work stream stage assignments, not writable through the tree); Wheel specs (wheel-by-wheel curves, not checked).
