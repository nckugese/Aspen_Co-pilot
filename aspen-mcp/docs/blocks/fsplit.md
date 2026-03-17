# FSplit (Stream Splitter)

Splits one inlet stream into multiple outlet streams by fraction.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| HS | IN | Heat stream |
| WS | IN | Work stream |
| PS | IN | Pseudo stream |
| P | OUT | Product (multiple) |
| HS | OUT | Heat stream out |
| WS | OUT | Work stream out |
| PS | OUT | Pseudo stream out |

## Key Input Paths

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\FRAC\{stream}` | float | Split fraction for each outlet stream |

## Typical Setup Steps

1. Place: `place_block(session, 'SP1', 'FSplit')`
2. Connect multiple outlet streams
3. Set fractions: `set_value(session, aspen_path='\Data\Blocks\SP1\Input\FRAC\S2', value='0.3')`
4. Leave one stream unspecified (it gets the balance)

## Gotchas

- Fractions must sum to 1.0. Leave one outlet without a fraction — it becomes the balance stream.
