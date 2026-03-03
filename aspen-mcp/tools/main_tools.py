"""Implementations for main category tools (open, close, list, run, save)."""

from __future__ import annotations


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
    return manager.reinit(session_name)


def run_simulation(manager, session_name: str) -> str:
    """Run the simulation in a given session."""
    return manager.run(session_name)


def save_simulation(manager, session_name: str, file_path: str = None) -> str:
    """Save the current simulation to disk."""
    return manager.save(session_name, file_path)
