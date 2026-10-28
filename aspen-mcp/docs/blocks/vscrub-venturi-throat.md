# VScrub: venturi throat

Throat shape and size of a `VENTURI` in `SIMULATION` mode. Paths are under `\Data\Blocks\{name}\`; basics in [vscrub.md](vscrub.md).

Each shape takes its own size fields; one left blank keeps the block incomplete.

With `GASVEL-SEL` the block sizes the throat from `GAS_VEL`; `YUNG` still needs `LEN_THROAT`.

| Path | Type | Purpose |
|---|---|---|
| `Input\THROAT_SHAPE` | `ROUND`, `ANNULAR`, `SQUARE`, `RECTANGULAR` | Throat cross-section (default `ROUND`) |
| `Input\SIMPARA_OPT` | `THRGEO-SEL`, `GASVEL-SEL` | Give the throat size (default) or the throat gas velocity |
| `Input\IN_DIAM` | LENGTH | `ANNULAR`: inner edge of the ring-shaped gap |
| `Input\OUT_DIAM` | LENGTH | `ANNULAR`: outer diameter, larger than `IN_DIAM` |
| `Input\WIDTH` | LENGTH | `SQUARE`, `RECTANGULAR`: throat width |
| `Input\HEIGHT` | LENGTH | `RECTANGULAR`: throat height |
| `Input\GAS_VEL` | VELOCITY | `GASVEL-SEL`: throat gas velocity, 10 to 200 m/s |
| `Input\OD:ID` | ratio | `GASVEL-SEL`, `ANNULAR`: outer over inner diameter (default 2) |
| `Input\W:H` | ratio | `GASVEL-SEL`, `RECTANGULAR`: width over height (default 2) |

## Results (after a run)

| Path | Type | Purpose |
|---|---|---|
| `Output\DIAM` | LENGTH | Round throat diameter, given or sized |
| `Output\INSIDE_DIAM` | LENGTH | Annular inner diameter (`OUTSIDE_DIAM` the outer) |
| `Output\WIDTH` | LENGTH | Throat width (`HEIGHT` likewise) |
| `Output\LENGTH` | LENGTH | Throat length |
| `Output\LIQ_RATIO` | ratio | Droplet over gas velocity at the throat exit |
