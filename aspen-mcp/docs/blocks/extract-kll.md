# Extract K-values

Paths are under `\Data\Blocks\{name}\`.

A component's liquid-liquid K-value is its 2nd liquid mole fraction over its 1st liquid mole fraction.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_KLL` | `PROPMETH`, `COEFFICIENT` | Where K-values come from: the property method or a correlation |
| `Input\KLL_BASIS` | `MOLE`, `MASS`, `STDVOL` | Fraction basis of the correlation |

## Correlation (`OPT_KLL=COEFFICIENT`, rows labelled by component)

ln K = `KLL_A` + `KLL_B`/T, T in K: with `KLL_A` alone K = exp(`KLL_A`).

A component row added to `KLL_A` also appears in `KLL_B`, `KLL_C` and `KLL_D`.

| Path | Type | Purpose |
|---|---|---|
| `Input\KLL_A\{comp}` | real | Constant term of ln K |
| `Input\KLL_B\{comp}` | real | Term divided by the absolute temperature |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\KLL_OUT\{stage}\{comp}` | real | K-value used on a stage |
