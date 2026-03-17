# Aspen Plus MCP Project

This project provides an MCP server for controlling Aspen Plus via COM API.

## Documentation

When you need to look up how to operate Aspen Plus blocks, streams, reactions, or other features, start from the documentation index:

- [aspen-mcp/docs/aspen.md](aspen-mcp/docs/aspen.md) — Main index for all Aspen Plus operations

Do NOT guess Aspen paths or parameters. Always read the relevant doc file first.

## Key Files

- `aspen-mcp/server.py` — MCP server entry point (all tool registrations)
- `aspen-mcp/aspen_manager.py` — COM connection manager and low-level operations
- `aspen-mcp/tools/` — Tool implementations
- `aspen-mcp/knowledge/knowledge_base.md` — General tips and gotchas (loaded as MCP resource)
- `aspen-mcp/definitions/` — Block/stream YAML definitions for property lookup
