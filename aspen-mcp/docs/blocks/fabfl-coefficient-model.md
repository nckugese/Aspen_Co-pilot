# FabFl: coefficient model (air-to-cloth ratio)

The Operation Options sheet: a basic air-to-cloth ratio, corrected for the cleaning system, the filter element, the dust load and the dust. `MODE` `DESIGN` with `AREA_OPT` `FROM-ACRATIO` uses it ([design](fabfl-design.md)). Paths are under `\Data\Blocks\{name}\`; basics in [fabfl.md](fabfl.md).

It needs `ACRATIO`, `FILTER_SYS`, `FILTER_MED`, `FIELD` and `SOLDEN`.

Pairs that ran: `SHAKER` or `JET-VENTURI` with `BAGS` or `POCKETS`, `DIRECT-PULSE` with `SINGLE-BAG` or `MULTI-BAG`; any other pair stops with an error on the filter medium.

Each correction moved the area from 169 m2: `MED-CONC` 188, `HIGH-CONC` and `HYGROSCOPIC` 212, `SOLDEN` 2000 kg/m3 159, `ACRATIO` 0.03 m/s 113.

## Input | Operation Options

| Path | Type | Purpose |
|---|---|---|
| `Input\ACRATIO` | VELOCITY | Basic air-to-cloth ratio (gas volume flow per cloth area) |
| `Input\FILTER_SYS` | `SHAKER`, `DIRECT-PULSE`, `JET-VENTURI` | Cleaning system: shaker or reverse air, direct pulse, jet with venturi |
| `Input\FILTER_MED` | `BAGS`, `POCKETS`, `SINGLE-BAG`, `MULTI-BAG` | Filter element |
| `Input\FIELD` | `LOW-CONC`, `MED-CONC`, `HIGH-CONC` | Dust concentration class of the duty |
| `Input\SOLDEN` | DENSITY | Bulk density of the collected dust |
| `Input\HYGROSCOPIC` | `NO`, `YES` | Moist or hygroscopic dust in a humid climate |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TOT_AREA` | AREA | Filtering area found |
| `Output\VELOCITY` | VELOCITY | Gas velocity through the cloth |
