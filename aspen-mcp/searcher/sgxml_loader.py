"""Parse Aspen Plus SGXML files to auto-discover block property definitions."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default SGXML directory shipped with Aspen Plus V15
DEFAULT_SGXML_DIR = r"C:\Program Files\AspenTech\Aspen Plus V15.0\GUI\Xeq\sgxml\ENG"

# Files that are NOT individual block definitions (summaries, cross-block views, etc.)
_SKIP_PREFIXES = (
    "Aplus-BlockSummaryDefinition",
    "Aplus-Columns",
    "Aplus-Design-Spec",
    "Aplus-Utilities",
    "Aplus-Stream-Price",
)

# DataType mapping from SGXML to our simplified types
_TYPE_MAP = {
    "real": "float",
    "integer": "integer",
    "string": "string",
}


def _convert_path(raw_path: str) -> str:
    """Convert an SGXML path like ``Input.TEMP`` to an Aspen COM path template.

    Examples::

        Input.TEMP          -> \\Data\\Blocks\\{block_name}\\Input\\TEMP
        Output.B_TEMP       -> \\Data\\Blocks\\{block_name}\\Output\\B_TEMP
        Input.STAGE_PRES.1  -> \\Data\\Blocks\\{block_name}\\Input\\STAGE_PRES\\1
        Input.D:F           -> \\Data\\Blocks\\{block_name}\\Input\\D:F
    """
    segments = raw_path.replace(".", "\\")
    return f"\\Data\\Blocks\\{{block_name}}\\{segments}"


def parse_sgxml_file(file_path: Path) -> dict[str, Any] | None:
    """Parse a single SGXML file and return block property definitions.

    Returns ``None`` if the file is not a block-type definition.
    """
    try:
        tree = ET.parse(file_path)
    except ET.ParseError:
        logger.warning("Failed to parse SGXML file: %s", file_path)
        return None

    root = tree.getroot()
    grid = root.find(".//Grid[@Type='Block']")
    if grid is None:
        return None

    block_type = grid.get("Caption", "")
    if not block_type:
        return None

    properties: dict[str, dict[str, Any]] = {}

    for var in grid.findall(".//Variable"):
        path_el = var.find("Path")
        if path_el is None or path_el.text is None:
            continue

        raw_path = path_el.text.strip()

        # Skip the #Name pseudo-path
        if raw_path.startswith("#"):
            continue

        display_el = var.find("DisplayName")
        dtype_el = var.find("DataType")
        readonly_el = var.find("ReadOnly")

        description = display_el.text.strip() if display_el is not None and display_el.text else ""
        raw_type = dtype_el.text.strip().lower() if dtype_el is not None and dtype_el.text else "string"
        read_only = (readonly_el.text.strip().lower() == "true") if readonly_el is not None and readonly_el.text else False

        # Property name = last meaningful segment of the path
        # e.g. Input.TEMP -> TEMP, Input.STAGE_PRES.1 -> STAGE_PRES.1, Output.B_TEMP -> B_TEMP
        parts = raw_path.split(".", 1)
        prop_name = parts[1] if len(parts) > 1 else parts[0]

        properties[prop_name] = {
            "aspen_path": _convert_path(raw_path),
            "type": _TYPE_MAP.get(raw_type, "string"),
            "description": description,
            "read_only": read_only,
        }

    return {
        "block_type": block_type,
        "properties": properties,
    }


def load_all_sgxml(sgxml_dir: str | None = None) -> dict[str, dict[str, Any]]:
    """Load all block definitions from SGXML files in the given directory.

    Returns a dict mapping ``block_type_lower`` to
    ``{"block_type": <original casing>, "properties": {prop_name: {...}}}``.
    Gracefully returns an empty dict if the directory doesn't exist.
    """
    if sgxml_dir is None:
        sgxml_dir = DEFAULT_SGXML_DIR

    sgxml_path = Path(sgxml_dir)
    if not sgxml_path.is_dir():
        logger.warning("SGXML directory not found: %s — falling back to YAML-only mode", sgxml_dir)
        return {}

    results: dict[str, dict[str, Any]] = {}

    for fp in sorted(sgxml_path.glob("Aplus-*.sgxml")):
        # Skip non-block summary/cross-block files
        if any(fp.stem.startswith(prefix.replace(".sgxml", "")) for prefix in _SKIP_PREFIXES):
            continue

        parsed = parse_sgxml_file(fp)
        if parsed is None:
            continue

        block_type = parsed["block_type"]
        key = block_type.lower()
        results[key] = parsed
        logger.debug("Loaded %d properties for %s from SGXML", len(parsed["properties"]), block_type)

    logger.info("Loaded %d block types from SGXML directory: %s", len(results), sgxml_dir)
    return results
