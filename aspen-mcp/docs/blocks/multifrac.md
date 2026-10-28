# MultiFrac

Several rigorous columns solved together and tied by connect streams: side strippers and rectifiers, a column split into two shells, prefractionators. Paths are under `\Data\Blocks\{name}\`; `{col}` is a column number, `{cs}` a connect-stream number; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feeds, `LD(OUT)` / `VD(OUT)` the liquid / vapor distillate, `B(OUT)` one bottoms stream, `SP(OUT)` side products, `PS(OUT)` pseudo streams, `HS(IN)` / `HS(OUT)` heat streams, `CWD(OUT)` free water. `B(OUT)` and `LD(OUT)` hold one stream each: take another column's bottoms or top product on `SP(OUT)`, from its bottom or top stage with phase `L` or `V`.

1. A new block already has column 1 and connect stream 1. `add_element` on `Subobjects\Columns` with `2`, `3`, ... adds columns and on `Subobjects\Connect Streams` adds connect streams; `NCOL` follows (writing it does nothing).
2. Connect the streams to the ports, then place each one on a column (`FEED_COL`, `PROD_COL`) and a stage.
3. Per column set the stages, condenser, reboiler, its specs and the top pressure; give each connect stream its source, destination and phase.
4. Give every column a temperature estimate for its top and its bottom stage: without them the column stays incomplete and the block does not run.

Column 1 takes one of `BASIS_D` / `BASIS_B` and one of `BASIS_RR`, `BASIS_L1`, `Q1`, `QN`; a condenser or reboiler set to `NONE` takes the place of the second one.

Every other column takes one spec per condenser or reboiler it has, from `BASIS_D`, `BASIS_B`, `Q1`, `QN` (`BASIS_RR` and `BASIS_L1` are refused); with neither it takes none.

A connect stream without a flow takes all the liquid leaving a bottom stage that has no reboiler or bottoms product, or all the vapor leaving a top stage without condenser.

Column 1's top vapor is its distillate: a connect stream cannot start there.

## Setup | Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\COLSP_NSTAGE\{col}` | int | Stages of the column (condenser = 1, reboiler = last) |
| `Input\CONDENSER\{col}` | `TOTAL`, `PARTIAL-V`, `PARTIAL-V-L`, `NONE` | Condenser of column 1 |
| `Input\CONDENSE2\{col}` | `NONE`, `PARTIAL-V` | Condenser of columns 2 and on (vapor distillate only); copied into `CONDENSER` |
| `Input\REBOILER\{col}` | `NONE`, `KETTLE` | Reboiler |
| `Input\BASIS_D\{col}` | MOLE-FLOW | Spec: distillate rate |
| `Input\BASIS_B\{col}` | MOLE-FLOW | Spec: bottoms rate |
| `Input\BASIS_RR\{col}` | ratio | Spec: reflux ratio (column 1) |
| `Input\BASIS_L1\{col}` | MOLE-FLOW | Spec: reflux rate (column 1) |
| `Input\Q1\{col}` | ENTHALPY-FLO | Spec: condenser duty, negative |
| `Input\QN\{col}` | ENTHALPY-FLO | Spec: reboiler duty |

## Streams

| Path | Type | Purpose |
|---|---|---|
| `Input\FEED_COL\{stream}` | int | Column a feed enters |
| `Input\FEED_STAGE\{stream}` | int | Feed stage |
| `Input\FEED_CONVEN\{stream}` | `ABOVE`, `ON` | Feed enters above the stage or on it |
| `Input\PROD_COL\{stream}` | int | Column a product leaves |
| `Input\PROD_STAGE\{stream}` | int | Draw stage of a stream on `SP(OUT)` |
| `Input\PROD_PHASE\{stream}` | `L`, `V` | Side-product phase |
| `Input\PROD_FLOW\{stream}` | MOLE-FLOW | Side-product rate |

## Connect Streams

| Path | Type | Purpose |
|---|---|---|
| `Input\SOURCE_COL\{cs}` | int | Column the stream is drawn from |
| `Input\SOURCE_STAGE\{cs}` | int | Draw stage |
| `Input\DEST_COL\{cs}` | int | Column it returns to |
| `Input\DEST_STAGE\{cs}` | int | Return stage |
| `Input\CS_PHASE\{cs}` | `L`, `V` | Phase drawn |
| `Input\BASIS_CSFLOW\{cs}` | flow | Flow drawn (left empty: all of it, see above) |
| `Input\CSFLOW_BASIS\{cs}` | `MOLE`, `MASS`, `STDVOL` | Basis of that flow |

## Setup | Pressure

| Path | Type | Purpose |
|---|---|---|
| `Input\PRES1\{col}` | PRESSURE | Top-stage pressure |
| `Input\OPT_DP\{col}` | `DPSTAGE`, `DPCOL` | Rest of the column from a drop per stage or for the column |
| `Input\DP_STAGE\{col}` | PDROP | Drop per stage |
| `Input\DP_COL\{col}` | PDROP | Drop over the column |

## Estimates | Temperature

| Path | Type | Purpose |
|---|---|---|
| `Input\TEMP_EST\{col}\{stage}` | TEMPERATURE | Stage temperature estimate (row: `insert_row` + `set_label` the stage on `TEMP_EST\{col}`) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\COND_Q_NSC\{col}` | ENTHALPY-FLO | Condenser duty |
| `Output\REB_DUTY\{col}` | ENTHALPY-FLO | Reboiler duty |
| `Output\MOLE_RR\{col}` | ratio | Molar reflux ratio |
| `Output\MOLE_D\{col}` | MOLE-FLOW | Net flow leaving the top stage |
| `Output\B_TEMP2\{col}\{stage}` | TEMPERATURE | Stage temperature |
| `Output\PROD_FLOW_MO\{stream}` | MOLE-FLOW | Product stream rate |

More: [condenser options](multifrac-condenser.md), [heaters and heat streams](multifrac-heaters.md), [design specs](multifrac-design-specs.md), [flow ratios and flow specs](multifrac-flow-specs.md), [efficiencies](multifrac-efficiencies.md), [convergence and estimates](multifrac-convergence.md), [tray and packing sizing](multifrac-sizing.md), [heating curves](multifrac-hcurves.md), [report, targeting, pseudo streams](multifrac-analysis.md), [property sections](multifrac-properties.md).

Not covered: Subroutines (user Fortran subroutines for tray and packing hydraulics); Free-water stages (free-water stage ranges; not checked).
