"""Stream get/set — resolves property paths via the searcher."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aspen_manager import AspenPlusManager
    from searcher.definition_searcher import DefinitionSearcher


def get_stream_value(
    manager: AspenPlusManager,
    searcher: DefinitionSearcher,
    session_name: str,
    stream_name: str,
    stream_type: str,
    property_name: str,
    extra_params: dict | None = None,
) -> str:
    """Read a property from an Aspen stream.

    Uses the searcher to resolve *stream_type* + *property_name* into a COM path.
    """
    result = searcher.resolve_lookup_stream(stream_type, property_name)
    if not result.matched:
        return result.message

    hint = f"[Note: {result.message}]\n" if result.message else ""
    aspen_path = result.value.format(stream_name=stream_name, **(extra_params or {}))
    return hint + str(manager.get_node_value(session_name, aspen_path))


def set_stream_value(
    manager: AspenPlusManager,
    searcher: DefinitionSearcher,
    session_name: str,
    stream_name: str,
    stream_type: str,
    property_name: str,
    value,
    extra_params: dict | None = None,
    unit: str = None,
) -> str:
    """Write a property on an Aspen stream.

    Uses the searcher to resolve *stream_type* + *property_name* into a COM path.
    """
    result = searcher.resolve_lookup_stream(stream_type, property_name)
    if not result.matched:
        return result.message

    hint = f"[Note: {result.message}]\n" if result.message else ""
    aspen_path = result.value.format(stream_name=stream_name, **(extra_params or {}))
    return hint + str(manager.set_node_value(session_name, aspen_path, value, unit=unit))
