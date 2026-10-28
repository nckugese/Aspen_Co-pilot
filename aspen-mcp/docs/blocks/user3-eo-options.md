# USER3: EO options

Block Options | EO Options and Simulation Options of a USER3 block; the property, report and diagnostic sheets are in [common.md](common.md). Paths are under `\Data\Blocks\{name}\`.

| Path | Type | Purpose |
|---|---|---|
| `Input\AUTO_COMPS` | `ALWAYS`, `IF-NO-COMPS`, `NEVER` | Leave out of the model any component that enters under the `AUTO_COMPS_T` mole fraction |
| `Input\AUTO_COMPS_T` | fraction | Mole-fraction limit for that |
| `Input\RESTART` | `NO`, `YES` | Start each flash from the previous result |
