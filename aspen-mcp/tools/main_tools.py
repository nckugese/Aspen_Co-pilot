"""Implementations for main category tools (open, close, list, run, save, etc.).

reinit / run / save / list_node_children contain COM logic directly.
"""

from __future__ import annotations

import os


def open_aspen_plus(manager, file_path: str) -> str:
    """Open Aspen Plus and load a .bkp simulation file."""
    return manager.open_with_file(file_path)


def close_aspen_plus(manager, session_name: str = None) -> str:
    """Close an Aspen Plus session."""
    return manager.close(session_name)


def list_aspen_sessions(manager) -> str:
    """List all active Aspen Plus sessions."""
    return manager.list_sessions()


def reinit_simulation(manager, session_name: str) -> str:
    """Reinitialize the simulation in a given session."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        app.Reinit()
        return f"Simulation '{session_name}' reinitialized."
    except Exception as exc:
        return f"Failed to reinitialize simulation '{session_name}'. Error: {exc}"


def run_simulation(manager, session_name: str) -> str:
    """Run the simulation in a given session.

    Checks that all required inputs are complete before running,
    matching the behavior of the Aspen Plus UI Run button.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        # Check input completeness via COMPSTATUS attribute on the root Data node
        # HAP_COMPSTATUS = 12, HAP_INPUT_INCOMPLETE = 64, HAP_INPUT_COMPLETE = 128
        root = app.Tree.FindNode(r"\Data")
        if root is not None:
            try:
                status = root.AttributeValue(12)  # HAP_COMPSTATUS
                if isinstance(status, int):
                    if status & 64:  # HAP_INPUT_INCOMPLETE
                        return (
                            f"Cannot run simulation '{session_name}': "
                            "required inputs are incomplete. "
                            "Use check_inputs to see what is missing."
                        )
            except Exception:
                pass  # If status check fails, fall through to try running

        app.Run2()
        return f"Simulation '{session_name}' run completed."
    except Exception as exc:
        return f"Failed to run simulation '{session_name}'. Error: {exc}"


def save_simulation(manager, session_name: str, file_path: str = None) -> str:
    """Save the current simulation to disk."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        if file_path:
            app.SaveAs(os.path.abspath(file_path))
            return f"Session '{session_name}' saved to {file_path}."
        else:
            app.Save()
            return f"Session '{session_name}' saved."
    except Exception as exc:
        return f"Failed to save session '{session_name}'. Error: {exc}"


def check_inputs(manager, session_name: str) -> str:
    """Check if all required inputs are complete before running.

    Uses NextIncomplete(64) to walk the tree and find all incomplete input nodes.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        incomplete = []
        node = app.Tree.FindNode(r"\Data")
        seen = set()
        for _ in range(200):  # safety limit
            result = node.NextIncomplete(64)  # HAP_INPUT_INCOMPLETE
            # COM returns (path_or_node, code) tuple
            if isinstance(result, tuple):
                item = result[0]
            else:
                item = result
            if item is None:
                break
            # item may be a path string or a COM node
            if isinstance(item, str):
                path = item
                if path in seen:
                    break
                seen.add(path)
                incomplete.append(f"  - {path}")
                # navigate to this node for next iteration
                next_node = app.Tree.FindNode(path)
                if next_node is None:
                    break
                node = next_node
            else:
                # COM node object
                name = item.Name
                if name in seen:
                    break
                seen.add(name)
                try:
                    prompt = item.AttributeValue(19)  # HAP_PROMPT
                except Exception:
                    prompt = ""
                if prompt:
                    incomplete.append(f"  - {name}: {prompt}")
                else:
                    incomplete.append(f"  - {name}")
                node = item

        if not incomplete:
            return "All required inputs are complete. Ready to run."
        return f"Incomplete inputs ({len(incomplete)}):\n" + "\n".join(incomplete)
    except Exception as exc:
        return f"Error checking inputs: {exc}"


def get_node_value(manager, session_name: str, aspen_path: str) -> str:
    """Read a raw value from the Aspen Plus data tree."""
    return manager.get_node_value(session_name, aspen_path)


def set_node_value(manager, session_name: str, aspen_path: str, value, unit: str = None) -> str:
    """Write a raw value to the Aspen Plus data tree."""
    return manager.set_node_value(session_name, aspen_path, value, unit=unit)


def get_node_unit_info(manager, session_name: str, aspen_path: str) -> str:
    """Return unit information for a node."""
    return manager.get_node_unit_info(session_name, aspen_path)


def list_node_children(manager, session_name: str, aspen_path: str) -> str:
    """List all child elements of a node in the Aspen Plus data tree."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        node = app.Tree.FindNode(aspen_path)
        if node is None:
            return f"Node not found: {aspen_path}"
        els = node.Elements
        if els.Count == 0:
            return f"'{aspen_path}' has no children."
        children = []
        for i in range(els.Count):
            child = els.Item(i)
            name = child.Name
            try:
                val = child.Value
                if val is None:
                    try:
                        sub = child.Elements
                        if sub is not None and sub.Count > 0:
                            children.append(f"  {name} = [table, {sub.Count} entries]")
                        else:
                            children.append(f"  {name} = None")
                    except Exception:
                        children.append(f"  {name} = None")
                else:
                    children.append(f"  {name} = {val}")
            except Exception:
                children.append(f"  {name}/")
        return f"Children of '{aspen_path}' ({els.Count}):\n" + "\n".join(children)
    except Exception as exc:
        return f"Error listing '{aspen_path}': {exc}"
