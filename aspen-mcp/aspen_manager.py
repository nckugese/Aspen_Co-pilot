import os
import win32com.client
import win32com.client.dynamic
import pythoncom

from searcher import unit_table


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
            aspen = win32com.client.dynamic.Dispatch("Apwn.Document")
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
            if value is None:
                return f"Node '{aspen_path}' has no value."
            # Append unit string if the node has one
            try:
                unit_str = node.UnitString
                if unit_str:
                    return f"{value} (unit: {unit_str})"
            except Exception:
                pass
            return str(value)
        except Exception as exc:
            return f"Error reading '{aspen_path}': {exc}"

    def set_node_value(
        self, session_name: str, aspen_path: str,
        value=None, unit: str = None, basis: str = None,
    ) -> str:
        """Write a value to the Aspen Plus simulation tree.

        Smart dispatch based on which arguments are provided:
          - value only                → node.Value = value
          - value + unit (no basis)   → SetValueAndUnit(value, unitcol, force)
          - anything with basis       → SetValueUnitAndBasis(value, unitcol, basis, force)
          - unit only / basis only    → reads current value first, then sets
        """
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"

            has_value = value is not None
            has_unit = unit is not None
            has_basis = basis is not None

            if not has_value and not has_unit and not has_basis:
                return "Nothing to set -- provide at least one of: value, unit, basis."

            # Check enterable via HAP_ENTERABLE (attr 7): 0 = not enterable
            try:
                if not node.AttributeValue(7):
                    return f"Node '{aspen_path}' is not enterable."
            except Exception:
                pass  # Attribute not available — proceed anyway

            # Simple case: value only, no unit/basis change
            if has_value and not has_unit and not has_basis:
                node.Value = value
                return f"Set '{aspen_path}' = {value}"

            # Resolve the value to use
            v = float(value) if has_value else float(node.Value)

            # Resolve unitcol
            if has_unit:
                unitcol = unit_table.lookup_unit(unit)
                if unitcol is None:
                    return f"Unknown unit '{unit}'. Use get_node_unit_info to see available units."
            else:
                # Keep current unit — look up unitcol from current UnitString
                try:
                    current_unit = node.UnitString
                    unitcol = unit_table.lookup_unit(current_unit) if current_unit else 0
                except Exception:
                    unitcol = 0

            # Dispatch: use SetValueAndUnit when no basis, SetValueUnitAndBasis when basis involved
            if has_basis:
                node.SetValueUnitAndBasis(v, unitcol, basis, False)
            else:
                node.SetValueAndUnit(v, unitcol, False)

            # Read back for confirmation
            parts = [f"Set '{aspen_path}' = {v}"]
            try:
                confirmed_unit = node.UnitString
                if confirmed_unit:
                    parts.append(confirmed_unit)
            except Exception:
                if has_unit:
                    parts.append(unit)
            if has_basis:
                parts.append(f"(basis: {basis})")
            return " ".join(parts)
        except Exception as exc:
            return f"Error writing '{aspen_path}': {exc}"

    def get_node_unit_info(self, session_name: str, aspen_path: str) -> str:
        """Return unit information for a node: current unit, dimension, and available units."""
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"

            try:
                unit_str = node.UnitString
            except Exception:
                return f"Node '{aspen_path}' has no unit information."

            if not unit_str:
                return f"Node '{aspen_path}' has no unit information."

            # Find dimension from current unit string
            dim_row = unit_table.find_dimension_by_unit(unit_str)

            if dim_row is None:
                return (
                    f"Current unit: {unit_str}\n"
                    f"(Dimension not found for '{unit_str}')"
                )

            dim_name = unit_table.dimension_name(dim_row)
            available = unit_table.list_units_for_dimension(dim_row)

            lines = [
                f"Current unit: {unit_str}",
                f"Dimension: {dim_name} (row {dim_row})",
                f"Available units ({len(available)}):",
            ]
            for i, u in enumerate(available):
                marker = " <-- current" if u.lower() == unit_str.lower() else ""
                lines.append(f"  [{i}] {u}{marker}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Error reading unit info for '{aspen_path}': {exc}"

    # ------------------------------------------------------------------
    # Node attribute access (HAP_BASIS=13, HAP_UNITROW=2, HAP_UNITCOL=3, etc.)
    # ------------------------------------------------------------------

    # Well-known attribute numbers for reference
    HAP_ATTRS = {
        "VALUE": 0, "UNITROW": 2, "UNITCOL": 3,
        "OPTIONLIST": 5, "RECORDTYPE": 6, "ENTERABLE": 7,
        "UPPERLIMIT": 8, "LOWERLIMIT": 9, "VALUEDEFAULT": 10,
        "USERENTERED": 11, "COMPSTATUS": 12, "BASIS": 13,
        "INOUT": 14, "PROMPT": 19,
    }

    def get_node_attribute(self, session_name: str, aspen_path: str, attribute: int | str) -> str:
        """Read an attribute from a node.

        *attribute* can be an integer (e.g. 13) or a name (e.g. 'BASIS').
        """
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"

            attr_num = self._resolve_attr(attribute)
            if attr_num is None:
                return f"Unknown attribute '{attribute}'. Known: {', '.join(self.HAP_ATTRS.keys())}"

            val = node.AttributeValue(attr_num)
            return str(val)
        except Exception as exc:
            return f"Error reading attribute {attribute} on '{aspen_path}': {exc}"

    def set_node_attribute(self, session_name: str, aspen_path: str, attribute: int | str, value) -> str:
        """Write an attribute on a node.

        *attribute* can be an integer (e.g. 13) or a name (e.g. 'BASIS').
        Example: set_node_attribute(session, path, 'BASIS', 'Mass-Flow')
        """
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"

            attr_num = self._resolve_attr(attribute)
            if attr_num is None:
                return f"Unknown attribute '{attribute}'. Known: {', '.join(self.HAP_ATTRS.keys())}"

            # COM indexed property PUT: AttributeValue(attrnumber, force) = value
            # Python win32com requires low-level Invoke for parameterized PUT
            dispid = node._oleobj_.GetIDsOfNames('AttributeValue')
            if isinstance(dispid, tuple):
                dispid = dispid[0]
            node._oleobj_.Invoke(
                dispid, 0, pythoncom.DISPATCH_PROPERTYPUT, 0,
                attr_num, False, value,
            )
            # Read back for confirmation
            confirmed = node.AttributeValue(attr_num)
            return f"Set attribute {attribute} (#{attr_num}) on '{aspen_path}' = {confirmed}"
        except Exception as exc:
            return f"Error setting attribute {attribute} on '{aspen_path}': {exc}"

    def _resolve_attr(self, attribute: int | str) -> int | None:
        """Resolve an attribute name or number to an integer."""
        if isinstance(attribute, int):
            return attribute
        upper = str(attribute).upper().replace(" ", "_").replace("-", "_")
        return self.HAP_ATTRS.get(upper)
