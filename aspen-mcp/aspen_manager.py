import os
import time
import win32com.client
import pythoncom


class AspenPlusManager:
    """Manages multiple Aspen Plus COM connections."""

    def __init__(self):
        self._sessions: dict[str, object] = {}

    def _session_name(self, file_path: str) -> str:
        """Extract session name from file path (filename without extension)."""
        return os.path.splitext(os.path.basename(file_path))[0]

    def _is_alive(self, name: str) -> bool:
        """Check whether a session's COM object is still alive."""
        app = self._sessions.get(name)
        if app is None:
            return False
        try:
            app.Visible  # noqa: B018
            return True
        except Exception:
            del self._sessions[name]
            return False

    def list_sessions(self) -> str:
        """List all active sessions."""
        alive = [name for name in list(self._sessions) if self._is_alive(name)]
        if not alive:
            return "No active Aspen Plus sessions."
        return "Active sessions:\n" + "\n".join(f"  - {name}" for name in alive)

    def open_with_file(self, file_path: str) -> str:
        """Open Aspen Plus and load a .bkp file."""
        file_path = os.path.abspath(file_path)
        name = self._session_name(file_path)

        if self._is_alive(name):
            return f"Session '{name}' is already open."

        if not os.path.exists(file_path):
            return f"Failed: cannot find file: {file_path}"

        pythoncom.CoInitialize()

        try:
            aspen = win32com.client.Dispatch("Apwn.Document")
            aspen.InitFromFile2(file_path)
            aspen.Visible = True
            self._sessions[name] = aspen
            return f"Aspen Plus opened successfully. Session: '{name}'"
        except Exception as exc:
            return f"Failed to launch Aspen Plus. Error: {exc}"

    def close(self, session_name: str = None) -> str:
        """Close an Aspen Plus session by name, or close all if no name given."""
        if session_name:
            if not self._is_alive(session_name):
                return f"No active session named '{session_name}'."
            try:
                self._sessions[session_name].Close()
                del self._sessions[session_name]
                return f"Session '{session_name}' closed successfully."
            except Exception as exc:
                self._sessions.pop(session_name, None)
                return f"Failed to close session '{session_name}'. Error: {exc}"

        # Close all sessions
        if not self._sessions:
            return "No active Aspen Plus sessions to close."

        results = []
        for name in list(self._sessions):
            try:
                self._sessions[name].Close()
                del self._sessions[name]
                results.append(f"Session '{name}' closed successfully.")
            except Exception as exc:
                self._sessions.pop(name, None)
                results.append(f"Failed to close session '{name}'. Error: {exc}")
        return "\n".join(results)

    # ------------------------------------------------------------------
    # Simulation control
    # ------------------------------------------------------------------

    def reinit(self, session_name: str) -> str:
        """Reinitialize the simulation."""
        if not self._is_alive(session_name):
            return f"No active session named '{session_name}'."
        try:
            app = self._sessions[session_name]
            app.Reinit()
            return f"Simulation '{session_name}' reinitialized."
        except Exception as exc:
            return f"Failed to reinitialize simulation '{session_name}'. Error: {exc}"

    def run(self, session_name: str) -> str:
        """Run the simulation."""
        if not self._is_alive(session_name):
            return f"No active session named '{session_name}'."
        try:
            app = self._sessions[session_name]
            app.Run2()
            return f"Simulation '{session_name}' run completed."
        except Exception as exc:
            return f"Failed to run simulation '{session_name}'. Error: {exc}"

    def save(self, session_name: str, file_path: str = None) -> str:
        """Save the simulation. Optionally specify a new file path."""
        if not self._is_alive(session_name):
            return f"No active session named '{session_name}'."
        try:
            app = self._sessions[session_name]
            if file_path:
                app.SaveAs(os.path.abspath(file_path))
                return f"Session '{session_name}' saved to {file_path}."
            else:
                app.Save()
                return f"Session '{session_name}' saved."
        except Exception as exc:
            return f"Failed to save session '{session_name}'. Error: {exc}"

    # ------------------------------------------------------------------
    # Node value access (generic COM tree navigation)
    # ------------------------------------------------------------------

    def _get_app(self, session_name: str):
        """Return the COM application object or None."""
        if not self._is_alive(session_name):
            return None
        return self._sessions[session_name]

    def get_node_value(self, session_name: str, aspen_path: str) -> str:
        """Read a value from the Aspen Plus simulation tree.

        Args:
            session_name: Name of the active session.
            aspen_path: Backslash-delimited path in the Aspen tree
                        (e.g. ``\\Data\\Blocks\\B1\\Input\\NSTAGE``).
        """
        app = self._get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"
            value = node.Value
            return str(value) if value is not None else f"Node '{aspen_path}' has no value."
        except Exception as exc:
            return f"Error reading '{aspen_path}': {exc}"

    def add_component(self, session_name: str, component_id: str) -> str:
        """Add a component to the simulation component list."""
        app = self._get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(r"\Data\Components\Specifications\Input\TYPE")
            tlb = node.Elements
            tlb.InsertRow(0, 0)
            tlb.SetLabel(0, 0, False, component_id)
            return f"Component '{component_id}' added."
        except Exception as exc:
            return f"Failed to add component '{component_id}': {exc}"

    def set_node_value(self, session_name: str, aspen_path: str, value) -> str:
        """Write a value to the Aspen Plus simulation tree.

        Args:
            session_name: Name of the active session.
            aspen_path: Backslash-delimited path in the Aspen tree.
            value: The value to set.
        """
        app = self._get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"
            node.Value = value
            return f"Set '{aspen_path}' = {value}"
        except Exception as exc:
            return f"Error writing '{aspen_path}': {exc}"

    # ------------------------------------------------------------------
    # Flowsheet manipulation (skeleton — to be fleshed out)
    # ------------------------------------------------------------------

    def place_block(self, session_name: str, block_name: str, block_type: str) -> str:
        """Add a block to the flowsheet."""
        app = self._get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            path = f"\\Data\\Blocks\\{block_name}"
            node = app.Tree.FindNode(path)
            if node is not None:
                return f"Block '{block_name}' already exists."

            blocks_node = app.Tree.FindNode("\\Data\\Blocks")
            blocks_node.Elements.Add(f"{block_name}!{block_type}")
            time.sleep(0.5)
            return f"Block '{block_name}' ({block_type}) placed."
        except Exception as exc:
            return f"Failed to place block '{block_name}': {exc}"

    def remove_block(self, session_name: str, block_name: str) -> str:
        """Remove a block from the flowsheet."""
        app = self._get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            app.Tree.FindNode("\\Data\\Blocks").Elements.Remove(block_name)
            return f"Block '{block_name}' removed."
        except Exception as exc:
            return f"Failed to remove block '{block_name}': {exc}"

    def place_stream(self, session_name: str, stream_name: str, stream_type: str = "MATERIAL") -> str:
        """Add a stream to the flowsheet."""
        app = self._get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            app.Tree.FindNode("\\Data\\Streams").Elements.Add(f"{stream_name}!{stream_type}")
            return f"Stream '{stream_name}' ({stream_type}) placed."
        except Exception as exc:
            return f"Failed to place stream '{stream_name}': {exc}"

    def remove_stream(self, session_name: str, stream_name: str) -> str:
        """Remove a stream from the flowsheet."""
        app = self._get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            app.Tree.FindNode("\\Data\\Streams").Elements.Remove(stream_name)
            return f"Stream '{stream_name}' removed."
        except Exception as exc:
            return f"Failed to remove stream '{stream_name}': {exc}"

    def connect_stream(
        self,
        session_name: str,
        block_name: str,
        stream_name: str,
        port_name: str,
    ) -> str:
        """Connect a stream to a block port.

        Args:
            session_name: Name of the active session.
            block_name: Block to connect to (e.g. "R1").
            stream_name: Stream to attach (e.g. "FEED").
            port_name: Port identifier (e.g. "F(IN)", "LD(OUT)", "B(OUT)").
        """
        app = self._get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            blocks = app.Tree.FindNode("\\Data\\Blocks")
            blocks.Elements(block_name).Elements("Ports").Elements(port_name).Elements.Add(stream_name)
            return f"Stream '{stream_name}' connected to {block_name} port {port_name}."
        except Exception as exc:
            return f"Failed to connect stream '{stream_name}' to {block_name}:{port_name}: {exc}"
