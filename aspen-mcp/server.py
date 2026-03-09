"""Aspen Plus MCP Server — entry point.

All tools are registered directly via @mcp.tool().
No dynamic activation/deactivation — every tool is always available.
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from aspen_manager import AspenPlusManager
from searcher import DefinitionSearcher
from tools import main_tools, flowsheet_tools, block_tools, stream_tools, create_tools
from tools.properties_tools import get_property_method as _get_prop, set_property_method as _set_prop, add_component as _add_comp, remove_component as _rm_comp
from searcher.tool_searcher import search_properties as _search_props
from searcher.discover_ports import discover_ports as _discover_ports

# ------------------------------------------------------------------
# Core objects
# ------------------------------------------------------------------

mcp = FastMCP(name="aspen-plus")
manager = AspenPlusManager()

SGXML_DIR = os.environ.get("ASPEN_SGXML_DIR", None)
searcher = DefinitionSearcher(sgxml_dir=SGXML_DIR)

# ==================================================================
# Main tools (5)
# ==================================================================

@mcp.tool()
def open_aspen_plus(file_path: str) -> str:
    """Open Aspen Plus and load a .bkp simulation file"""
    return main_tools.open_aspen_plus(manager, file_path)


@mcp.tool()
def close_aspen_plus(session_name: str = None) -> str:
    """Close an Aspen Plus session"""
    return main_tools.close_aspen_plus(manager, session_name)


@mcp.tool()
def list_aspen_sessions() -> str:
    """List all active Aspen Plus sessions"""
    return main_tools.list_aspen_sessions(manager)


@mcp.tool()
def reinit_simulation(session_name: str) -> str:
    """Reinitialize the block solver in a given session"""
    return main_tools.reinit_simulation(manager, session_name)


@mcp.tool()
def run_simulation(session_name: str) -> str:
    """Run the simulation in a given session"""
    return main_tools.run_simulation(manager, session_name)


@mcp.tool()
def save_simulation(session_name: str, file_path: str = None) -> str:
    """Save the current simulation to disk"""
    return main_tools.save_simulation(manager, session_name, file_path)


@mcp.tool()
def check_inputs(session_name: str) -> str:
    """Check if all required inputs are complete before running.
    
    Walks the data tree to find all incomplete input nodes.
    Call this before run_simulation to ensure nothing is missing.
    """
    return main_tools.check_inputs(manager, session_name)


@mcp.tool()
def get_node_value(session_name: str, aspen_path: str) -> str:
    """Read a raw value from the Aspen Plus data tree by path.

    Use list_node_children to explore available paths first.
    Example: '\\Data\\Blocks\\HEATER1\\Input\\TEMP'
    """
    return main_tools.get_node_value(manager, session_name, aspen_path)


@mcp.tool()
def set_node_value(session_name: str, aspen_path: str, value: str, unit: str = None) -> str:
    """Write a raw value to the Aspen Plus data tree by path.

    Use list_node_children to explore available paths first.
    Example: set_node_value(session, '\\Data\\Blocks\\HEATER1\\Input\\TEMP', '100')
    Optionally specify unit (e.g. 'atm', 'C', 'bar') to set value with unit conversion.
    """
    return main_tools.set_node_value(manager, session_name, aspen_path, value, unit=unit)


@mcp.tool()
def get_node_unit_info(session_name: str, aspen_path: str) -> str:
    """Get unit information for a node: current unit, dimension, and all available units.

    Example: get_node_unit_info(session, '\\Data\\Blocks\\COMP\\Input\\PRES')
    """
    return main_tools.get_node_unit_info(manager, session_name, aspen_path)


@mcp.tool()
def list_node_children(session_name: str, aspen_path: str) -> str:
    """List all child elements of a node in the Aspen Plus data tree.

    Use this to explore the tree structure.
    Example paths: '\\Data\\Properties\\Parameters', '\\Data\\Blocks'
    """
    return main_tools.list_node_children(manager, session_name, aspen_path)



# ==================================================================
# Flowsheet tools (5)
# ==================================================================

@mcp.tool()
def place_block(session_name: str, block_name: str, block_type: str) -> str:
    """Place a new block on the flowsheet"""
    return flowsheet_tools.place_block(manager, searcher, session_name, block_name, block_type)


@mcp.tool()
def remove_block(session_name: str, block_name: str) -> str:
    """Remove a block from the flowsheet"""
    return flowsheet_tools.remove_block(manager, session_name, block_name)


@mcp.tool()
def place_stream(session_name: str, stream_name: str, stream_type: str) -> str:
    """Place a new stream on the flowsheet"""
    return flowsheet_tools.place_stream(manager, searcher, session_name, stream_name, stream_type)


@mcp.tool()
def remove_stream(session_name: str, stream_name: str) -> str:
    """Remove a stream from the flowsheet"""
    return flowsheet_tools.remove_stream(manager, session_name, stream_name)


@mcp.tool()
def connect_stream(session_name: str, block_name: str, stream_name: str, port_name: str, block_type: str) -> str:
    """Connect a stream to a block port"""
    return flowsheet_tools.connect_stream(manager, searcher, session_name, block_name, stream_name, port_name, block_type)


# ==================================================================
# Property method tools (2)
# ==================================================================

@mcp.tool()
def get_property_method(session_name: str) -> str:
    """Get the current global property method"""
    return _get_prop(manager, session_name)


@mcp.tool()
def set_property_method(session_name: str, method: str) -> str:
    """Set the global property method (e.g. NRTL, UNIQUAC, PENG-ROB, IDEAL)"""
    return _set_prop(manager, session_name, method)


@mcp.tool()
def add_component(session_name: str, component_id: str) -> str:
    """Add a component to the simulation component list (e.g. WATER, ETHANOL, METHANOL).

    Accepts any component name, synonym, CAS number, or short ID.
    Long names are auto-resolved via the Aspen databank.
    """
    return _add_comp(manager, session_name, component_id)


@mcp.tool()
def remove_component(session_name: str, component_id: str) -> str:
    """Remove a component from the simulation component list by its label ID"""
    return _rm_comp(manager, session_name, component_id)


# ==================================================================
# Block tools (2)
# ==================================================================

@mcp.tool()
def get_block_value(
    session_name: str,
    block_name: str,
    block_type: str,
    property_name: str,
    extra_params: dict | None = None,
) -> str:
    """Get a property value from an Aspen Plus block.

    Use search_properties to find available block_type and property_name values.
    extra_params is for properties with additional placeholders (e.g. {"stream_name": "FEED"} for feed_stage).
    """
    return block_tools.get_block_value(
        manager, searcher, session_name, block_name, block_type, property_name, extra_params
    )


@mcp.tool()
def set_block_value(
    session_name: str,
    block_name: str,
    block_type: str,
    property_name: str,
    value: str,
    extra_params: dict | None = None,
    unit: str = None,
) -> str:
    """Set a property value on an Aspen Plus block.

    Use search_properties to find available block_type and property_name values.
    extra_params is for properties with additional placeholders (e.g. {"stream_name": "FEED"} for feed_stage).
    Optionally specify unit (e.g. 'atm', 'C', 'bar') to set value with unit conversion.
    """
    return block_tools.set_block_value(
        manager, searcher, session_name, block_name, block_type, property_name, value, extra_params, unit=unit
    )


# ==================================================================
# Stream tools (2)
# ==================================================================

@mcp.tool()
def get_stream_value(
    session_name: str,
    stream_name: str,
    stream_type: str,
    property_name: str,
    extra_params: dict | None = None,
) -> str:
    """Get a property value from an Aspen Plus stream.

    Use search_properties to find available stream_type and property_name values.
    extra_params is for properties with additional placeholders (e.g. {"component": "WATER"}).
    """
    return stream_tools.get_stream_value(
        manager, searcher, session_name, stream_name, stream_type, property_name, extra_params
    )


@mcp.tool()
def set_stream_value(
    session_name: str,
    stream_name: str,
    stream_type: str,
    property_name: str,
    value: str,
    extra_params: dict | None = None,
    unit: str = None,
) -> str:
    """Set a property value on an Aspen Plus stream.

    Use search_properties to find available stream_type and property_name values.
    extra_params is for properties with additional placeholders (e.g. {"component": "WATER"}).
    Optionally specify unit (e.g. 'atm', 'C', 'bar') to set value with unit conversion.
    """
    return stream_tools.set_stream_value(
        manager, searcher, session_name, stream_name, stream_type, property_name, value, extra_params, unit=unit
    )


# ==================================================================
# Search tool (1)
# ==================================================================

@mcp.tool()
def search_properties(query: str) -> str:
    """Search available block/stream properties by keyword.

    Returns matching property names, types, and descriptions.
    Example: search_properties("radfrac reflux") or search_properties("temperature").

    Use search_properties to find available block_type and property_name values.
    """
    return _search_props(searcher, query)


# ==================================================================
# Discovery tool (1)
# ==================================================================

@mcp.tool()
def discover_ports(session_name: str) -> str:
    """Auto-discover block ports for all known block types via COM API.

    Places a temporary block of each type, reads its ports, removes it,
    and saves results to block_ports.json. Requires an active Aspen session
    (preferably a blank simulation).
    """
    try:
        results, errors = _discover_ports(manager, session_name, SGXML_DIR)
        searcher.reload()
        summary_lines = [f"Discovered ports for {len(results)} block types:"]
        for bt, ports in sorted(results.items()):
            summary_lines.append(f"  {bt}: {', '.join(ports) if ports else '(none)'}")
        if errors:
            summary_lines.append(f"\nFailed for {len(errors)} block types:")
            for err in errors:
                summary_lines.append(f"  {err}")
        return "\n".join(summary_lines)
    except Exception as exc:
        return f"Port discovery failed: {exc}"


# ==================================================================
# Create tool (1)
# ==================================================================

@mcp.tool()
def create_tool(
    name: str,
    category: str,
    description: str = "",
    block_type: str = None,
    stream_type: str = None,
    properties: list[dict] = None,
) -> str:
    """Create a new tool definition by writing a YAML file to the definitions/ directory.

    Args:
        name: Unique tool name.
        category: Category path (e.g. "blocks/mixer").
        description: Human-readable description.
        block_type: Aspen block type (for block tools).
        stream_type: Aspen stream type (for stream tools).
        properties: List of property dicts with keys: name, aspen_path, type, description.
    """
    return create_tools.create_tool(
        searcher, name, category, description, block_type, stream_type, properties
    )


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
