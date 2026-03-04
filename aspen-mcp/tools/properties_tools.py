"""Implementations for properties category tools.

get/set_property_method use manager.get_node_value/set_node_value (low-level).
add_component calls manager.get_app() and does COM operations directly.
"""

from __future__ import annotations


def get_property_method(manager, session_name: str) -> str:
    """Get the current global property method."""
    return manager.get_node_value(
        session_name, r"\Data\Properties\Specifications\Input\GOPSETNAME"
    )


def set_property_method(manager, session_name: str, method: str = "NRTL") -> str:
    """Set the global property method (e.g. NRTL, UNIQUAC, PENG-ROB, IDEAL)."""
    return manager.set_node_value(
        session_name, r"\Data\Properties\Specifications\Input\GOPSETNAME", method
    )


def add_component(manager, session_name: str, component_id: str) -> str:
    """Add a component to the simulation component list."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        node = app.Tree.FindNode(r"\Data\Components\Specifications\Input\TYPE")
        tlb = node.Elements
        tlb.InsertRow(0, 0)
        tlb.SetLabel(0, 0, False, component_id)
        return f"Component '{component_id}' added."
    except Exception as exc:
        return f"Failed to add component '{component_id}': {exc}"
