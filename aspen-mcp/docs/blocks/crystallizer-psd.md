# Crystallizer: size distribution

`OPT_PSD` sets the crystals' size distribution. It needs the `CIPSD` substream (`MIXCIPSD`) and a PSD mesh. Paths are under `\Data\Blocks\{name}\`; basics in [crystallizer.md](crystallizer.md).

`COPY` (default) and the growth rules act on the feed's crystals: on a clear feed `COPY` ended with a PSD warning, so the first crystallizer of a train needs `SPEC` or `GROWTH`.

| Path | Type | Purpose |
|---|---|---|
| `Input\OPT_PSD` | `COPY`, `SPEC`, `GROWTH`, `MCCABE`, `CONSTANT` | Copy the feed's distribution, specify it, compute it from kinetics ([growth](crystallizer-growth.md)), grow the feed crystals by McCabe's delta-L law, or by a `CONST_METHOD` rule |
| `Input\CONST_METHOD` | `DELTAD-NUM`, `DELTAD-MASS`, `DELTAV-MASS`, `DELTAV-NUM`, `EQUI-MASS`, `EQUI-SURFACE`, `EQUI-NUMBER` | `CONSTANT`: how added mass spreads over the sizes: equal steps in diameter (`DELTAD-`) or volume (`DELTAV-`) on a number or mass basis, or shares of the inlet mass, surface or number (`EQUI-`) |

## `SPEC`: distribution function

| Path | Type | Purpose |
|---|---|---|
| `Input\OV_PSDID` | mesh ID | PSD mesh of the specified distribution (`PSD`) |
| `Input\OPT_OVERALL` | `DISTFUN`, `TABULAR` | A distribution function (default) or tabulated weights |

1. Insert a row labeled `1` on `OV_DISTFUN`; it adds row `1` to `SPEC_OVOPT`, `OV_D50`, `OV_FRACTION` and the other `OV_*` lists.

| Path | Type | Purpose |
|---|---|---|
| `Input\OV_DISTFUN\1` | `GGS`, `RRSB`, `NORMAL`, `LOG-NORMAL` | Distribution function |
| `Input\SPEC_OVOPT\1` | `D63GGS`, `MGGS`, `D63D50`, `MD50`, `D50GGS`, `MD63`, `D50EDER`, `D50RRSB`, `D63EDER`, `D50SV`, `D63SV`, `D50GMV`, `D63GMV` | The two parameters that fix it, e.g. `D50RRSB` = D50 plus the RRSB n, `D50SV` = D50 plus `OV_STDDEV` |
| `Input\OV_D50\1` | LENGTH | Median size D50 |
| `Input\OV_D63\1` | LENGTH | Size D63 |
| `Input\OV_DIAM\1` | LENGTH | Largest particle size |
| `Input\OV_RRSBN\1` | real | RRSB dispersion n |
| `Input\OV_GGSN\1` | real | GGS dispersion n |
| `Input\OV_FRACTION\1` | fraction | Weight of this function (the rows sum to 1) |
| `Input\OV_STDDEV\1` | LENGTH | Standard deviation (`SV` codes) |
| `Input\OV_GMDEV\1` | real | Log-normal spread for the `GMV` codes (geometric deviation) |
| `Input\OV_STEEPNES\1` | real | Steepness (`EDER` codes), a value below 1: 1.5 is refused |

`SV` goes with `NORMAL` and `GMV` with `LOG-NORMAL`: the crossed pairs ended in block errors.

The function must fit the PSD mesh: `LOG-NORMAL`, D50 100 um, `OV_GMDEV` 1.2 left mass above the 500 um top size and ended with a warning; 0.3 converged.

## `SPEC`: table

| Path | Type | Purpose |
|---|---|---|
| `Input\OV_MESHOPT` | `PREDEF`, `LOCAL` | Global PSD mesh (default) or a local one |

Use `LOCAL` with `TABULAR`: weights on the global mesh left the block incomplete.

1. Insert one row per interval on `USER_OVLOWER` (`#0`, `#1`, ...); it adds the `USER_OVUPPER` and `USER_OVVALUE` rows.

| Path | Type | Purpose |
|---|---|---|
| `Input\USER_OVLOWER\{row}` | LENGTH | Lower size of the interval |
| `Input\USER_OVUPPER\{row}` | LENGTH | Upper size of the interval |
| `Input\USER_OVVALUE\{row}` | fraction | Weight fraction in the interval |
