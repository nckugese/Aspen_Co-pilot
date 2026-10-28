# RStoic reaction heats

Paths are under `\Data\Blocks\{name}\`. Reports the heat of each reaction, or replaces it by a given value ([rstoic.md](rstoic.md)).

1. Write `CALCULATE` or `SPECIFY` to `Input\HEAT_OF_REAC`.
2. `insert_row` on `Input\HREF_CID` and `set_label` it with the reaction number; `H_REAC`, `REF_TEMP` and `REF_PRES` get the same entry.
3. `set_value` `HREF_CID\{id}`: the component the heat is counted per mole of; it must be a reactant of that reaction.

`CALCULATE` only reports the heat, from heats of formation; the duty is unchanged.

`SPECIFY` moves the duty by the extent times (given minus calculated heat); stream enthalpies stay as they are, and the input check warns about that.

## Setup | Reaction heats

| Path | Type | Purpose |
|---|---|---|
| `Input\HEAT_OF_REAC` | `NO-CALC-SPEC`, `CALCULATE`, `SPECIFY` | Not reported, calculated, or given |
| `Input\HREF_CID\{id}` | component ID | Reference component of that reaction |
| `Input\H_REAC\{id}` | MOLE-ENTHALP | Given heat of reaction per mole of the reference component (`SPECIFY`) |
| `Input\REF_TEMP\{id}` | TEMPERATURE | Temperature the heat value refers to |
| `Input\REF_PRES\{id}` | PRESSURE | Pressure the heat value refers to |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\HEAT_REAC\{id}` | MOLE-ENTHALP | Heat of reaction from heats of formation |
| `Output\R_HREAC\{id}` | MOLE-ENTHALP | Heat of reaction used (`SPECIFY`) |
| `Output\QCALC` | ENTHALPY-FLO | Heat duty |
