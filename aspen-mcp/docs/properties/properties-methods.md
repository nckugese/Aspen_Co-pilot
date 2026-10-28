# Property method options

Change the models inside the global method, or keep a named copy of a method.

Root: `\Data\Properties\Specifications`

## Models of the global method

A model field written here replaces that model in the global method: the run's input carries `ESRK` as a replacement in NRTL, and the field still reads `ESRK` after the run.

`GMODIFY` does not gate this: with `NO` the run takes `ESRK` all the same.

| Path | Type | Purpose |
|---|---|---|
| `Input\GMODIFY` | `YES`, `NO` | Flag of the GUI's modify sheet; model fields take effect either way |
| `Input\GVAPOREOS` | `ESIG`, `ESRK`, `ESPR` | Vapor equation of state (`ESIG` ideal gas) |
| `Input\GHEATOFMIX` | `YES`, `NO` | Include the mixing enthalpy in liquid enthalpies |
| `Input\GPOYNTING` | `YES`, `NO` | Poynting correction of liquid fugacities |
| `Input\GFREE_WATER` | `STEAM-TA`, `IAPWS-95`, `IDEAL` | How the free-water phase is computed |
| `Input\GSOLU_WATER` | `0`, `1`, `2`, `3`, `4`, `5` | Water solubility in the organic liquid, codes as the block field `SOLU_WATER` |
| `Input\GBASEOPSET` | method name | Base method; writing it also sets `GOPSETNAME` |

## A named copy of a method

1. `add_element` on `\Data\Properties\Property Methods` with a new ID.
2. Set its `Input\BASE`: the copy takes that method's property routes.
3. Set `GOPSETNAME` to the copy's ID.

| Path | Type | Purpose |
|---|---|---|
| `\Data\Properties\Property Methods\{method}\Input\BASE` | method name | Method the copy starts from |
| `\Data\Properties\Property Methods\{method}\Input\MPROP_NAME\{row}` | property (read) | Mixture property of one route row, e.g. `PHIVMX` |
| `\Data\Properties\Property Methods\{method}\Input\MROUTEID\{row}` | route ID (read) | Route that computes it |
| `\Data\Properties\Property Methods\{method}\Input\MODELNAME\{row}` | model name (read) | Model that route uses |
