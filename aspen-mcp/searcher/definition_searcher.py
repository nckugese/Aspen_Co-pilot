"""Core lookup engine — loads SGXML + YAML definitions and resolves Aspen COM paths."""

from __future__ import annotations

import difflib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .sgxml_loader import load_all_sgxml

logger = logging.getLogger(__name__)


@dataclass
class ResolveResult:
    """Result of a fuzzy name resolution."""

    matched: bool
    value: str | None = None
    original: str = ""
    resolved_as: str | None = None
    candidates: list[str] = field(default_factory=list)
    message: str = ""


def _definitions_dir() -> Path:
    """Return the absolute path to the definitions/ directory."""
    return Path(__file__).resolve().parent.parent / "definitions"


class DefinitionSearcher:
    """In-memory index of all block/stream YAML definitions."""

    def __init__(self, sgxml_dir: str | None = None) -> None:
        # block_type (lower) -> {property_name -> {aspen_path, type, description}}
        self._blocks: dict[str, dict[str, dict[str, Any]]] = {}
        # stream_type (lower) -> {property_name -> {aspen_path, type, description}}
        self._streams: dict[str, dict[str, Any]] = {}
        # raw metadata per block/stream type
        self._block_meta: dict[str, dict[str, Any]] = {}
        self._stream_meta: dict[str, dict[str, Any]] = {}
        self._sgxml_dir = sgxml_dir
        self.load_all()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_all(self) -> None:
        """Load all definitions: SGXML first (blocks), then YAML overlays."""
        self._blocks.clear()
        self._streams.clear()
        self._block_meta.clear()
        self._stream_meta.clear()

        self._load_sgxml()  # Phase 1: SGXML (blocks only, ~53 types)
        self._load_yaml()   # Phase 2: YAML overlays (blocks + streams)

    def _load_sgxml(self) -> None:
        """Load block definitions from SGXML files, then merge discovered ports."""
        sgxml_blocks = load_all_sgxml(self._sgxml_dir)

        for key, parsed in sgxml_blocks.items():
            block_type_display = parsed["block_type"]
            properties = parsed["properties"]

            # Strip read_only from property dicts for the _blocks store
            prop_map: dict[str, dict[str, Any]] = {}
            for prop_name, info in properties.items():
                prop_map[prop_name] = {
                    "aspen_path": info["aspen_path"],
                    "type": info["type"],
                    "description": info["description"],
                }

            self._blocks[key] = prop_map
            self._block_meta[key] = {
                "block_type": block_type_display,
                "description": "",
                "ports": [],
            }

        # Merge discovered ports from block_ports.json (if it exists)
        self._load_discovered_ports()

    def _load_discovered_ports(self) -> None:
        """Load auto-discovered port names from block_ports.json."""
        ports_json = Path(__file__).resolve().parent / "block_ports.json"
        if not ports_json.is_file():
            return

        try:
            data = json.loads(ports_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load block_ports.json: %s", exc)
            return

        for block_type, port_names in data.items():
            key = block_type.lower()
            meta = self._block_meta.get(key)
            if meta is None:
                # Block type from ports JSON but not in SGXML — create entry
                meta = {"block_type": block_type, "description": "", "ports": []}
                self._block_meta[key] = meta
                self._blocks.setdefault(key, {})

            # Only set ports if not already populated (YAML will override later)
            if not meta["ports"]:
                meta["ports"] = [{"name": p} for p in port_names]

        logger.info("Loaded discovered ports for %d block types from %s", len(data), ports_json)

    def _load_yaml(self) -> None:
        """Load YAML definitions, merging into existing SGXML data for blocks."""
        defs = _definitions_dir()
        for yaml_path in sorted(defs.rglob("*.yaml")):
            if yaml_path.name.startswith("_"):
                continue
            try:
                data = self._read_yaml(yaml_path)
            except Exception:
                continue

            block_type = data.get("block_type")
            stream_type = data.get("stream_type")
            props = [p for p in data.get("properties", []) if p is not None]

            if block_type:
                key = block_type.lower()

                # Merge metadata: YAML description/ports override empty SGXML values
                existing_meta = self._block_meta.get(key, {
                    "block_type": block_type,
                    "description": "",
                    "ports": [],
                })
                yaml_desc = data.get("description", "")
                yaml_ports = data.get("ports", [])
                if yaml_desc:
                    existing_meta["description"] = yaml_desc
                if yaml_ports:
                    existing_meta["ports"] = yaml_ports
                # Always prefer YAML's block_type casing
                existing_meta["block_type"] = block_type
                self._block_meta[key] = existing_meta

                # Merge properties: YAML wins on name conflict
                existing_props = self._blocks.get(key, {})
                for p in props:
                    existing_props[p["name"]] = {
                        "aspen_path": p["aspen_path"],
                        "type": p.get("type", "string"),
                        "description": p.get("description", ""),
                    }
                self._blocks[key] = existing_props

            elif stream_type:
                key = stream_type.lower()
                self._stream_meta[key] = {
                    "stream_type": stream_type,
                    "description": data.get("description", ""),
                }
                prop_map: dict[str, dict[str, Any]] = {}
                for p in props:
                    prop_map[p["name"]] = {
                        "aspen_path": p["aspen_path"],
                        "type": p.get("type", "string"),
                        "description": p.get("description", ""),
                    }
                self._streams[key] = prop_map

    def reload(self) -> None:
        """Re-scan YAML files (call after create_tool writes a new definition)."""
        self.load_all()

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(self, block_type: str, property_name: str) -> str | None:
        """Return the aspen_path template for a block property, or None."""
        props = self._blocks.get(block_type.lower())
        if props is None:
            return None
        prop = props.get(property_name)
        return prop["aspen_path"] if prop else None

    def lookup_stream(self, stream_type: str, property_name: str) -> str | None:
        """Return the aspen_path template for a stream property, or None."""
        props = self._streams.get(stream_type.lower())
        if props is None:
            return None
        prop = props.get(property_name)
        return prop["aspen_path"] if prop else None

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_block_properties(self, block_type: str) -> list[dict[str, str]]:
        """List all properties for a block type."""
        props = self._blocks.get(block_type.lower(), {})
        return [
            {"name": name, "type": info["type"], "description": info["description"]}
            for name, info in props.items()
        ]

    def list_stream_properties(self, stream_type: str) -> list[dict[str, str]]:
        """List all properties for a stream type."""
        props = self._streams.get(stream_type.lower(), {})
        return [
            {"name": name, "type": info["type"], "description": info["description"]}
            for name, info in props.items()
        ]

    def list_block_types(self) -> list[str]:
        """Return all known block type names (original casing)."""
        return [m["block_type"] for m in self._block_meta.values()]

    def list_stream_types(self) -> list[str]:
        """Return all known stream type names (original casing)."""
        return [m["stream_type"] for m in self._stream_meta.values()]

    # ------------------------------------------------------------------
    # Full search (used by tool_searcher)
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[dict[str, Any]]:
        """Keyword search across all definitions (properties and ports).

        Uses OR matching — results are ranked by number of matching tokens
        so that the most relevant entries appear first.
        """
        tokens = query.lower().split()
        scored: list[tuple[int, dict[str, Any]]] = []

        for key, props in self._blocks.items():
            meta = self._block_meta[key]
            # Search properties
            for prop_name, info in props.items():
                text = f"{meta['block_type']} {meta['description']} {prop_name} {info['description']}".lower()
                hits = sum(1 for t in tokens if t in text)
                if hits > 0:
                    scored.append((hits, {
                        "kind": "block",
                        "block_type": meta["block_type"],
                        "property": prop_name,
                        "type": info["type"],
                        "description": info["description"],
                    }))
            # Search ports
            for port in meta.get("ports", []):
                text = f"{meta['block_type']} {meta['description']} {port['name']} {port.get('description', '')}".lower()
                hits = sum(1 for t in tokens if t in text)
                if hits > 0:
                    scored.append((hits, {
                        "kind": "port",
                        "block_type": meta["block_type"],
                        "port": port["name"],
                        "description": port.get("description", ""),
                    }))

        for key, props in self._streams.items():
            meta = self._stream_meta[key]
            for prop_name, info in props.items():
                text = f"{meta['stream_type']} {meta['description']} {prop_name} {info['description']}".lower()
                hits = sum(1 for t in tokens if t in text)
                if hits > 0:
                    scored.append((hits, {
                        "kind": "stream",
                        "stream_type": meta["stream_type"],
                        "property": prop_name,
                        "type": info["type"],
                        "description": info["description"],
                    }))

        # Sort by number of matching tokens (descending)
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored]

    # ------------------------------------------------------------------
    # Fuzzy matching
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(s: str) -> str:
        """Remove ``_ - ( ) `` and whitespace, then lowercase."""
        return re.sub(r"[_\-()\s]", "", s.lower())

    @staticmethod
    def _fuzzy_match(
        query: str,
        candidates: list[str],
        descriptions: dict[str, str] | None = None,
        cutoff: float = 0.6,
    ) -> str | None:
        """Try to match *query* against *candidates* using multiple strategies.

        Returns the matched candidate name, or ``None`` if no unique match.
        """
        if not candidates:
            return None

        # 1. Exact match
        if query in candidates:
            return query

        q_lower = query.lower()

        # 2. Case-insensitive
        hits = [c for c in candidates if c.lower() == q_lower]
        if len(hits) == 1:
            return hits[0]

        # 3. Normalized (strip _ - ( ) and spaces)
        q_norm = DefinitionSearcher._normalize(query)
        hits = [c for c in candidates if DefinitionSearcher._normalize(c) == q_norm]
        if len(hits) == 1:
            return hits[0]

        # 4. Substring (query is a substring of candidate)
        hits = [c for c in candidates if q_lower in c.lower()]
        if len(hits) == 1:
            return hits[0]

        # 5. Keyword match via descriptions
        if descriptions:
            q_tokens = q_lower.split()
            if q_tokens:
                hits = []
                for c in candidates:
                    desc = descriptions.get(c, "")
                    text = f"{c} {desc}".lower()
                    if all(t in text for t in q_tokens):
                        hits.append(c)
                if len(hits) == 1:
                    return hits[0]

        # 6. difflib fuzzy match
        close = difflib.get_close_matches(query, candidates, n=1, cutoff=cutoff)
        if close:
            return close[0]

        # Also try normalized fuzzy matching
        norm_to_orig: dict[str, str] = {}
        for c in candidates:
            norm_to_orig[DefinitionSearcher._normalize(c)] = c
        close = difflib.get_close_matches(
            q_norm, list(norm_to_orig.keys()), n=1, cutoff=cutoff
        )
        if close:
            return norm_to_orig[close[0]]

        return None

    # ------------------------------------------------------------------
    # Resolve methods (public API for fuzzy lookup)
    # ------------------------------------------------------------------

    def resolve_block_type(self, query: str) -> ResolveResult:
        """Fuzzy-match a block type name."""
        candidates = self.list_block_types()
        match = self._fuzzy_match(query, candidates)
        if match:
            return ResolveResult(
                matched=True, value=match, original=query,
                resolved_as=match if match != query else None,
                candidates=candidates,
                message=f"Resolved block type '{query}' -> '{match}'" if match != query else "",
            )
        return ResolveResult(
            matched=False, value=None, original=query,
            candidates=candidates,
            message=f"Unknown block type '{query}'. Known types: {', '.join(candidates)}",
        )

    def resolve_stream_type(self, query: str) -> ResolveResult:
        """Fuzzy-match a stream type name."""
        candidates = self.list_stream_types()
        match = self._fuzzy_match(query, candidates)
        if match:
            return ResolveResult(
                matched=True, value=match, original=query,
                resolved_as=match if match != query else None,
                candidates=candidates,
                message=f"Resolved stream type '{query}' -> '{match}'" if match != query else "",
            )
        return ResolveResult(
            matched=False, value=None, original=query,
            candidates=candidates,
            message=f"Unknown stream type '{query}'. Known types: {', '.join(candidates)}",
        )

    def resolve_block_property(self, block_type: str, property_name: str) -> ResolveResult:
        """Fuzzy-match a property name within a block type."""
        props = self._blocks.get(block_type.lower(), {})
        candidates = list(props.keys())
        descriptions = {name: info["description"] for name, info in props.items()}
        match = self._fuzzy_match(property_name, candidates, descriptions)
        if match:
            return ResolveResult(
                matched=True, value=match, original=property_name,
                resolved_as=match if match != property_name else None,
                candidates=candidates,
                message=f"Resolved property '{property_name}' -> '{match}'" if match != property_name else "",
            )
        return ResolveResult(
            matched=False, value=None, original=property_name,
            candidates=candidates,
            message=f"Unknown property '{property_name}' for {block_type}. Available: {', '.join(candidates)}",
        )

    def resolve_stream_property(self, stream_type: str, property_name: str) -> ResolveResult:
        """Fuzzy-match a property name within a stream type."""
        props = self._streams.get(stream_type.lower(), {})
        candidates = list(props.keys())
        descriptions = {name: info["description"] for name, info in props.items()}
        match = self._fuzzy_match(property_name, candidates, descriptions)
        if match:
            return ResolveResult(
                matched=True, value=match, original=property_name,
                resolved_as=match if match != property_name else None,
                candidates=candidates,
                message=f"Resolved property '{property_name}' -> '{match}'" if match != property_name else "",
            )
        return ResolveResult(
            matched=False, value=None, original=property_name,
            candidates=candidates,
            message=f"Unknown property '{property_name}' for {stream_type}. Available: {', '.join(candidates)}",
        )

    def resolve_port(self, block_type: str, port_query: str) -> ResolveResult:
        """Fuzzy-match a port name for a block type."""
        meta = self._block_meta.get(block_type.lower(), {})
        ports = meta.get("ports", [])
        candidates = [p["name"] for p in ports]
        descriptions = {p["name"]: p.get("description", "") for p in ports}

        if not candidates:
            return ResolveResult(
                matched=False, value=None, original=port_query,
                candidates=[],
                message=f"No port definitions found for block type '{block_type}'.",
            )

        match = self._fuzzy_match(port_query, candidates, descriptions)
        if match:
            return ResolveResult(
                matched=True, value=match, original=port_query,
                resolved_as=match if match != port_query else None,
                candidates=candidates,
                message=f"Resolved port '{port_query}' -> '{match}'" if match != port_query else "",
            )
        return ResolveResult(
            matched=False, value=None, original=port_query,
            candidates=candidates,
            message=f"Unknown port '{port_query}' for {block_type}. Available: {', '.join(candidates)}",
        )

    def resolve_lookup(self, block_type: str, property_name: str) -> ResolveResult:
        """Resolve *block_type* + *property_name* into an ``aspen_path``.

        Combines :meth:`resolve_block_type` and :meth:`resolve_block_property`.
        """
        bt = self.resolve_block_type(block_type)
        if not bt.matched:
            return ResolveResult(
                matched=False, value=None,
                original=f"{block_type}.{property_name}",
                candidates=bt.candidates, message=bt.message,
            )
        resolved_bt = bt.value

        prop = self.resolve_block_property(resolved_bt, property_name)
        if not prop.matched:
            return ResolveResult(
                matched=False, value=None,
                original=f"{block_type}.{property_name}",
                resolved_as=resolved_bt,
                candidates=prop.candidates, message=prop.message,
            )
        resolved_prop = prop.value

        aspen_path = self.lookup(resolved_bt, resolved_prop)
        parts = []
        if bt.resolved_as:
            parts.append(bt.message)
        if prop.resolved_as:
            parts.append(prop.message)

        return ResolveResult(
            matched=True, value=aspen_path,
            original=f"{block_type}.{property_name}",
            resolved_as=f"{resolved_bt}.{resolved_prop}",
            candidates=[], message="; ".join(parts) if parts else "",
        )

    def resolve_lookup_stream(self, stream_type: str, property_name: str) -> ResolveResult:
        """Resolve *stream_type* + *property_name* into an ``aspen_path``.

        Combines :meth:`resolve_stream_type` and :meth:`resolve_stream_property`.
        """
        st = self.resolve_stream_type(stream_type)
        if not st.matched:
            return ResolveResult(
                matched=False, value=None,
                original=f"{stream_type}.{property_name}",
                candidates=st.candidates, message=st.message,
            )
        resolved_st = st.value

        prop = self.resolve_stream_property(resolved_st, property_name)
        if not prop.matched:
            return ResolveResult(
                matched=False, value=None,
                original=f"{stream_type}.{property_name}",
                resolved_as=resolved_st,
                candidates=prop.candidates, message=prop.message,
            )
        resolved_prop = prop.value

        aspen_path = self.lookup_stream(resolved_st, resolved_prop)
        parts = []
        if st.resolved_as:
            parts.append(st.message)
        if prop.resolved_as:
            parts.append(prop.message)

        return ResolveResult(
            matched=True, value=aspen_path,
            original=f"{stream_type}.{property_name}",
            resolved_as=f"{resolved_st}.{resolved_prop}",
            candidates=[], message="; ".join(parts) if parts else "",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
