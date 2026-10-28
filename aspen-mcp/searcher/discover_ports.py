"""Auto-discover block ports via COM API.

Places a temporary block of each requested type, reads its Ports children, then removes it.

Two port tables, one view:
  PORTS_JSON  shipped with the package, read only (an upgrade replaces it)
  USER_PORTS  ~/.aspen-mcp/block_ports.json -- only what discover_ports found; overlays PORTS_JSON
PORTS is the merged view the tools use. reload_ports() refreshes it in place, so every
module holding a reference to it (flowsheet_tools._PORTS) sees new discoveries at once.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from tools import dialogs

if TYPE_CHECKING:
    from aspen_manager import AspenPlusManager

logger = logging.getLogger(__name__)

PORTS_JSON = Path(__file__).resolve().parent / "block_ports.json"
USER_PORTS = Path.home() / ".aspen-mcp" / "block_ports.json"

TEMP_BLOCK_NAME = "ZTMPDISC"

PORTS: dict[str, list[str]] = {}


def _read(path: Path) -> dict[str, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_ports() -> dict[str, list[str]]:
    """The shipped table with the user's discoveries laid over it, one entry per type whatever
    the case (Aspen's type names ignore it: a discovery of "MULTIFRAC" replaces "MultiFrac"),
    under the first spelling seen."""
    out: dict[str, list[str]] = {}
    spelled: dict[str, str] = {}
    for table in (_read(PORTS_JSON), _read(USER_PORTS)):
        for typ, ports in table.items():
            out[spelled.setdefault(str(typ).upper(), str(typ))] = list(ports or [])
    return out


def ports_for(block_type) -> list[str]:
    """The ports of ``block_type`` in PORTS, its case ignored; [] when the type is not listed."""
    key = str(block_type or "").upper()
    hit = PORTS.get(block_type) if block_type in PORTS else next(
        (v for k, v in PORTS.items() if k.upper() == key), None)
    return list(hit or [])


def reload_ports() -> dict[str, list[str]]:
    """Re-read both tables into PORTS, keeping the same dict object."""
    fresh = load_ports()
    PORTS.clear()
    PORTS.update(fresh)
    return PORTS


reload_ports()


def _save_user_ports(results: dict[str, list[str]]) -> None:
    merged = {**_read(USER_PORTS), **results}
    USER_PORTS.parent.mkdir(parents=True, exist_ok=True)
    tmp = USER_PORTS.with_name(USER_PORTS.name + ".tmp")
    tmp.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, USER_PORTS)


def _free_block_name(tree) -> str:
    """A block name nobody uses, so the temp block can never be (or delete) a user's block."""
    for name in (TEMP_BLOCK_NAME, *(f"ZTMPD{i:03d}" for i in range(1, 1000))):
        if tree.FindNode(f"\\Data\\Blocks\\{name}") is None:
            return name
    raise RuntimeError("No free temporary block name (ZTMPDISC, ZTMPD001..ZTMPD999 all taken).")


@dialogs.quiet
def discover_ports(
    manager: "AspenPlusManager",
    session_name: str,
    block_types: list[str] | None = None,
) -> tuple[dict[str, list[str]], list[str]]:
    """Discover ports for block types using a live Aspen session.

    For each block type: place a temporary block under a free name, read the children of
    \\Data\\Blocks\\{name}\\Ports, remove the block. Blocks already in the model are never
    touched.

    Args:
        block_types: Block type names to discover. If None, every type in the shipped
                     table and the user's table.

    Returns (results, errors): results maps block_type -> [port_name, ...]. Results are
    saved to USER_PORTS and take effect immediately (PORTS is reloaded).
    """
    app = manager.get_app(session_name)
    if app is None:
        raise RuntimeError(f"No active session named '{session_name}'.")

    if block_types is None:
        block_types = list(load_ports())
    if not block_types:
        raise RuntimeError("No block types to discover. Provide block_types.")

    blocks_node = app.Tree.FindNode("\\Data\\Blocks")
    if blocks_node is None:
        raise RuntimeError("Cannot find \\Data\\Blocks in the simulation tree.")

    temp = _free_block_name(app.Tree)
    temp_path = f"\\Data\\Blocks\\{temp}"
    results: dict[str, list[str]] = {}
    errors: list[str] = []

    for block_type in block_types:
        if app.Tree.FindNode(temp_path) is not None:   # a previous removal failed
            errors.append(f"temporary block {temp} could not be removed; stopped before {block_type}")
            break
        logger.info("Discovering ports for %s ...", block_type)
        try:
            blocks_node.Elements.Add(f"{temp}!{block_type}")
            time.sleep(0.3)

            ports_node = app.Tree.FindNode(f"{temp_path}\\Ports")
            port_names: list[str] = []
            if ports_node is not None:
                for i in range(ports_node.Elements.Count):
                    port_names.append(ports_node.Elements.Item(i).Name)

            if port_names:
                results[block_type] = port_names
                logger.info("  %s -> %d ports: %s", block_type, len(port_names), port_names)
            else:   # an empty entry would mask the shipped one
                errors.append(f"{block_type}: no ports found (not a block type?)")
        except Exception as exc:
            errors.append(f"{block_type}: {exc}")
            logger.warning("  Failed for %s: %s", block_type, exc)
        finally:
            try:   # the name was free before we added it, so this only removes our own block
                blocks_node.Elements.Remove(temp)
                time.sleep(0.1)
            except Exception:
                pass

    if results:
        try:
            _save_user_ports(results)
            logger.info("Saved port definitions for %d block types to %s", len(results), USER_PORTS)
        except OSError as exc:
            errors.append(f"not saved to {USER_PORTS} (in effect until restart): {exc}")
        reload_ports()
        PORTS.update(results)   # already there when the save worked; kept for this process if not

    return results, errors
