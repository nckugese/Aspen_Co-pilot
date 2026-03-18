# SSplit (Substream Splitter)

Splits feed into multiple outlets by substream. Unlike FSplit (which splits all substreams equally), SSplit can specify different split fractions for each substream (MIXED, CISOLID, etc.).

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| P | OUT | Product (multiple outlets) |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\FRAC\{stream}\MIXED` | float | Split fraction of MIXED substream to outlet |
| `\Data\Blocks\{name}\Input\BASIS_FLOW\{stream}\MIXED` | float | Flow rate of MIXED substream to outlet |

> Specify split fractions per substream per outlet. Leave one outlet unspecified as the balance stream.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\STREAMFRAC\{stream}\MIXED` | float | Calculated split fraction per stream |

## Typical Setup

1. Place: `place_block(session, 'SS1', 'SSplit')`
2. Connect multiple outlet streams.
3. Set split fractions per substream: `set_value(session, aspen_path='\Data\Blocks\SS1\Input\FRAC\S2\MIXED', value='0.3')`

## Gotchas

- Use SSplit (not FSplit) when you need different splits for MIXED vs. solid substreams.
- Leave one outlet as the balance stream (fractions must sum to 1.0 per substream).
