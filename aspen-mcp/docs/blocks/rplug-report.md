# RPlug profile report

Paths are under `\Data\Blocks\{name}\`. How many profile points the results hold, and what the block report prints.

`NPOINT` = 20 gives 21 points in every `Output` profile.

## Report | Profiles

| Path | Type | Purpose |
|---|---|---|
| `Input\NPOINT` | int | Equally spaced intervals along the tube |
| `Input\PROFILE` | `PROFILE`, `NOPROFILE` | Profile tables on or off in the printed results |
| `Input\COMPS` | `COMPS`, `NOCOMPS` | Composition profiles in the report |
| `Input\USERVECS` | `USERVECS`, `NOUSERVECS` | User-subroutine vectors in the report |

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\B_TEMP\MIXED\{id}` | TEMPERATURE | Temperature at each of the `NPOINT` + 1 points |
