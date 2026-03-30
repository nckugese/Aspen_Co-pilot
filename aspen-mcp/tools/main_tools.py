"""Implementations for main category tools (open, close, list, run, save, etc.).

reinit / run / save / list_node_children contain COM logic directly.
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)


def open_aspen_plus(manager, file_path: str) -> str:
    """Open Aspen Plus and load a .bkp simulation file."""
    return manager.open_with_file(file_path)


# Path to the blank simulation template bundled with the MCP
_BLANK_TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "..", "Blank_Simulation.bkp")


def create_new_simulation(manager, project_name: str, destination_folder: str = None) -> str:
    """Create a new Aspen Plus simulation by copying the blank template.

    Copies Blank_Simulation.bkp to <destination_folder>/<project_name>.bkp
    and opens it. If destination_folder is not provided, uses the same
    directory as the blank template.
    """
    import shutil

    template = os.path.abspath(_BLANK_TEMPLATE)
    if not os.path.exists(template):
        return f"Blank template not found at {template}. Cannot create new simulation."

    # Sanitize project name — strip .bkp if user included it
    name = project_name.strip()
    if name.lower().endswith(".bkp"):
        name = name[:-4]

    if destination_folder:
        dest_dir = os.path.abspath(destination_folder)
    else:
        dest_dir = os.path.dirname(template)

    if not os.path.isdir(dest_dir):
        return f"Destination folder does not exist: {dest_dir}"

    dest_path = os.path.join(dest_dir, f"{name}.bkp")
    if os.path.exists(dest_path):
        return f"File already exists: {dest_path}. Open it with open_aspen_plus or choose a different name."

    try:
        shutil.copy2(template, dest_path)
    except Exception as exc:
        logger.error("Failed to copy template to '%s': %s", dest_path, exc, exc_info=True)
        return f"Failed to copy template: {exc}"

    # Open the new simulation
    result = manager.open_with_file(dest_path)
    return f"Created new simulation: {dest_path}\n{result}"


def close_aspen_plus(manager, session_name: str = None) -> str:
    """Close an Aspen Plus session."""
    return manager.close(session_name)


def list_aspen_sessions(manager) -> str:
    """List all active Aspen Plus sessions."""
    return manager.list_sessions()


def reinit_simulation(manager, session_name: str) -> str:
    """Reinitialize the simulation in a given session."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        app.SuppressDialogs = 1
        app.Reinit()
        app.SuppressDialogs = 0
        return f"Simulation '{session_name}' reinitialized."
    except Exception as exc:
        logger.error("Failed to reinitialize '%s': %s", session_name, exc, exc_info=True)
        return f"Failed to reinitialize simulation '{session_name}'. Error: {exc}"


def run_simulation(manager, session_name: str) -> str:
    """Run the simulation in a given session.

    Checks that all required inputs are complete before running,
    matching the behavior of the Aspen Plus UI Run button.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        # Check input completeness via COMPSTATUS attribute on the root Data node
        # HAP_COMPSTATUS = 12, HAP_INPUT_INCOMPLETE = 64, HAP_INPUT_COMPLETE = 128
        root = app.Tree.FindNode(r"\Data")
        if root is not None:
            try:
                status = root.AttributeValue(12)  # HAP_COMPSTATUS
                if isinstance(status, int):
                    if status & 64:  # HAP_INPUT_INCOMPLETE
                        return (
                            f"Cannot run simulation '{session_name}': "
                            "required inputs are incomplete. "
                            "Use check_inputs to see what is missing."
                        )
            except Exception:
                logger.debug("COMPSTATUS check failed for '%s', proceeding to run", session_name)

        app.Run2()
        # Wait for simulation to finish (Run2 may return asynchronously)
        while app.Engine.IsRunning:
            time.sleep(0.5)

        # Auto-check run status; only dig deeper if there are issues
        run_status = _check_run_status(app)

        msg = f"Simulation '{session_name}' run completed."
        if run_status:
            msg += "\n\n" + run_status
            msg += "\n\n" + _check_block_errors(app)
            convergence_report = _check_loop_convergence(app)
            if convergence_report:
                msg += "\n\n" + convergence_report
            msg += (
                "\n\n⚠ STOP — Use the aspen-doc agent to look up the relevant block documentation, "
                "and follow the troubleshooting workflow in docs/troubleshooting.md"
            )
        return msg
    except Exception as exc:
        logger.error("Failed to run simulation '%s': %s", session_name, exc, exc_info=True)
        return f"Failed to run simulation '{session_name}'. Error: {exc}"


def _check_run_status(app) -> str:
    """Check simulation-level run status from Results Summary."""
    try:
        per_node = app.Tree.FindNode(
            r"\Data\Results Summary\Run-Status\Output\PER_ERROR"
        )
        if per_node is None:
            return ""
        els = per_node.Elements
        if els.Count == 0:
            return ""

        lines = []
        for i in range(els.Count):
            val = els.Item(i).Value
            if val is not None and str(val).strip():
                lines.append(str(val).strip())

        if not lines:
            return ""
        return "Run status message:\n  " + "\n  ".join(lines)
    except Exception:
        logger.debug("_check_run_status failed", exc_info=True)
        return "Warning: could not read run status"


def _check_block_errors(app) -> str:
    """Check BLKSTAT and PER_ERROR for all blocks after a run."""
    try:
        blocks_node = app.Tree.FindNode(r"\Data\Blocks")
        if blocks_node is None:
            return ""
        els = blocks_node.Elements
        if els.Count == 0:
            return ""

        errors = []
        for i in range(els.Count):
            block = els.Item(i)
            block_name = block.Name
            try:
                stat_node = app.Tree.FindNode(
                    rf"\Data\Blocks\{block_name}\Output\BLKSTAT"
                )
                if stat_node is None or stat_node.Value is None:
                    continue
                blkstat = stat_node.Value
                if blkstat == 0:
                    continue  # OK

                # Get short message
                msg_node = app.Tree.FindNode(
                    rf"\Data\Blocks\{block_name}\Output\BLKMSG"
                )
                blkmsg = msg_node.Value if msg_node is not None and msg_node.Value else ""

                # Get detailed error from PER_ERROR
                per_node = app.Tree.FindNode(
                    rf"\Data\Blocks\{block_name}\Output\PER_ERROR"
                )
                detail = ""
                if per_node is not None:
                    per_els = per_node.Elements
                    if per_els.Count > 0:
                        detail_lines = []
                        for j in range(per_els.Count):
                            detail_lines.append(str(per_els.Item(j).Value))
                        detail = "\n    ".join(detail_lines)

                entry = f"  {block_name}: {blkmsg}"
                if detail:
                    entry += f"\n    {detail}"
                errors.append(entry)
            except Exception:
                logger.debug("Failed to read error info for block %d", i, exc_info=True)
                continue

        if not errors:
            return ""
        return "Block errors:\n" + "\n".join(errors)
    except Exception:
        logger.debug("_check_block_errors failed", exc_info=True)
        return "Warning: could not read block error status"


def _check_loop_convergence(app) -> str:
    """Check convergence status for all loop solvers after a run.

    Uses ROWSTAT3 for the official status, and shows the last 5 ERR_TOL2
    values so the user can see the trend.
    """
    try:
        conv_node = app.Tree.FindNode(r"\Data\Convergence\Convergence")
        if conv_node is None:
            return ""
        els = conv_node.Elements
        if els.Count == 0:
            return ""

        lines = ["Loop convergence summary:"]
        for i in range(els.Count):
            solver = els.Item(i)
            solver_name = solver.Name
            try:
                # Official convergence status
                status_node = app.Tree.FindNode(
                    rf"\Data\Convergence\Convergence\{solver_name}\Output\ROWSTAT3"
                )
                status = status_node.Value if status_node is not None else "UNKNOWN"

                # Total iterations
                iter_node = app.Tree.FindNode(
                    rf"\Data\Convergence\Convergence\{solver_name}\Output\TOT_ITER"
                )
                tot_iter = iter_node.Value if iter_node is not None else "?"

                # Last 5 ERR_TOL2 values for trend
                err_node = app.Tree.FindNode(
                    rf"\Data\Convergence\Convergence\{solver_name}\Output\ERR_TOL2"
                )
                tail_str = ""
                if err_node is not None:
                    err_els = err_node.Elements
                    n = err_els.Count
                    if n > 0:
                        start = max(0, n - 5)
                        tail = [err_els.Item(j).Value for j in range(start, n)]
                        tail_str = " | last errors: [" + ", ".join(f"{v:.4g}" for v in tail) + "]"

                lines.append(f"  {solver_name}: {status} in {tot_iter} iterations{tail_str}")
            except Exception:
                logger.debug("Failed to read convergence data for '%s'", solver_name, exc_info=True)
                lines.append(f"  {solver_name}: could not read convergence data")

        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception:
        logger.debug("_check_loop_convergence failed", exc_info=True)
        return "Warning: could not read loop convergence status"


def get_flowsheet_topology(manager, session_name: str) -> str:
    """Show all stream connections: source block → stream → destination block."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        # Build connection map from Block Connections (always available, even
        # before a simulation run — unlike the Output/SOURCE|DESTINATION nodes
        # on streams which are only populated after a successful run).
        stream_src: dict[str, str] = {}  # stream_name → source block
        stream_dst: dict[str, str] = {}  # stream_name → destination block

        blocks_node = app.Tree.FindNode(r"\Data\Blocks")
        if blocks_node is not None:
            for i in range(blocks_node.Elements.Count):
                block = blocks_node.Elements.Item(i)
                block_name = block.Name
                conn_node = app.Tree.FindNode(
                    rf"\Data\Blocks\{block_name}\Connections"
                )
                if conn_node is None:
                    continue
                for j in range(conn_node.Elements.Count):
                    elem = conn_node.Elements.Item(j)
                    sname = elem.Name          # stream name
                    port_info = str(elem.Value) if elem.Value else ""
                    if "(IN)" in port_info.upper():
                        stream_dst[sname] = block_name
                    elif "(OUT)" in port_info.upper():
                        stream_src[sname] = block_name

        streams_node = app.Tree.FindNode(r"\Data\Streams")
        if streams_node is None:
            return "No streams found."
        els = streams_node.Elements
        if els.Count == 0:
            return "No streams found."

        lines = []
        for i in range(els.Count):
            stream_name = els.Item(i).Name
            src_label = stream_src.get(stream_name, "(FEED)")
            dst_label = stream_dst.get(stream_name, "(OUT)")
            lines.append(f"  {src_label} --[{stream_name}]--> {dst_label}")

        return f"Flowsheet topology ({els.Count} streams):\n" + "\n".join(lines)
    except Exception as exc:
        logger.error("Failed to get topology for '%s': %s", session_name, exc, exc_info=True)
        return f"Failed to get flowsheet topology. Error: {exc}"


def save_simulation(manager, session_name: str, file_path: str = None) -> str:
    """Save the current simulation to disk."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        if file_path:
            app.SaveAs(os.path.abspath(file_path))
            return f"Session '{session_name}' saved to {file_path}."
        else:
            app.Save()
            return f"Session '{session_name}' saved."
    except Exception as exc:
        logger.error("Failed to save session '%s': %s", session_name, exc, exc_info=True)
        return f"Failed to save session '{session_name}'. Error: {exc}"


def check_inputs(manager, session_name: str) -> str:
    """Check if all required inputs are complete before running.

    Uses NextIncomplete(64) to walk the tree and find all incomplete input nodes.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    incomplete = []
    node = app.Tree.FindNode(r"\Data")
    seen = set()
    for _ in range(200):  # safety limit
        try:
            result = node.NextIncomplete(64)  # HAP_INPUT_INCOMPLETE
        except Exception:
            logger.debug("NextIncomplete iteration ended", exc_info=True)
            break  # no more incomplete items
        # COM returns (path_or_node, code) tuple
        if isinstance(result, tuple):
            item = result[0]
        else:
            item = result
        if item is None:
            break
        # item may be a path string or a COM node
        if isinstance(item, str):
            path = item
            if not path or path in seen:
                break
            seen.add(path)
            incomplete.append(f"  - {path}")
            # navigate to this node for next iteration
            next_node = app.Tree.FindNode(path)
            if next_node is None:
                break
            node = next_node
        else:
            # COM node object
            name = item.Name
            if not name or name in seen:
                break
            seen.add(name)
            try:
                prompt = item.AttributeValue(19)  # HAP_PROMPT
            except Exception:
                logger.debug("Could not read HAP_PROMPT for '%s'", name)
                prompt = ""
            if prompt:
                incomplete.append(f"  - {name}: {prompt}")
            else:
                incomplete.append(f"  - {name}")
            node = item

    if not incomplete:
        return "All required inputs are complete. Ready to run."
    result = f"Incomplete inputs ({len(incomplete)}):\n" + "\n".join(incomplete)
    result += (
        "\n\n⚠ Use the aspen-doc agent to look up required fields "
        "for the incomplete block(s)."
    )
    return result


def get_node_value(manager, session_name: str, aspen_path: str) -> str:
    """Read a raw value from the Aspen Plus data tree."""
    return manager.get_node_value(session_name, aspen_path)


def set_node_value(manager, session_name: str, aspen_path: str, value=None, unit: str = None, basis: str = None) -> str:
    """Write a raw value to the Aspen Plus data tree."""
    return manager.set_node_value(session_name, aspen_path, value=value, unit=unit, basis=basis)


def get_node_unit_info(manager, session_name: str, aspen_path: str) -> str:
    """Return unit information for a node."""
    return manager.get_node_unit_info(session_name, aspen_path)


def get_node_attribute(manager, session_name: str, aspen_path: str, attribute) -> str:
    """Read an attribute from a node."""
    return manager.get_node_attribute(session_name, aspen_path, attribute)


def set_node_attribute(manager, session_name: str, aspen_path: str, attribute, value) -> str:
    """Write an attribute on a node."""
    return manager.set_node_attribute(session_name, aspen_path, attribute, value)


def list_node_children(manager, session_name: str, aspen_path: str) -> str:
    """List all child elements of a node in the Aspen Plus data tree."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    try:
        node = app.Tree.FindNode(aspen_path)
        if node is None:
            return f"Node not found: {aspen_path}"
        els = node.Elements
        if els.Count == 0:
            return f"'{aspen_path}' has no children."
        children = []
        for i in range(els.Count):
            child = els.Item(i)
            if child is None:
                children.append(f"  [{i}] = (None object)")
                continue
            try:
                name = child.Name
                if name is None:
                    name = f"[{i}]"
            except Exception:
                logger.debug("Could not read name for child %d at '%s'", i, aspen_path)
                name = f"[{i}]"
            try:
                val = child.Value
                if val is None:
                    try:
                        sub = child.Elements
                        if sub is not None and sub.Count > 0:
                            children.append(f"  {name} = [table, {sub.Count} entries]")
                        else:
                            children.append(f"  {name} = None")
                    except Exception:
                        logger.debug("Could not read sub-elements for '%s' at '%s'", name, aspen_path)
                        children.append(f"  {name} = None")
                else:
                    children.append(f"  {name} = {val}")
            except Exception:
                logger.debug("Could not read value for '%s' at '%s'", name, aspen_path)
                children.append(f"  {name}/")
        return f"Children of '{aspen_path}' ({els.Count}):\n" + "\n".join(children)
    except Exception as exc:
        logger.error("Error listing '%s': %s", aspen_path, exc, exc_info=True)
        return f"Error listing '{aspen_path}': {exc}"
