"""Implementations for flowsheet category tools.

Each function calls manager.get_app() to get the COM object directly.
Port resolution uses a simple JSON lookup from block_ports.json.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from aspen_manager import AspenPlusManager

# Load port definitions from JSON (once at import time)
_PORTS_JSON = Path(__file__).resolve().parent.parent / "searcher" / "block_ports.json"
_PORTS: dict[str, list[str]] = {}
if _PORTS_JSON.exists():
    with open(_PORTS_JSON, encoding="utf-8") as f:
        _PORTS = json.load(f)


def _resolve_port(block_type: str, port_name: str) -> str | None:
    """Resolve a port name using block_ports.json. Returns matched port or None."""
    ports = _PORTS.get(block_type, [])
    if not ports:
        return None
    # Exact match
    if port_name in ports:
        return port_name
    # Case-insensitive match
    upper = port_name.upper()
    for p in ports:
        if p.upper() == upper:
            return p
    return None


def place_block(
    manager: AspenPlusManager,
    session_name: str,
    block_name: str,
    block_type: str,
) -> str:
    """Place a new block on the flowsheet."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        path = f"\\Data\\Blocks\\{block_name}"
        node = app.Tree.FindNode(path)
        if node is not None:
            return f"Block '{block_name}' already exists."

        blocks_node = app.Tree.FindNode("\\Data\\Blocks")
        blocks_node.Elements.Add(f"{block_name}!{block_type}")
        time.sleep(0.5)
        return f"Block '{block_name}' ({block_type}) placed."
    except Exception as exc:
        logger.error("Failed to place block '%s': %s", block_name, exc, exc_info=True)
        return f"Failed to place block '{block_name}': {exc}"


def remove_block(manager: AspenPlusManager, session_name: str, block_name: str) -> str:
    """Remove a block from the flowsheet."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        app.Tree.FindNode("\\Data\\Blocks").Elements.Remove(block_name)
        return f"Block '{block_name}' removed."
    except Exception as exc:
        logger.error("Failed to remove block '%s': %s", block_name, exc, exc_info=True)
        return f"Failed to remove block '{block_name}': {exc}"


def place_stream(
    manager: AspenPlusManager,
    session_name: str,
    stream_name: str,
    stream_type: str = "MATERIAL",
) -> str:
    """Place a new stream on the flowsheet."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        app.Tree.FindNode("\\Data\\Streams").Elements.Add(f"{stream_name}!{stream_type}")
        return f"Stream '{stream_name}' ({stream_type}) placed."
    except Exception as exc:
        logger.error("Failed to place stream '%s': %s", stream_name, exc, exc_info=True)
        return f"Failed to place stream '{stream_name}': {exc}"


def remove_stream(manager: AspenPlusManager, session_name: str, stream_name: str) -> str:
    """Remove a stream from the flowsheet."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        app.Tree.FindNode("\\Data\\Streams").Elements.Remove(stream_name)
        return f"Stream '{stream_name}' removed."
    except Exception as exc:
        logger.error("Failed to remove stream '%s': %s", stream_name, exc, exc_info=True)
        return f"Failed to remove stream '{stream_name}': {exc}"


def connect_stream(
    manager: AspenPlusManager,
    session_name: str,
    block_name: str,
    stream_name: str,
    port_name: str,
    block_type: str | None = None,
) -> str:
    """Connect a stream to a block port.(port name: F(IN), LD(OUT), B(OUT)...)"""
    if block_type:
        resolved = _resolve_port(block_type, port_name)
        if resolved:
            port_name = resolved

    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        blocks = app.Tree.FindNode("\\Data\\Blocks")
        block_node = blocks.Elements(block_name)
        ports_node = block_node.Elements("Ports")
        port_node = ports_node.Elements(port_name)
        if port_node is None:
            return (f"Port '{port_name}' not found on block '{block_name}'."
                    " Use discover_ports to see valid port names.")
        port_els = port_node.Elements
        if port_els is None:
            return (f"Port '{port_name}' not found on block '{block_name}'."
                    " Use discover_ports to see valid port names.")

        # For output ports (non-feed), auto-disconnect existing stream if occupied
        is_output = "(OUT)" in port_name.upper()
        if is_output and port_els.Count > 0:
            old_stream = port_els.Item(0).Name
            try:
                port_els.Remove(old_stream)
                logger.info("Auto-disconnected stream '%s' from %s:%s", old_stream, block_name, port_name)
            except Exception as rm_exc:
                logger.warning("Could not auto-disconnect '%s' from %s:%s: %s",
                               old_stream, block_name, port_name, rm_exc)

        port_els.Add(stream_name)
        return f"Stream '{stream_name}' connected to {block_name} port {port_name}."
    except Exception as exc:
        logger.error("Failed to connect stream '%s' to %s:%s: %s", stream_name, block_name, port_name, exc, exc_info=True)
        return f"Failed to connect stream '{stream_name}' to {block_name}:{port_name}: {exc}"
