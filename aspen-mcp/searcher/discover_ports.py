"""Auto-discover block ports via COM API.

Places a temporary block of each known type, reads its Ports children,
then removes it. Results are saved to block_ports.json for use by
DefinitionSearcher.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .sgxml_loader import load_all_sgxml

if TYPE_CHECKING:
    from aspen_manager import AspenPlusManager

logger = logging.getLogger(__name__)

PORTS_JSON = Path(__file__).resolve().parent / "block_ports.json"

TEMP_BLOCK_NAME = "ZTMPDISC"


def discover_ports(
    manager: "AspenPlusManager",
    session_name: str,
    sgxml_dir: str | None = None,
) -> tuple[dict[str, list[str]], list[str]]:
    """Discover ports for all SGXML block types using a live Aspen session.

    For each block type:
      1. Place a temporary block
      2. Read children of \\Data\\Blocks\\{name}\\Ports
      3. Remove the temporary block

    Returns (results_dict, errors_list).
    results_dict maps block_type (original casing) -> [port_name, ...].
    Also saves results to block_ports.json.
    """
    app = manager.get_app(session_name)
    if app is None:
        raise RuntimeError(f"No active session named '{session_name}'.")

    # Get all block types from SGXML
    sgxml_blocks = load_all_sgxml(sgxml_dir)
    if not sgxml_blocks:
        from .sgxml_loader import DEFAULT_SGXML_DIR
        used_dir = sgxml_dir or DEFAULT_SGXML_DIR
        raise RuntimeError(
            f"No block types found in SGXML. "
            f"Checked directory: {used_dir} "
            f"(exists={Path(used_dir).is_dir()})"
        )

    blocks_node = app.Tree.FindNode("\\Data\\Blocks")
    if blocks_node is None:
        raise RuntimeError("Cannot find \\Data\\Blocks in the simulation tree.")

    results: dict[str, list[str]] = {}
    errors: list[str] = []

    for key, parsed in sgxml_blocks.items():
        block_type = parsed["block_type"]
        logger.info("Discovering ports for %s ...", block_type)

        try:
            # Place temporary block
            blocks_node.Elements.Add(f"{TEMP_BLOCK_NAME}!{block_type}")
            time.sleep(0.3)

            # Read ports
            ports_path = f"\\Data\\Blocks\\{TEMP_BLOCK_NAME}\\Ports"
            ports_node = app.Tree.FindNode(ports_path)

            port_names: list[str] = []
            if ports_node is not None:
                for i in range(ports_node.Elements.Count):
                    port_names.append(ports_node.Elements.Item(i).Name)

            results[block_type] = port_names
            logger.info("  %s -> %d ports: %s", block_type, len(port_names), port_names)

        except Exception as exc:
            errors.append(f"{block_type}: {exc}")
            logger.warning("  Failed for %s: %s", block_type, exc)
        finally:
            # Always try to remove the temp block
            try:
                blocks_node.Elements.Remove(TEMP_BLOCK_NAME)
                time.sleep(0.1)
            except Exception:
                pass

    # Merge with existing JSON (preserve manually added entries like MHeatX)
    existing: dict[str, list[str]] = {}
    if PORTS_JSON.is_file():
        try:
            existing = json.loads(PORTS_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # New discoveries overwrite, but keep entries that weren't re-discovered
    merged = {**existing, **results}
    PORTS_JSON.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    logger.info("Saved port definitions for %d block types to %s", len(merged), PORTS_JSON)

    return results, errors
