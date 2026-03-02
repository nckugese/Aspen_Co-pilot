# Aspen Plus MCP Integration

This project integrates Aspen Plus with a custom MCP (Model Control Program) server, allowing users to open, manage, and close Aspen Plus sessions through Python and MCP. The server facilitates interaction with Aspen Plus simulations via tools defined in `FastMCP`.

## Project Overview

The main components of this project are:

- **AspenPlusManager**: Manages the opening, listing, and closing of Aspen Plus sessions through COM automation.
- **MCP Server**: A server utilizing `FastMCP` that provides tools to interact with Aspen Plus using commands like opening sessions, listing active sessions, and closing them.

The MCP server is designed to work with a simulated control system, enabling automation and management of Aspen Plus simulations via simple commands.

## Requirements

- Python 3.6 or higher
- `pywin32` (for interacting with Aspen Plus COM API)
- `fastmcp` (for MCP server functionality)

### Install Dependencies

First, ensure you have Python installed. Then, install the required Python packages:

```bash
pip install pywin32 fastmcp
```

## Usage

1. **Starting the MCP Server**: The MCP server listens for commands and exposes tools that can be invoked.

   * To start the MCP server, run `main.py`:

   ```bash
   python main.py
   ```

   This will start the server and allow you to use the tools defined in the code.

2. **Tools Provided**:

   * **open_aspen_plus(file_path)**: Opens an Aspen Plus session with the given `.bkp` file.
   * **close_aspen_plus(session_name=None)**: Closes a specific Aspen Plus session, or all sessions if no session name is provided.
   * **list_aspen_sessions()**: Lists all currently open Aspen Plus sessions.

### Example

Here’s how you can use the tools after starting the MCP server:

```python
# Start the MCP server
mcp.run()

# Example of how to use the tools
file_path = "C:\\path\\to\\simulation.bkp"

# Open a simulation
open_aspen_plus(file_path)

# List active Aspen Plus sessions
list_aspen_sessions()

# Close a specific session
close_aspen_plus("Simulation 1")

# Or close all sessions
close_aspen_plus()
```

### File Structure

* `aspen_manager.py`: Contains the `AspenPlusManager` class which handles interaction with Aspen Plus via COM automation.
* `main.py`: Defines the MCP server and exposes tools to interact with Aspen Plus through `FastMCP`.

## How It Works

* The `AspenPlusManager` class interacts with Aspen Plus through its COM API, allowing us to open, manage, and close Aspen Plus sessions.
* The `FastMCP` server listens for incoming commands and invokes the corresponding tools.
* The MCP server is initialized in `main.py` where three tools are defined:

  * `open_aspen_plus`: Opens a new Aspen Plus session with a given `.bkp` file.
  * `close_aspen_plus`: Closes a specific session or all sessions.
  * `list_aspen_sessions`: Lists all currently active Aspen Plus sessions.

## Contributing

If you would like to contribute to this project, please fork the repository, make your changes, and submit a pull request. Contributions are welcome to improve the functionality and add new features.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```

### 說明：

1. **專案概覽**：
   - 這部分簡要介紹了專案的功能，如何通過 Python 和 MCP 伺服器來控制 Aspen Plus 模擬。
   
2. **安裝要求**：
   - 列出了所需的 Python 版本和必要的庫 `pywin32` 和 `fastmcp`，並提供了安裝指令。

3. **使用說明**：
   - 這裡詳細說明了如何啟動 MCP 伺服器以及如何使用所提供的工具來與 Aspen Plus 進行互動。

4. **範例**：
   - 提供了如何啟動伺服器並使用工具的範例代碼。

5. **檔案結構**：
   - 解釋了兩個檔案的內容以及它們的作用。

6. **如何運作**：
   - 描述了 `AspenPlusManager` 類別如何與 Aspen Plus 進行交互，以及 `FastMCP` 伺服器如何處理命令。

7. **貢獻**：
   - 。

8. **授權條款**：
   -。


```
