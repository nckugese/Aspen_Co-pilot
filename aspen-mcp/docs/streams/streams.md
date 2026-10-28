# Material streams

A material stream carries components between blocks; as a feed it needs two state variables and its flows.

Root: `\Data\Streams\{id}`

Every input keyword ends in the substream: `Input\TEMP\MIXED`; a solids substream has its own ID in that place ([solids](streams-solids.md)).

`place_stream` writes names in upper case. It refuses a name of more than 8 characters, or with a character other than letters, digits and `-`, and names one that fits: a longer name made another way connects and runs, but the stream gets no results.

## Connecting

`connect_stream` on an outlet that holds a stream puts the new stream there and leaves the old one unconnected (an FSplit outlet takes several).

Connecting a stream to another port of the same direction moves it there: no `disconnect_stream` first.

`disconnect_stream` takes a stream off a port and its inputs stay; `remove_stream` deletes the stream and its inputs.

## Input | Specifications

| Path | Type | Purpose |
|---|---|---|
| `Input\MIXED_SPEC\MIXED` | `TP`, `TV`, `PV` | Which two state variables are given: T, P, vapor fraction |
| `Input\TEMP\MIXED` | TEMPERATURE | Temperature |
| `Input\PRES\MIXED` | PRESSURE | Pressure |
| `Input\VFRAC\MIXED` | fraction | Vapor fraction (`TV`, `PV`) |
| `Input\FLOW\MIXED\{comp}` | `MOLE-FLOW`, `MASS-FLOW`, `STDVOL-FLOW`, `MOLE-FRAC`, `MASS-FRAC`, `STDVOL-FRAC`, `MOLE-CONC`, `MASS-CONC` | Amount of one component, in the basis it was entered with |
| `Input\TOTFLOW\MIXED` | `MOLE`, `MASS`, `STDVOL`, `VOLUME` | Total flow; needed with fractions or concentrations |
| `Input\BASIS\MIXED` | `MOLE-CONC`, `MASS-CONC` | Concentration basis, written as well (steps below) |
| `Input\SOLVENT\MIXED` | component | Solvent of a concentration basis |

The basis comes with the value: `set_value(..., basis='MASS-FLOW')` on the first component (`basis='MASS'` on `TOTFLOW`); later values without `basis` keep it.

`BASIS` or `FLOWBASE` written by itself does not change what the run uses: 3000 entered after `BASIS` `MASS-FLOW` ran as 3000 kmol/hr.

With `TOTFLOW` set, component flows are scaled to it: 30 and 20 kmol/hr with a total of 100 ran as 60 and 40.

Concentrations:

1. Write each solute's concentration with `basis='MOLE-CONC'` or `'MASS-CONC'`.
2. Write `TOTFLOW` as a volume flow (`basis='VOLUME'`).
3. Write the same code in `Input\BASIS\MIXED` and the solvent in `Input\SOLVENT\MIXED`; without the code the solvent is not passed on and the run stops at input.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\TEMP_OUT\MIXED` | TEMPERATURE | Temperature |
| `Output\PRES_OUT\MIXED` | PRESSURE | Pressure |
| `Output\VFRAC_OUT\MIXED` | fraction | Vapor fraction |
| `Output\MOLEFLMX\MIXED` | MOLE-FLOW | Total mole flow |
| `Output\MASSFLMX\MIXED` | MASS-FLOW | Total mass flow |
| `Output\VOLFLMX\MIXED` | VOLUME-FLOW | Actual volume flow |
| `Output\MOLEFLOW\MIXED\{comp}` | MOLE-FLOW | Component flow, mole basis |
| `Output\MOLEFRAC\MIXED\{comp}` | fraction | Component share, mole basis |
| `Output\MASSFLOW\MIXED\{comp}` | MASS-FLOW | Component flow, mass basis |
| `Output\MASSFRAC\MIXED\{comp}` | fraction | Component share, mass basis |
| `Output\TOT_FLOW` | MOLE-FLOW | Total mole flow over all substreams |
| `Output\RES_TEMP` | TEMPERATURE | Stream temperature, all substreams |
| `Output\RES_PRES` | PRESSURE | Stream pressure, all substreams |

More: [flash options, reference temperatures, price](streams-options.md), [solids substreams](streams-solids.md), [heat and work streams](streams-heat-work.md), [tear estimates](streams-estimates.md).

Not covered: EO options (material), EO model components, EO options (heat) (equation-oriented settings, not checked); Stream attribute mesh (its keyword is not in the tree); Heat load curves (class LOAD needs a stream attribute the test did not define; did not run); PSD distribution functions (written over COM they leave the distribution empty).
