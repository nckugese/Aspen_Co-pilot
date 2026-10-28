# Report options

What the run report (`.rep`) prints.

Root: `\Data\Setup`

| Path | Type | Purpose |
|---|---|---|
| `ReportOptions\Report\Input\REPORT` | `REPORT`, `NOREPORT` | Write a report at all |
| `ReportOptions\Report\Input\INPUT` | `NOINPUT`, `INPUT` | Print the input file |
| `ReportOptions\Report\Input\BLOCKS` | `BLOCKS`, `NOBLOCKS` | Print the block sections |
| `ReportOptions\Report\Input\STREAMS` | `STREAMS`, `NOSTREAMS` | Print the stream table |
| `ReportOptions\Block-Report\Input\TOTBAL` | `TOTBAL`, `NOTOTBAL` | Per-block totals in and out (mass, energy) |
| `ReportOptions\Block-Report\Input\COMPBAL` | `NOCOMPBAL`, `COMPBAL` | Component balance per block |
| `ReportOptions\Flowsheet-Report\Input\COMPBAL` | `COMPBAL`, `NOCOMPBAL` | Component balance of the whole flowsheet |
| `ReportOptions\Stream-Report\Input\MOLEFLOW` | `MOLEFLOW`, `NOMOLEFLOW` | Stream table: mole flows |
| `ReportOptions\Stream-Report\Input\MASSFLOW` | `NOMASSFLOW`, `MASSFLOW` | Stream table: mass flows |
| `ReportOptions\Stream-Report\Input\MOLEFRAC` | `NOMOLEFRAC`, `MOLEFRAC` | Stream table: mole fractions |
| `ReportOptions\Stream-Report\Input\MASSFRAC` | `NOMASSFRAC`, `MASSFRAC` | Stream table: mass fractions |
| `ReportOptions\Stream-Report\Input\ZEROFLOW` | `ZEROFLOW`, `NOZEROFLOW` | Keep components with zero flow in the table |
