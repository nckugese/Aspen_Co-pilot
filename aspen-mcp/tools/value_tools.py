"""Unified get/set value — direct aspen_path only."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aspen_manager import AspenPlusManager


def get_value(
    manager: AspenPlusManager,
    session_name: str,
    aspen_path: str,
) -> str:
    """Read a value by direct Aspen path."""
    return manager.get_node_value(session_name, aspen_path)


def set_value(
    manager: AspenPlusManager,
    session_name: str,
    aspen_path: str,
    value=None,
    unit: str | None = None,
    basis: str | None = None,
) -> str:
    """Write a value by direct Aspen path."""
    return manager.set_node_value(session_name, aspen_path, value=value, unit=unit, basis=basis)


def batch_set_values(
    manager: AspenPlusManager,
    session_name: str,
    items: list[dict],
) -> str:
    """Set multiple values in one call.

    Args:
        items: [{"path": "\\Data\\...", "value": "100", "unit": "C"}, ...]
               Each item needs "path" and at least one of "value", "unit", "basis".
    """
    results = []
    for item in items:
        path = item.get("path")
        if not path:
            results.append("Error: missing 'path'")
            continue
        r = manager.set_node_value(
            session_name, path,
            value=item.get("value"),
            unit=item.get("unit"),
            basis=item.get("basis"),
        )
        results.append(r)
    return "\n".join(results)
