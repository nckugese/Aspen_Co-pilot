# Extract heat streams

Paths are under `\Data\Blocks\{name}\`.

Connect the heat stream first: its stage entry, keyed by the stream name, appears then.

| Path | Type | Purpose |
|---|---|---|
| `Input\H_FEED_STAGE\{heat}` | int | Stage an inlet heat stream (`HS(IN)`) goes to |

Its duty is added to that stage.

| Path | Type | Purpose |
|---|---|---|
| `Input\H_PROD_STAGE\{heat}` | int | Stage whose duty an outlet heat stream (`HS(OUT)`) carries |

The outlet heat stream carries the duty that holds its stage at the set temperature.

## Results

| Path | Type | Purpose |
|---|---|---|
| `Output\DUTY\{stage}` | ENTHALPY-FLO | Stage duty, the heat stream's included |
