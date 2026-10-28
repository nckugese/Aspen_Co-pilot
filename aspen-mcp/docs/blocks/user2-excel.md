# USER2: Excel model

Instead of a compiled subroutine, USER2 can hand each pass to an Excel workbook: Aspen writes the inlets and parameters into fixed sheets, recalculates, and reads the outlets back. Excel must be installed. Paths are under `\Data\Blocks\{name}\`.

## Setting it up (in this order)

1. Copy `userxltemplate.xls` from `<Aspen Plus>\Engine\User`; it carries the four interface sheets and the macros Aspen calls at each pass.
2. Build the model in formulas: `Aspen_Input` has one column per inlet (column B = first), `Aspen_Output` one per outlet; both list the component flows, then `TOTFLOW`, `TEMP`, `PRES`, `ENTHALPY`, `VAP FRAC`, `LIQ FRAC`, `ENTROPY`, `DENSITY`, `MOLE WT`, in the SI units of [user2.md](user2.md).
3. Parameters: `Aspen_IntParams` and `Aspen_RealParams` hold INT and REAL in column B from row 2; Aspen writes them before the recalculation and reads them back after.
4. Set `Input\EXCEL_FILE` to the workbook's full path and leave `USRMODEL` empty (Aspen's own Excel routine runs); no linker file is needed.

| Path | Type | Purpose |
|---|---|---|
| `Input\EXCEL_FILE` | file path (.xls, .xlsm, .xlsb) | Workbook that holds the model |

Formulas in `Aspen_Output` survive the run; the template's end-of-run macro saves the workbook, with a values copy of the outputs in sheet `Aspen_Output_<block>`.
