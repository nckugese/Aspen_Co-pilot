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
    result = manager.set_node_value(
        session_name, r"\Data\Properties\Specifications\Input\GOPSETNAME", method
    )
    # Auto-load binary interaction params from databank
    # After setting the property method, Aspen creates parameter nodes but
    # doesn't automatically retrieve databank values (e.g. NRTL-1).
    # App-level Reconcile creates the nodes, then touching the Input node
    # via Reconcile triggers the databank retrieval (the call fails with
    # "not yet implemented" but has the necessary side effect).
    app = manager.get_app(session_name)
    if app is not None:
        try:
            app.Reconcile(1 | 1048576 | 2097152)
        except Exception:
            pass
        # Reconcile ALL binary interaction parameter sets, not just NRTL-1
        try:
            bi_node = app.Tree.FindNode(
                r"\Data\Properties\Parameters\Binary Interaction"
            )
            if bi_node is not None:
                for i in range(bi_node.Elements.Count):
                    try:
                        inp = bi_node.Elements.Item(i).Elements("Input")
                        if inp is not None:
                            inp.Reconcile(1)
                    except Exception:
                        pass
        except Exception:
            pass
    return result


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
