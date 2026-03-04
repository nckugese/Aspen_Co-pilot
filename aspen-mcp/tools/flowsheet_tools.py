"""Implementations for flowsheet category tools.

Each function calls manager.get_app() to get the COM object directly,
and uses the searcher for type/port resolution.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aspen_manager import AspenPlusManager
    from searcher.definition_searcher import DefinitionSearcher


def place_block(
    manager: AspenPlusManager,
    searcher: DefinitionSearcher,
    session_name: str,
    block_name: str,
    block_type: str,
) -> str:
    """Place a new block on the flowsheet."""
    result = searcher.resolve_block_type(block_type)
    if result.matched:
        block_type = result.value

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
        return f"Failed to remove block '{block_name}': {exc}"


def place_stream(
    manager: AspenPlusManager,
    searcher: DefinitionSearcher,
    session_name: str,
    stream_name: str,
    stream_type: str = "MATERIAL",
) -> str:
    """Place a new stream on the flowsheet."""
    result = searcher.resolve_stream_type(stream_type)
    if result.matched:
        stream_type = result.value

    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        app.Tree.FindNode("\\Data\\Streams").Elements.Add(f"{stream_name}!{stream_type}")
        return f"Stream '{stream_name}' ({stream_type}) placed."
    except Exception as exc:
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
        return f"Failed to remove stream '{stream_name}': {exc}"


def connect_stream(
    manager: AspenPlusManager,
    searcher: DefinitionSearcher,
    session_name: str,
    block_name: str,
    stream_name: str,
    port_name: str,
    block_type: str | None = None,
) -> str:
    """Connect a stream to a block port.(port name: F(IN), LD(OUT), B(OUT)...)"""
    if block_type:
        result = searcher.resolve_port(block_type, port_name)
        if result.matched:
            port_name = result.value
        else:
            return f"Failed to connect stream '{stream_name}' to {block_name}:{port_name}: {result.message}"

    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        blocks = app.Tree.FindNode("\\Data\\Blocks")
        blocks.Elements(block_name).Elements("Ports").Elements(port_name).Elements.Add(stream_name)
        return f"Stream '{stream_name}' connected to {block_name} port {port_name}."
    except Exception as exc:
        return f"Failed to connect stream '{stream_name}' to {block_name}:{port_name}: {exc}"
