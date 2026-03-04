import os
import win32com.client
import pythoncom


class AspenPlusManager:
    """Manages multiple Aspen Plus COM connections.

    Responsible only for session lifecycle and low-level COM tree access.
    All business logic (blocks, streams, components, etc.) lives in tools/.
    """

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

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

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
    # COM object access
    # ------------------------------------------------------------------

    def get_app(self, session_name: str):
        """Return the COM application object or None."""
        if not self._is_alive(session_name):
            return None
        return self._sessions[session_name]

    # ------------------------------------------------------------------
    # Low-level node value access (shared by block/stream/properties tools)
    # ------------------------------------------------------------------

    def get_node_value(self, session_name: str, aspen_path: str) -> str:
        """Read a value from the Aspen Plus simulation tree."""
        app = self.get_app(session_name)
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

    def set_node_value(self, session_name: str, aspen_path: str, value) -> str:
        """Write a value to the Aspen Plus simulation tree."""
        app = self.get_app(session_name)
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
