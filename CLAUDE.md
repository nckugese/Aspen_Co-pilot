# Aspen Plus MCP Project

This project provides an MCP server for controlling Aspen Plus via COM API.

## Documentation

Do NOT guess Aspen paths or parameters. Before using any Aspen MCP tool (place_block, set_value, add_reaction, optimize, etc.), delegate to the `aspen-doc` agent to look up the relevant documentation. Do NOT read doc files directly in the main conversation — let the subagent read and summarize only what you need.

- [aspen-mcp/docs/aspen.md](aspen-mcp/docs/aspen.md) — Main index for all Aspen Plus operations (used by aspen-doc agent)

## Error Troubleshooting

When `run_simulation` returns errors or warnings, invoke the `aspen-error-troubleshooting` skill for the diagnosis → fix → record → share workflow.

## Key Files

- `aspen-mcp/server.py` — MCP server entry point (all tool registrations)
- `aspen-mcp/aspen_manager.py` — COM connection manager and low-level operations
- `aspen-mcp/tools/` — Tool implementations
