# Design spec

Moves one input between two limits until an expression of defined variables equals its target.

Root: `\Data\Flowsheeting Options\Design-Spec\{id}`

1. `add_element` on `\Data\Flowsheeting Options\Design-Spec` with an ID.
2. Define the variables it reads ([flowsheeting.md](flowsheeting.md#define-a-variable)).
3. Write `EXPR1`, `EXPR2` and `TOL`.
4. Pick the input to vary ([flowsheeting.md](flowsheeting.md#vary-an-input)) and give `LOWER` and `UPPER`.

The varied input keeps its own value in `Input`: the flash still reads 95 C there while it ran at the 94.73 C the spec found, which is also `Output\FINAL_VAL\1`.

## Spec

| Path | Type | Purpose |
|---|---|---|
| `Input\EXPR1` | expression | Expression of defined variables (Fortran syntax), e.g. `VF` |
| `Input\EXPR2` | expression | Target: a number or an expression |
| `Input\TOL` | expression | Tolerance on the difference between the two |

## Vary

| Path | Type | Purpose |
|---|---|---|
| `Input\LOWER` | expression | Lower limit of the varied input |
| `Input\UPPER` | expression | Upper limit |

The limits are in the unit of `VARYUOM` and the target in that of `FVN_UOM`: 363.15-372.15 K with a target of 11.1111 mol/sec end at the same 94.73 C as the base run.

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\BLKSTAT` | int | 0 when the target was met |
| `Output\FINAL_VAL\{n}` | real | Final values: 1 is the varied input, then each defined variable |
| `Output\VARID\{n}` | string | Their names, in the same order |
| `Output\VAR_UNIT\{n}` | unit | Their units |
