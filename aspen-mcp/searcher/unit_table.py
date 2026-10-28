"""Parse Aspen Plus rcunits.dat to map unit names → unitcol indices.

The file lists units per dimension in order; position = unitcol for
SetValueAndUnit().  We build two lookups:

  dimensions : {row_int: {"name": str, "aliases": [str], "units": [str]}}
  unit_index : {unit_name_lower: [{"dimension_row": int, "col": int}]}
"""

from __future__ import annotations

import difflib
import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate rcunits.dat
# ---------------------------------------------------------------------------

_DEFAULT_PATH = r"C:\Program Files\AspenTech\Aspen Plus V15.0\Engine\Xeq\rcunits.dat"


def _find_rcunits() -> str:
    """env ASPEN_RCUNITS_PATH; the Aspen that COM starts (the install aspen_strings finds,
    so another folder or version works); the newest %ProgramFiles%\\AspenTech\\Aspen Plus
    V*; the V15 default."""
    path = os.environ.get("ASPEN_RCUNITS_PATH", "")
    if path and os.path.isfile(path):
        return path
    tried = []
    try:
        from tools import aspen_strings                     # stdlib only, no I/O at import
        found = aspen_strings.find_dll()
    except Exception:  # noqa: BLE001 -- discovery is best effort
        found = None
    if found and found.get("aspen"):
        dll = Path(found["dll"])                             # ...\AprSystem V15.0\GUI\Xeq\<dll>
        root = next((p.parent for p in dll.parents if p.name.lower().startswith("aprsystem")), None)
        if root:
            cand = root / f"Aspen Plus {found['aspen']}" / "Engine" / "Xeq" / "rcunits.dat"
            tried.append(str(cand))
            if cand.is_file():
                return str(cand)
    best = None
    for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if not base:
            continue
        for d in Path(base, "AspenTech").glob("Aspen Plus V*"):
            f = d / "Engine" / "Xeq" / "rcunits.dat"
            key = tuple(int(n) for n in re.findall(r"\d+", d.name))
            if f.is_file() and (best is None or key > best[0]):
                best = (key, f)
    if best:
        return str(best[1])
    if os.path.isfile(_DEFAULT_PATH):
        return _DEFAULT_PATH
    raise FileNotFoundError(
        f"rcunits.dat not found (tried {', '.join(tried + [_DEFAULT_PATH])}). "
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


# Spellings Aspen does not list: micrometre is "micron" (also inside compound units, um/sec ->
# micron/sec), and another micro- unit is written "mu" (muS/m, muA/sqcm).
_ALIAS = {"um": "micron", "µm": "micron", "μm": "micron"}
_MICRO = ("µ", "μ")


def canonical(unit_name: str) -> str:
    """``unit_name`` with the aliases above replaced, token by token ("um/sec" -> "micron/sec")."""
    parts = re.split(r"([/*-])", str(unit_name).strip())
    out = []
    for t in parts:
        low = t.lower()
        if low in _ALIAS:
            t = _ALIAS[low]
        elif t[:1] in _MICRO and len(t) > 1:
            t = "mu" + t[1:]
        out.append(t)
    return "".join(out)


def lookup_unit(unit_name: str, dimension_row: int | None = None) -> int | None:
    """Return the unitcol index for a unit name (1-based, as COM expects), the name taken as
    written first, then with its aliases replaced (``canonical``).

    If dimension_row is given, only match within that dimension.
    Returns None if not found.
    """
    _ensure_loaded()
    for name in dict.fromkeys((str(unit_name).lower(), canonical(unit_name).lower())):
        entries = _unit_index.get(name, [])
        if dimension_row is not None:
            entries = [e for e in entries if e["dimension_row"] == dimension_row]
        if entries:
            return entries[0]["col"] + 1  # COM uses 1-based unitcol
    return None


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


def unit_at(dimension_row: int, col: int) -> str | None:
    """The unit name at 1-based ``col`` of a dimension (lookup_unit's inverse)."""
    units = list_units_for_dimension(dimension_row)
    return units[col - 1] if 0 < col <= len(units) else None


def closest(unit_name: str, dimension_row: int, n: int = 6) -> list[str]:
    """The units of a dimension whose names come closest to ``unit_name`` (case ignored)."""
    units = list(dict.fromkeys(list_units_for_dimension(dimension_row)))
    by_low = {u.lower(): u for u in units}
    hits = difflib.get_close_matches(canonical(unit_name).lower(), list(by_low), n=n, cutoff=0.3)
    return [by_low[h] for h in hits] or units[:n]


def dimension_name(dimension_row: int) -> str:
    """Return the dimension name for a row number."""
    _ensure_loaded()
    dim = _dimensions.get(dimension_row)
    return dim["name"] if dim else f"ROW-{dimension_row}"
