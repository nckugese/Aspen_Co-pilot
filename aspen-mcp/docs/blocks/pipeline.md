# Pipeline

A line of pipe segments joined at nodes, each with its own length, diameter and slope; gives the pressure and temperature profile along the line. For one pipe use Pipe. Paths are under `\Data\Blocks\{name}\`; rules shared by all blocks: [common.md](common.md).

Ports: `F(IN)` feed, `P(OUT)` product.

To run it needs at least one segment with an inlet node, an outlet node, a length and an inner diameter (with `XYZ`: the end coordinates instead of length and angle).

## Segments

1. `insert_row` on `Input\INNODE` with the segment ID as label (`1`, `2`, ...); every per-segment field gets that row.
2. Fill the row: nodes, length, diameter, angle. Segment 2 starts at segment 1's outlet node; the nodes name the result profiles.

## Setup | Configuration

| Path | Type | Purpose |
|---|---|---|
| `Input\PIPE_METH` | `FLUID`, `SOLIDS` | Fluid flow, or pneumatic solids conveying ([pipeline-solids.md](pipeline-solids.md)) |
| `Input\PRES_CALC` | `OUTLET`, `INLET` | Which end's pressure is calculated |
| `Input\P_INLET` | PRESSURE | Inlet pressure, replaces the feed's (`OUTLET`) |
| `Input\T_INLET` | TEMPERATURE | Inlet temperature, replaces the feed's (`OUTLET`) |
| `Input\P_OUTLET` | PRESSURE | Outlet pressure to reach (`INLET`) |
| `Input\T_OUTLET` | TEMPERATURE | Outlet temperature (`INLET`) |
| `Input\FLOW_CALC` | `OUTLET`, `INLET` | Flow and composition taken from the feed, or from the product stream's own input |
| `Input\OPT_SGEOM` | `LTHETA`, `XYZ` | Segment geometry by length and angle, or by end coordinates |
| `Input\THERMAL` | `NO`, `YES` | Temperature given, or from an energy balance ([pipeline-heat-transfer.md](pipeline-heat-transfer.md)) |

`P_INLET` / `T_INLET` override the feed: the run with 10 bar and 40 C starts the line at those values.

With `FLOW_CALC=INLET` give the product stream a flow and composition; the feed's results take them. Left empty, the block warns and uses the feed.

## Setup | Connectivity (one row per segment)

| Path | Type | Purpose |
|---|---|---|
| `Input\INNODE\{seg}` | string | Inlet node name |
| `Input\OUTNODE\{seg}` | string | Outlet node name |
| `Input\LENGTH\{seg}` | LENGTH | Segment length (`LTHETA`) |
| `Input\ANGLE\{seg}` | ANGLE | Slope from horizontal, upward positive (`LTHETA`) |
| `Input\INNERD\{seg}` | LENGTH | Inner diameter |
| `Input\ROUGH\{seg}` | LENGTH | Wall roughness |
| `Input\OUTERD\{seg}` | LENGTH | Outer diameter |
| `Input\IN_CERO\{seg}` | real | Erosional-velocity coefficient at the inlet node (`OUT_CERO`: outlet) |
| `Input\IN_ELEV\{seg}` | LENGTH | Inlet node elevation (`XYZ`); `IN_XLEN`, `IN_YLEN` the plan position; `OUT_ELEV`, `OUT_XLEN`, `OUT_YLEN` for the outlet node |

| Path | Type | Purpose |
|---|---|---|
| `Output\B_PRES_IN` | PRESSURE | Inlet pressure |
| `Output\B_PRES_OUT` | PRESSURE | Outlet pressure |
| `Output\B_TEMP_OUT` | TEMPERATURE | Outlet temperature |
| `Output\ENTH_BAL` | ENTHALPY-FLO | Heat duty of the line |
| `Output\HOLDUP_OUT2` | VOLUME | Liquid volume held in the line |
| `Output\IN_PRES_OUT\{node}` | PRESSURE | Pressure at each node (`1` = inlet) |
| `Output\DPTOTL\{node}` | PRESSURE | Drop over the segment ending at that node; `DPFRIC`, `DPELEV`, `DPACC` its friction, elevation and acceleration parts |
| `Output\CUM_DPTOTL\{node}` | PRESSURE | Drop from the inlet to that node |
| `Output\REGIME\{node}` | string | Two-phase pattern at that node |
| `Output\LIQ_VEL\{node}` | VELOCITY | Liquid velocity (`GAS_VEL` gas, `ERO_VEL` erosional limit) |

More: [heat transfer](pipeline-heat-transfer.md), [methods](pipeline-methods.md), [convergence](pipeline-convergence.md), [solids conveying](pipeline-solids.md), [properties and flash](pipeline-properties.md).

Not covered: Results form (result sheets; the key results are in each file's Results); Subroutines (pressure drop, holdup) (user Fortran subroutines).
