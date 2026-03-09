"""Parse Aspen Plus rcunits.dat to map unit names → unitcol indices.

The file lists units per dimension in order; position = unitcol for
SetValueAndUnit().  We build two lookups:

  dimensions : {row_int: {"name": str, "aliases": [str], "units": [str]}}
  unit_index : {unit_name_lower: [{"dimension_row": int, "col": int}]}
"""

from __future__ import annotations

import os
import re

# ---------------------------------------------------------------------------
# Locate rcunits.dat
# ---------------------------------------------------------------------------

_DEFAULT_PATH = r"C:\Program Files\AspenTech\Aspen Plus V15.0\Engine\Xeq\rcunits.dat"


def _find_rcunits() -> str:
    path = os.environ.get("ASPEN_RCUNITS_PATH", "")
    if path and os.path.isfile(path):
        return path
    if os.path.isfile(_DEFAULT_PATH):
        return _DEFAULT_PATH
    raise FileNotFoundError(
        f"rcunits.dat not found at '{_DEFAULT_PATH}'. "
        "Set ASPEN_RCUNITS_PATH to override."
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# Dimension header:  "    01       07         AREA"
_DIM_RE = re.compile(
    r"^\s+(\d+)\s+(\d+)\s+(\S+)(?:\s+(\S+))?(?:\s+(\S+))?\s*$"
)

# Unit line:  "    sqm                 1.000000000000000E+00"
# May have optional gauge offset:  "    psig   6.89...E+03   -99999.0"
_UNIT_RE = re.compile(
    r"^\s+(\S+)\s+([\d.eEdD+-]+)(?:\s+([\d.eEdD+-]+))?\s*$"
)


def parse_rcunits(path: str | None = None):
    """Return (dimensions, unit_index) parsed from rcunits.dat."""
    if path is None:
        path = _find_rcunits()

    dimensions: dict[int, dict] = {}
    unit_index: dict[str, list[dict]] = {}

    current_row: int | None = None
    expected_count = 0
    col = 0

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n\r")

            # Skip comments
            if line.lstrip().startswith("/*") or line.lstrip().startswith("/**"):
                continue
            # Skip the "ADD UNITS TABLE" header
            if "ADD UNITS" in line and "TABLE" in line:
                continue
            # Skip the total-count header line (e.g. "    113 + 42 UNIT-TYPES FOLLOW")
            if "UNIT-TYPES FOLLOW" in line:
                continue

            # Try dimension header
            m = _DIM_RE.match(line)
            if m:
                current_row = int(m.group(1))
                expected_count = int(m.group(2))
                dim_name = m.group(3)
                aliases = [a for a in [m.group(4), m.group(5)] if a]
                dimensions[current_row] = {
                    "name": dim_name,
                    "aliases": aliases,
                    "units": [],
                }
                col = 0
                continue

            # Try unit line
            if current_row is not None:
                mu = _UNIT_RE.match(line)
                if mu:
                    unit_name = mu.group(1)
                    dimensions[current_row]["units"].append(unit_name)

                    key = unit_name.lower()
                    if key not in unit_index:
                        unit_index[key] = []
                    unit_index[key].append({
                        "dimension_row": current_row,
                        "col": col,
                    })
                    col += 1

                    if col >= expected_count:
                        current_row = None
                    continue

    return dimensions, unit_index


# ---------------------------------------------------------------------------
# Module-level singleton (loaded once at import)
# ---------------------------------------------------------------------------

_dimensions: dict[int, dict] | None = None
_unit_index: dict[str, list[dict]] | None = None


def _ensure_loaded():
    global _dimensions, _unit_index
    if _dimensions is None:
        _dimensions, _unit_index = parse_rcunits()


def get_dimensions() -> dict[int, dict]:
    _ensure_loaded()
    return _dimensions


def get_unit_index() -> dict[str, list[dict]]:
    _ensure_loaded()
    return _unit_index


def lookup_unit(unit_name: str, dimension_row: int | None = None) -> int | None:
    """Return the unitcol index for a unit name (1-based, as COM expects).

    If dimension_row is given, only match within that dimension.
    Returns None if not found.
    """
    _ensure_loaded()
    entries = _unit_index.get(unit_name.lower(), [])
    if not entries:
        return None
    if dimension_row is not None:
        for e in entries:
            if e["dimension_row"] == dimension_row:
                return e["col"] + 1  # COM uses 1-based unitcol
        return None
    return entries[0]["col"] + 1  # COM uses 1-based unitcol


def find_dimension_by_unit(unit_name: str) -> int | None:
    """Return the dimension row number that contains this unit name."""
    _ensure_loaded()
    entries = _unit_index.get(unit_name.lower(), [])
    return entries[0]["dimension_row"] if entries else None


def list_units_for_dimension(dimension_row: int) -> list[str]:
    """Return all unit names for a given dimension row."""
    _ensure_loaded()
    dim = _dimensions.get(dimension_row)
    return dim["units"] if dim else []


def dimension_name(dimension_row: int) -> str:
    """Return the dimension name for a row number."""
    _ensure_loaded()
    dim = _dimensions.get(dimension_row)
    return dim["name"] if dim else f"ROW-{dimension_row}"
