# RStoic combustion

Paths are under `\Data\Blocks\{name}\`. `COMBUSTION` `YES` adds the burning reactions of the fuel components by itself ([rstoic.md](rstoic.md)).

No reaction needs to be entered; the generated ones are listed in `REAC_STOI`. With oxygen to spare the fuel burns out to carbon dioxide and water and nitrogen passes unchanged.

`PROD_NOX` picks the oxide nitrogen oxides leave as: `NO` turns NO2 into NO, `NO2` turns NO into NO2.

## Setup | Combustion

| Path | Type | Purpose |
|---|---|---|
| `Input\COMBUSTION` | `NO`, `YES` | Generate the burning reactions |
| `Input\PROD_NOX` | `NO`, `NO2` | Nitrogen oxide the products hold |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP` | TEMPERATURE | Outlet temperature (adiabatic flame temperature with duty 0) |
| `Output\REAC_STOI\{id}` | text | Each generated reaction |
