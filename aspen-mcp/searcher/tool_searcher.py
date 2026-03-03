"""LLM-facing search tool — keyword search across all YAML definitions."""

from __future__ import annotations

from .definition_searcher import DefinitionSearcher


def search_properties(searcher: DefinitionSearcher, query: str) -> str:
    """Search all YAML definitions for properties, ports, and other info matching *query*.

    Returns a formatted string listing every match.
    """
    results = searcher.search(query)
    if not results:
        return f"No results found matching '{query}'."

    lines: list[str] = []
    for r in results:
        if r["kind"] == "block":
            lines.append(
                f"[Block] {r['block_type']} — {r['property']} ({r['type']}): {r['description']}"
            )
        elif r["kind"] == "port":
            lines.append(
                f"[Port] {r['block_type']} — {r['port']}: {r['description']}"
            )
        else:
            lines.append(
                f"[Stream] {r['stream_type']} — {r['property']} ({r['type']}): {r['description']}"
            )
    return "\n".join(lines)
