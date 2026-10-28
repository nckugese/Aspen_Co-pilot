# Chemistry (electrolytes)

Equilibrium reactions among ions and molecules in the liquid phase; an electrolyte property method solves them in every block.

Root: `\Data\Reactions\Chemistry\{id}`

## Build

1. `add_component` for the molecules and the ions; ion IDs such as `H3O+`, `OH-`, `HCO3-`, `CO3--` resolve from the databank with their charge.
2. A Henry set with the dissolved gases, named in `GHEN` ([properties-henry.md](properties-henry.md)).
3. `set_property_method` with an electrolyte method, e.g. `ENRTL-RK`.
4. `create_chemistry` with the reactions. It saves the model, writes the object into the .bkp and reopens the file, so the session closes for a few seconds; `bind_global` (default) sets `GCHEMISTRY`.

Electrolyte pair parameters need no input: the run's input carries the databank values.

`set_value` cannot add a reaction: a row written on `RXNID` is gone at the next read.

Each reaction is `{reactants: {id: coef}, products: {id: coef}}` with positive coefficients. Without `keq` its equilibrium constant comes from Gibbs energies in the databank; `keq` `{A, B, C, D}` gives `ln(K) = A + B/T + C*ln(T) + D*T` with T in kelvin and K on the `KBASIS` basis.

A created reaction's values can be changed with `set_value`; write `A` to `D` together.

## Fields

| Path | Type | Purpose |
|---|---|---|
| `Input\RXNID\{row}` | text | Reaction number |
| `Input\RXNTYPE\{row}` | text | Reaction type (`Equilibrium`) |
| `Input\RXNSTRING\{row}` | text (read) | The reaction as text |
| `Input\COEF\{n}\{comp}` | real | Reactant coefficient, negative |
| `Input\COEF1\{n}\{comp}` | real | Product coefficient |
| `Input\A\{n}` | real | `A` of ln K; likewise `B\{n}`, `C\{n}`, `D\{n}` |
| `Input\STOIC_OPTION\{n}` | `YES` | ln K from `A` to `D` |

## Options

| Path | Type | Purpose |
|---|---|---|
| `Input\KBASIS` | `MOLEFRAC`, `MOLAL`, `PARTIALPRES` | Basis of K |
| `Input\GAMMA_BASIS` | `UNSYMMETRIC`, `SYMMETRIC` | Reference state of the activity coefficients |
| `Input\OPT_REACTYPE` | `REACTION` | Reactions are listed one by one (what create_chemistry writes) |
| `\Data\Properties\Specifications\Input\GCHEMISTRY` | ID | Chemistry used by every block |
| `\Data\Properties\Specifications\Input\GTRUE_COMPS` | `YES`, `NO` | Results in true species (ions) or apparent components; `NO` only with an electrolyte method |
| `\Data\Components\Specifications\Input\CHARGE\{comp}` | int (read) | Charge of an ion, from the databank |

With `GTRUE_COMPS` `NO` the stream results give apparent components: the ions read 0.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `\Data\Streams\{stream}\Output\MOLEFRAC\MIXED\{comp}` | fraction | Liquid composition by true species, e.g. `HCO3-` |
