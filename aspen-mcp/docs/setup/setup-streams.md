# Stream class, PSD mesh, stream prices

Setup settings that every stream follows: the substreams it carries, the particle-size mesh, and a price.

Root: `\Data\Setup`

`Global\Input\SCLASS` sets the class ([setup.md](setup.md)); a class with `PSD` in its name carries the mesh below.

## PSD mesh

| Path | Type | Purpose |
|---|---|---|
| `Stream-Class\Subs-Attr\PSD\Input\TYPE` | `USER`, `EQUIDISTANT`, `GEOMETRIC`, `LOGARITHMIC` | How the size intervals are made; `USER`: you give each one |
| `Stream-Class\Subs-Attr\PSD\Input\INTERVALS` | int | Number of size intervals; the rows below follow it |
| `Stream-Class\Subs-Attr\PSD\Input\PARTICLESIZE\{row}` | LENGTH | Lower size of an interval |
| `Stream-Class\Subs-Attr\PSD\Input\PARTICLESIZ2\{row}` | LENGTH | Upper size of an interval |
| `Stream-Class\Subs-Attr\PSD\Input\LOWER` | LENGTH | Smallest size of a generated mesh |
| `Stream-Class\Subs-Attr\PSD\Input\UPPER` | LENGTH | Largest size of a generated mesh |
| `Stream-Class\Subs-Attr\PSD\Input\GMESH` | `YES`, `NO` | `YES`: fill the interval rows from `TYPE`, `INTERVALS`, `LOWER` and `UPPER`; a generated mesh needs it |

## Stream prices

1. `insert_row` on `Stream-Price\Input\PRICE`; label the row with the stream it prices (`set_label`).

| Path | Type | Purpose |
|---|---|---|
| `Stream-Price\Input\PRICE\{stream}` | UNIT-PRICE | Price per mass of that stream |

| Path | Type | Purpose |
|---|---|---|
| `Stream-Price\Output\COST\{stream}` | COST-RATE | Value of the stream per hour |

`COST` is the price times the stream's mass flow.
