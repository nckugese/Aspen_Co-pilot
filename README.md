# Aspen Plus MCP Integration

Control Aspen Plus simulations via the Model Context Protocol (MCP).

See [aspen-mcp/README.md](aspen-mcp/README.md) for full documentation on available tools and block/stream reference.

## Prerequisites

- Windows (Aspen Plus only runs on Windows)
- Aspen Plus installed
- Python 3.11+

## Setup

1. Install dependencies:

   ```bash
   pip install -r aspen-mcp/requirements.txt
   ```

2. Copy `.mcp.json.example` to `.mcp.json`:

   ```bash
   cp .mcp.json.example .mcp.json
   ```

3. Edit `.mcp.json` and update the path to `server.py`:

   ```json
   {
     "mcpServers": {
       "aspen-plus": {
         "command": "python",
         "args": ["path/to/aspen-mcp/server.py"]
       }
     }
   }
   ```

   If `python` is not in your system PATH, use the full path to your Python executable:

   ```json
   "command": "C:/Users/YourName/AppData/Local/Programs/Python/Python311/python.exe"
   ```

## Privacy & Data Collection

This project includes an optional, anonymous error-sharing feature to help the community resolve simulation issues faster.

- **What is collected**: Error keyword, block type, property method, generalized cause description, fix direction (not specific values), Aspen path pattern, and failed attempts (generalized). All data is abstracted to pattern-level knowledge before submission.
- **Opt-in only**: After resolving a simulation error, you might be asked "Share this fix to community? (y/n)".
- **Review process**: All submissions go through human review before being published. A maintainer reviews each entry and only approved records are made available to other users.
- **Local recording**: Error resolutions are always saved locally to `aspen-mcp/docs/error-history.md`. This file never leaves your machine unless you commit and push it yourself.

## License

This project is licensed under the MIT License.
