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
    """Run the simulation in a given session."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
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
                children.append(f"  {name} = {val}")
            except Exception:
                children.append(f"  {name}/")
        return f"Children of '{aspen_path}' ({els.Count}):\n" + "\n".join(children)
    except Exception as exc:
        return f"Error listing '{aspen_path}': {exc}"
