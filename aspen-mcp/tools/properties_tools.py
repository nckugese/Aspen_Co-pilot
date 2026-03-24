"""Implementations for properties category tools.

get/set_property_method use manager.get_node_value/set_node_value (low-level).
add_component calls manager.get_app() and does COM operations directly.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _reconcile_binary_interactions(app):
    """Trigger databank retrieval for all binary interaction parameter sets."""
    if app is None:
        return
    try:
        app.Reconcile(1 | 1048576 | 2097152)
    except Exception:
        logger.debug("App-level Reconcile failed (expected side-effect call)", exc_info=True)
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
                    logger.debug("Binary interaction reconcile failed for set %d", i)
    except Exception:
        logger.debug("Failed to reconcile binary interactions", exc_info=True)


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
    _reconcile_binary_interactions(app)
    return result


def _generate_short_id(component_id: str) -> str:
    """Generate a short (<=8 char) component ID from a long name."""
    # Remove common separators, take first 8 chars uppercase
    short = component_id.upper().replace(" ", "").replace("-", "").replace(",", "")
    if len(short) <= 8:
        return short
    # Try abbreviation: take first 8 alphanumeric chars
    return short[:8]


def add_component(manager, session_name: str, component_id: str) -> str:
    """Add a component to the simulation component list.

    Accepts any component name, synonym, CAS number, or short ID.
    If the name exceeds 8 characters, a short ID is auto-generated and the
    full name is written to ANAME so Aspen resolves it from the databank.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        needs_aname = len(component_id) > 8
        if needs_aname:
            label = _generate_short_id(component_id)
        else:
            label = component_id

        # Check for duplicate label and make unique if needed
        type_node = app.Tree.FindNode(r"\Data\Components\Specifications\Input\TYPE")
        existing = set()
        for i in range(type_node.Elements.Count):
            existing.add(type_node.Elements.Item(i).Name.upper())
        if label.upper() in existing:
            base = label[:6] if len(label) > 6 else label
            for suffix in range(1, 100):
                candidate = f"{base}{suffix}"
                if len(candidate) <= 8 and candidate.upper() not in existing:
                    label = candidate
                    break

        tlb = type_node.Elements
        tlb.InsertRow(0, 0)
        tlb.SetLabel(0, 0, False, label)

        if needs_aname:
            aname_node = app.Tree.FindNode(
                rf"\Data\Components\Specifications\Input\ANAME\{label}"
            )
            if aname_node is not None:
                aname_node.Value = component_id

        _reconcile_binary_interactions(app)

        # Read back what Aspen resolved
        resolved = ""
        try:
            aname = app.Tree.FindNode(
                rf"\Data\Components\Specifications\Input\ANAME\{label}"
            )
            dbname = app.Tree.FindNode(
                rf"\Data\Components\Specifications\Input\DBNAME\{label}"
            )
            if aname:
                resolved += f", alias={aname.Value}"
            if dbname:
                resolved += f", dbname={dbname.Value}"
        except Exception:
            logger.debug("Could not read back resolved names for component '%s'", label)

        if needs_aname:
            return f"Component '{label}' added (from '{component_id}'{resolved})."
        return f"Component '{label}' added{resolved}."
    except Exception as exc:
        logger.error("Failed to add component '%s': %s", component_id, exc, exc_info=True)
        return f"Failed to add component '{component_id}': {exc}"


def remove_component(manager, session_name: str, component_id: str) -> str:
    """Remove a component from the simulation component list by its label ID."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        type_node = app.Tree.FindNode(r"\Data\Components\Specifications\Input\TYPE")
        tlb = type_node.Elements
        # Find the component index by label (case-insensitive)
        target_idx = None
        for i in range(tlb.Count):
            if tlb.Item(i).Name.upper() == component_id.upper():
                target_idx = i
                break
        if target_idx is None:
            return f"Component '{component_id}' not found."
        tlb.RemoveRow(0, target_idx)
        _reconcile_binary_interactions(app)
        return f"Component '{component_id}' removed."
    except Exception as exc:
        logger.error("Failed to remove component '%s': %s", component_id, exc, exc_info=True)
        return f"Failed to remove component '{component_id}': {exc}"


# ------------------------------------------------------------------
# Side duty helpers (RadFrac HEATER_DUTY)
# ------------------------------------------------------------------


def add_side_duty(
    manager, session_name: str, block_name: str, stage: int, duty: float
) -> str:
    """Add or update a side duty (HEATER_DUTY) on a RadFrac stage.

    Uses manager.ensure_node to create the table row if it doesn't exist.

    Args:
        block_name: RadFrac block name (e.g. 'STRIP').
        stage:      Stage number (integer).
        duty:       Heat duty value in current unit (e.g. cal/sec).
    """
    path = rf"\Data\Blocks\{block_name}\Input\HEATER_DUTY\{stage}"
    try:
        node = manager.ensure_node(session_name, path)
        if node is None:
            return (
                f"Failed to create HEATER_DUTY node for block '{block_name}' "
                f"stage {stage}. Is it a RadFrac block?"
            )
        node.Value = duty
        return (
            f"Added HEATER_DUTY on block '{block_name}' "
            f"stage {stage} = {duty}."
        )
    except Exception as exc:
        logger.error("Failed to add side duty on '%s' stage %d: %s", block_name, stage, exc, exc_info=True)
        return f"Failed to add side duty on '{block_name}' stage {stage}: {exc}"


def remove_side_duty(
    manager, session_name: str, block_name: str, stage: int
) -> str:
    """Remove a side duty entry from a RadFrac stage.

    Args:
        block_name: RadFrac block name.
        stage:      Stage number to remove.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        duty_node = app.Tree.FindNode(
            rf"\Data\Blocks\{block_name}\Input\HEATER_DUTY"
        )
        if duty_node is None:
            return f"HEATER_DUTY node not found for block '{block_name}'."

        stage_str = str(stage)
        elems = duty_node.Elements
        target_idx = None
        for i in range(elems.Count):
            if elems.Item(i).Name == stage_str:
                target_idx = i
                break
        if target_idx is None:
            return f"No side duty on stage {stage} of block '{block_name}'."

        elems.RemoveRow(0, target_idx)
        return f"Removed side duty on block '{block_name}' stage {stage}."
    except Exception as exc:
        logger.error("Failed to remove side duty on '%s' stage %d: %s", block_name, stage, exc, exc_info=True)
        return f"Failed to remove side duty on '{block_name}' stage {stage}: {exc}"
