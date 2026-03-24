"""Unified get/set value — resolves paths via searcher or direct aspen_path."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aspen_manager import AspenPlusManager
    from searcher.definition_searcher import DefinitionSearcher


def _resolve_path(
    searcher: DefinitionSearcher,
    aspen_path: str | None,
    block_name: str | None,
    block_type: str | None,
    stream_name: str | None,
    stream_type: str | None,
    property_name: str | None,
    extra_params: dict | None,
) -> tuple[str | None, str]:
    """Resolve to an aspen_path from direct path or searcher lookup.

    Returns (path, hint_message).  path is None on failure.
    """
    if aspen_path:
        return aspen_path, ""

    if block_name and block_type and property_name:
        result = searcher.resolve_lookup(block_type, property_name)
        if not result.matched:
            return None, result.message
        path = result.value.format(block_name=block_name, **(extra_params or {}))
        return path, result.message

    if stream_name and stream_type and property_name:
        result = searcher.resolve_lookup_stream(stream_type, property_name)
        if not result.matched:
            return None, result.message
        path = result.value.format(stream_name=stream_name, **(extra_params or {}))
        return path, result.message

    return None, (
        "Provide either aspen_path, "
        "or (block_name + block_type + property_name), "
        "or (stream_name + stream_type + property_name)."
    )


def get_value(
    manager: AspenPlusManager,
    searcher: DefinitionSearcher,
    session_name: str,
    aspen_path: str | None = None,
    block_name: str | None = None,
    block_type: str | None = None,
    stream_name: str | None = None,
    stream_type: str | None = None,
    property_name: str | None = None,
    extra_params: dict | None = None,
) -> str:
    """Read a value — resolves path automatically."""
    path, hint = _resolve_path(
        searcher, aspen_path,
        block_name, block_type, stream_name, stream_type,
        property_name, extra_params,
    )
    if path is None:
        return hint

    result = manager.get_node_value(session_name, path)
    return f"[Note: {hint}]\n{result}" if hint else result


def set_value(
    manager: AspenPlusManager,
    searcher: DefinitionSearcher,
    session_name: str,
    value=None,
    unit: str | None = None,
    basis: str | None = None,
    aspen_path: str | None = None,
    block_name: str | None = None,
    block_type: str | None = None,
    stream_name: str | None = None,
    stream_type: str | None = None,
    property_name: str | None = None,
    extra_params: dict | None = None,
) -> str:
    """Write a value — resolves path automatically, uses SetValueUnitAndBasis."""
    path, hint = _resolve_path(
        searcher, aspen_path,
        block_name, block_type, stream_name, stream_type,
        property_name, extra_params,
    )
    if path is None:
        return hint

    result = manager.set_node_value(session_name, path, value=value, unit=unit, basis=basis)
    return f"[Note: {hint}]\n{result}" if hint else result


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
