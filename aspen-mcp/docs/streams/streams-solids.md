# Solids substreams

A stream class with solids gives each stream substreams beside `MIXED`, each with its own state, flows and attributes.

Root: `\Data\Streams\{id}`

The global stream class picks the substreams (`\Data\Setup\Global\Input\SCLASS`): `MIXCISLD` adds `CISOLID`, `MIXCIPSD` adds `CIPSD`, `MIXNC` adds `NC`.

## Conventional solids

| Path | Type | Purpose |
|---|---|---|
| `Input\TEMP\CISOLID` | TEMPERATURE | Solids temperature |
| `Input\PRES\CISOLID` | PRESSURE | Solids pressure |
| `Input\FLOW\CISOLID\{solid}` | MOLE-FLOW | Flow of one solid; `basis=` as for `MIXED` |

## Particle size distribution

The intervals come from the class's PSD mesh (`\Data\Setup\Stream-Class\Subs-Attr\PSD\Input`, lower and upper size per row in `PARTICLESIZE` / `PARTICLESIZ2`); the stream gets one row per interval.

| Path | Type | Purpose |
|---|---|---|
| `Input\SUBSATT\CIPSD\{row}` | fraction | Mass fraction of the solid in one interval (`#0` the finest) |
| `Input\SUBSATT_OPT\CIPSD` | `FRAC`, `CUM-FRAC` | Fractions per interval, or cumulative |
| `Input\CUM_SUBSATT\CIPSD\{row}` | fraction | Cumulative fraction up to the interval's upper size |
| `Input\PSDID\CIPSD` | ID | Mesh the distribution uses |

Cumulative input comes back per interval: 0.02, 0.07, 0.17, ... gave 0.02, 0.05, 0.10, ...

| Path | Type | Purpose |
|---|---|---|
| `Output\SUBS-ATTR\CIPSD\{n}\PSD` | fraction | Fraction in interval `{n}` (1 the finest) |

## Nonconventional solids

An NC component needs enthalpy and density models (`\Data\Properties\Advanced\NC-Props\Input\ENTH_MODEL\{nc}`, `DENS_MODEL\{nc}`); coal with `HCOALGEN` and `DCOALIGT` asks for `PROXANAL`, `ULTANAL` and `SULFANAL`, and the stream gets one row list per attribute.

| Path | Type | Purpose |
|---|---|---|
| `Input\TEMP\NC` | TEMPERATURE | NC substream temperature |
| `Input\FLOW\NC\{nc}` | MASS-FLOW | Flow of the NC component, on a mass basis |
| `Input\ELEM\NC\{nc}\{attr}\{row}` | real | One element of an attribute, in its order (`PROXANAL`: moisture, fixed carbon, volatile matter, ash) |

The order holds in the results: `PROXANAL` `#0` came back as moisture, `ULTANAL` `#1` as carbon.

| Path | Type | Purpose |
|---|---|---|
| `Input\NEL\NC\{nc}\{attr}` | int | Elements the attribute has (read only) |
| `Input\ATTOTAL\NC\{nc}\{attr}` | real | Sum of the elements entered (read only) |
| `Output\COMP_ATTR\{elem}\{attr}\{nc}\NC` | real | Value of one element after the run |
