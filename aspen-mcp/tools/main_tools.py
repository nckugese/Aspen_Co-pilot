"""Implementations for main category tools (open, close, list, run, save, etc.).

reinit / run / save / list_node_children contain COM logic directly.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import time

from tools import checkpoints, diagnose, dialogs, inputs_check, knowledge_tools, model_registry, probes
from tools.checkpoints import SaveError

logger = logging.getLogger(__name__)


def open_aspen_plus(manager, file_path: str, visible: bool = True) -> str:
    """Open Aspen Plus and load a .bkp simulation file.

    Pass ``visible=False`` to hide the Aspen window. Hidden mode is ~5-15%
    faster and uses less memory — recommended for long optimization runs.

    A file a running Aspen already has open (the user's own, or one the standalone workbench
    left) is taken as it is -- no second copy is opened; ASPEN_MCP_ATTACH=0 turns that off.
    """
    return open_or_attach(manager, file_path, visible=visible)


def open_or_attach(manager, file_path: str, visible: bool = True) -> str:
    """open_with_file, unless a running Aspen has the file open: then that document becomes the
    session (aspen_manager.attach). Also what the window's Open model does."""
    import aspen_manager                       # (here: aspen_manager imports tools)

    attach = getattr(manager, "attach", None)
    if attach is not None and aspen_manager.attach_on():
        try:
            res = attach(file_path)
        except Exception:
            logger.warning("attach to a running Aspen failed for %s; opening it instead", file_path, exc_info=True)
            res = None
        if res is not None:
            return res
    return manager.open_with_file(file_path, visible=visible)


# Path to the blank simulation template bundled with the MCP. It sits next to server.py so
# that it ships inside the installed package rather than depending on the repo checkout.
_BLANK_TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "Blank_Simulation.bkp")


def _default_destination() -> str:
    """Where a new simulation lands when the caller does not say.

    The working directory the MCP client launched us from -- the user's project -- is the
    useful default. Explicitly NOT the template's own directory: since the template ships
    inside the installed package, writing there would put the user's work somewhere an
    upgrade wipes.
    """
    pkg_dir = os.path.dirname(os.path.abspath(_BLANK_TEMPLATE))
    try:
        cwd = os.path.abspath(os.getcwd())
    except OSError:
        cwd = ""
    if cwd and cwd != pkg_dir and os.access(cwd, os.W_OK):
        return cwd
    fallback = os.path.join(os.path.expanduser("~"), ".aspen-mcp", "simulations")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def create_new_simulation(manager, project_name: str, destination_folder: str = None) -> str:
    """Create a new Aspen Plus simulation by copying the blank template.

    Copies Blank_Simulation.bkp to <destination_folder>/<project_name>.bkp
    and opens it. If destination_folder is not provided, the file is created in the
    current working directory -- the project the MCP client was opened in.
    """
    import shutil

    template = os.path.abspath(_BLANK_TEMPLATE)
    if not os.path.exists(template):
        return f"Blank template not found at {template}. Cannot create new simulation."

    # Sanitize project name — strip .bkp if user included it
    name = (project_name or "").strip()
    if name.lower().endswith(".bkp"):
        name = name[:-4]
    # A name, not a path: destination_folder says where the file goes.
    if (not name or name in (".", "..") or "/" in name or "\\" in name or ".." in name
            or os.path.isabs(name) or os.path.splitdrive(name)[0] or ":" in name):
        return (f"Invalid project_name {project_name!r}: give a file name without folders, "
                f"'..' or a drive (use destination_folder for the location).")

    if destination_folder:
        dest_dir = os.path.abspath(destination_folder)
    else:
        dest_dir = _default_destination()

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

    # A new model, not matched by content to earlier template copies. The file is the
    # server's own write, so the first save does not back up an empty template.
    mid = model_registry.fresh(dest_path)
    result = manager.open_with_file(dest_path, model_id=mid)
    session = manager._session_name(dest_path)
    checkpoints.after_write(mid, dest_path, tool="create_new_simulation", session=session,
                            sidecars=False)
    return f"Created new simulation: {dest_path}\n{result}"


def close_aspen_plus(manager, session_name: str = None) -> str:
    """Close an Aspen Plus session."""
    return manager.close(session_name)


def list_aspen_sessions(manager) -> str:
    """List all active Aspen Plus sessions."""
    return manager.list_sessions()


def fault_refusal(manager, session_name: str, verb: str = "run") -> str | None:
    """The refusal of a run (``verb`` "reinitialize": of a Reinitialize) in a session Aspen
    reported an internal fault in (aspen_manager.note_fault: such a run never returns); None
    when it may run. No COM."""
    fault = getattr(manager, "fault", None)
    why = fault(session_name) if fault is not None else None
    return f"Cannot {verb} simulation '{session_name}': {why}" if why else None


def fault_note(manager, session_name: str, tool: str):
    """A walk's ``fault`` callback (inputs_check.deep / report): Aspen's internal fault met there
    flags the session (aspen_manager.note_fault), as a tool's own exception would; None when the
    manager keeps no such flag. No COM."""
    note = getattr(manager, "note_fault", None)
    return None if note is None else (lambda exc: note(session_name, exc, tool=tool))


def reinit_simulation(manager, session_name: str) -> str:
    """Reinitialize the simulation in a given session."""
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    refused = fault_refusal(manager, session_name, "reinitialize")
    if refused:
        return refused
    try:
        with dialogs.suppressed(app):
            app.Reinit()
        return f"Simulation '{session_name}' reinitialized."
    except Exception as exc:
        logger.error("Failed to reinitialize '%s': %s", session_name, exc, exc_info=True)
        return f"Failed to reinitialize simulation '{session_name}'. Error: {exc}"


def _model_dirs(manager, session_name: str) -> list[str]:
    """The folder of the session's model file, where the engine runs (its history file, a
    USER3's .cfg); [] when the manager knows no file. No COM."""
    get = getattr(manager, "session_file", None)
    try:
        f = get(session_name) if callable(get) else None
    except Exception:
        f = None
    return [os.path.dirname(os.path.abspath(f))] if f else []


def run_simulation(manager, session_name: str) -> str:
    """Run the simulation in a given session.

    Checks that all required inputs are complete before running,
    matching the behavior of the Aspen Plus UI Run button.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    refused = fault_refusal(manager, session_name)
    if refused:
        return refused
    try:
        # The same COMPSTATUS scan as check_inputs, so the two verdicts agree
        # (tools/inputs_check.py; the root \Data is deliberately not read). A flagged block is
        # read the way the GUI reads it and scanned again before it is believed (refresh); an
        # open required port and the translator's known traps refuse too: Aspen runs nothing then.
        sc = inputs_check.scan(app, ports=True)
        if inputs_check.refusal_paths(sc) and inputs_check.refresh(app, sc):
            sc = inputs_check.scan(app, ports=True)
        incomplete = inputs_check.refusal_names(sc)
        traps = inputs_check.traps(app, _model_dirs(manager, session_name))
        if incomplete or traps:
            msg = f"Cannot run simulation '{session_name}': "
            if incomplete:
                msg += (f"required inputs are incomplete under: {', '.join(incomplete)}. "
                        "Use check_inputs for details.")
            if traps:
                msg += ("\n" if incomplete else "") + "Aspen's input translator would reject:\n  - " + "\n  - ".join(traps)
            return msg

        his_dirs = list(dict.fromkeys(_model_dirs(manager, session_name) + [os.getcwd()]))
        his_marks, t_wall = _his_marks(his_dirs), time.time()
        t0 = time.perf_counter()
        with dialogs.suppressed(app):
            app.Run2()
            # Wait for simulation to finish (Run2 may return asynchronously)
            while app.Engine.IsRunning:
                time.sleep(0.5)

        # Auto-check run status; only dig deeper when it says warnings or errors (probes.run_state:
        # the verdict the journal and the workbench give the same lines). A line Aspen writes
        # after every clean run ("Properties estimation was never executed") is only information.
        run_status = _check_run_status(app)
        lines = probes.said_lines(app, run_status, t0)
        verdict = probes.run_state(None, blocks=False, lines=lines)["status"] if lines is not None else "unknown"

        msg = f"Simulation '{session_name}' run completed."
        if run_status:
            msg += "\n\n" + run_status
        if verdict == "unknown":
            why = _why_not_run(app, his_dirs, his_marks, t_wall)
            msg += (" -- and Aspen's history file reports errors: the run did not complete cleanly."
                    if probes.his_errors(why) else " -- so whether this run converged is not known.")
            if why:
                msg += "\n\n" + why
            return msg
        unrun = _no_result_blocks(app)
        if verdict != "ok":
            msg += "\n\n" + _check_block_errors(app)
            convergence_report = _check_loop_convergence(app)
            if convergence_report:
                msg += "\n\n" + convergence_report
            msg += (
                "\n\n⚠ STOP — Use the aspen-doc agent to look up the relevant block documentation, "
                "and follow the aspen-error-troubleshooting workflow: known fixes are in error-history.md "
                "(ASPEN_USER_DATA first, then ASPEN_DOCS_ROOT), convergence settings in convergence/convergence.md"
            )
        if unrun:
            msg += "\n\n" + unrun
        return msg
    except Exception as exc:
        logger.error("Failed to run simulation '%s': %s", session_name, exc, exc_info=True)
        return f"Failed to run simulation '{session_name}'. Error: {exc}"


def _check_run_status(app) -> str:
    """Check simulation-level run status from Results Summary. The lines read are handed to
    tools/probes.py (``saw_status``): the journal's run record and the workbench use them
    instead of reading them again."""
    try:
        per_node = app.Tree.FindNode(
            r"\Data\Results Summary\Run-Status\Output\PER_ERROR"
        )
        if per_node is None:                 # no run status at all: unknown, as the journal says
            return probes.UNREADABLE
        els = per_node.Elements
        if els.Count == 0:
            probes.saw_status(app, [])
            return ""

        values = [els.Item(i).Value for i in range(els.Count)]
        probes.saw_status(app, values)
        lines = []
        for val in values:
            if val is not None and str(val).strip():
                lines.append(str(val).strip())

        if not lines:
            return ""
        return "Run status message:\n  " + "\n  ".join(lines)
    except Exception:
        logger.debug("_check_run_status failed", exc_info=True)
        return probes.UNREADABLE


# The engine's history file (_xxxxnnn.his, beside the model; Aspen deletes it on closing). Without a
# run status it is the only place a run that never started says why (Aspen V15: CONCHK.4,
# ZUSPAN.2, U3ERRR.1, ATLOOK.1, NXTITM.1, EDBSEM.1, each with the block it is about).
_HIS_HEAD = re.compile(r"^\s*\*+\s*((?:SEVERE |SYSTEM |TERMINAL )?ERROR\b(?! SEVERITY).*)")
_HIS_MSGS = 6                                    # messages quoted at most
_HIS_CHARS = 300                                 # characters per message at most
_HIS_LINK = ("CPLNKI", "FPFNDI")                 # a user subroutine the engine could not link


def _his_marks(dirs) -> dict:
    """{history file: size} in ``dirs`` now: a run's own part is what comes after."""
    out = {}
    for d in dirs:
        try:
            for f in glob.glob(os.path.join(d, "_*.his")):
                out[f] = os.path.getsize(f)
        except OSError:
            pass
    return out


def _his_errors(text: str) -> list[str]:
    """The ERROR / SEVERE ERROR / SYSTEM ERROR / TERMINAL ERROR messages of a history text, each
    on one line, in order, without repeats."""
    msgs, cur = [], None
    for line in text.splitlines():
        m = _HIS_HEAD.match(line)
        if m:
            cur = [m.group(1).strip()]
            msgs.append(cur)
        elif cur is not None and line.strip() and not line.strip().startswith("*"):
            cur.append(line.strip())
        else:
            cur = None
    out = []
    for parts in msgs:
        s = " ".join(" ".join(parts).split())
        s = s if len(s) <= _HIS_CHARS else s[:_HIS_CHARS] + "..."
        if s not in out:
            out.append(s)
    return out


def _why_not_run(app, dirs, marks: dict, since: float) -> str:
    """For a run whose status cannot be read: the errors the newest history file in ``dirs``
    gained since ``since`` (its part after ``marks``), a note when a user subroutine could not be
    linked, and the blocks with no BLKSTAT; "" when there is none of these."""
    out = []
    files = []
    for d in dirs:
        try:
            files += [f for f in glob.glob(os.path.join(d, "_*.his")) if os.path.getmtime(f) >= since - 2]
        except OSError:
            pass
    if files:
        f = max(files, key=os.path.getmtime)
        try:
            with open(f, "rb") as fh:
                start = marks.get(f, 0)
                fh.seek(start if start <= os.path.getsize(f) else 0)
                text = fh.read().decode("latin-1")
        except OSError:
            text = ""
        errs = _his_errors(text)
        if errs:
            more = f"\n  (+{len(errs) - _HIS_MSGS} more)" if len(errs) > _HIS_MSGS else ""
            out.append(f"{probes.HIS_HEAD}{os.path.basename(f)}):\n  "
                       + "\n  ".join(errs[:_HIS_MSGS]) + more)
        if any(c in text for c in _HIS_LINK):
            out.append("A user subroutine could not be linked: point the linker options engine file at the "
                       ".opt that lists its object or DLL -- set_engine_file(session, <path to the .opt>, "
                       "kind=\"linker_options\") -- and run again.")
    unrun = _no_result_blocks(app)
    if unrun:
        out.append(unrun)
    return "\n".join(out)


def _no_result_blocks(app) -> str:
    """'Blocks with no result (BLKSTAT empty): B1, B2' for the blocks a run left without a block
    status (not run: the sequence stopped before them, or nothing ran); "" when every block has one."""
    try:
        els = app.Tree.FindNode(r"\Data\Blocks").Elements
        none = []
        for i in range(els.Count):
            name = els.Item(i).Name
            node = app.Tree.FindNode(rf"\Data\Blocks\{name}\Output\BLKSTAT")
            if node is None or node.Value is None:
                none.append(name)
        if none:
            shown = ", ".join(none[:12]) + (f" (+{len(none) - 12} more)" if len(none) > 12 else "")
            return f"Blocks with no result (BLKSTAT empty): {shown}"
    except Exception:
        logger.debug("_no_result_blocks: blocks not read", exc_info=True)
    return ""


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


# The error keywords worth recording and the keyword -> mechanism map (most specific first)
# live in tools/diagnose.py, which the workbench's failure card shares them from.
_ERROR_KEYWORDS = diagnose._ERROR_KEYWORDS
_MECHANISM_PATTERNS = diagnose._MECHANISM_PATTERNS


def classify_mechanisms(reason: str, detail: str, constraints=None) -> list[str]:
    """Turn ONE eval's (reason, detail) into multi-label failure tags.

    Pure string logic over the already-captured ``info['reason']`` /
    ``info['detail']`` from ``evaluate_x`` — no COM access. A single failed eval
    can yield SEVERAL tags. Examples:
      - reason='not_converged', detail='COL1: COLUMN NOT IN MASS BALANCE ; R1: ... FLASH ...'
            -> ['block:COL1:not_in_mass_balance', 'block:R1:flash']
      - reason='constraint', detail='constraint violated: PROPYL1=0.99 (viol=0.005)'
            -> ['constraint:PROPYL1'], or [] when ``constraints`` is given: declared
            constraints are modelled on their values (afmcbo's regression GPs), so a
            tag would count the same violation twice
      - reason in {set_fail, com_error, run_fail, obj_read_fail} -> [reason]
      - reason='ok' / '' -> []
    """
    if not reason or reason == "ok" or (reason == "constraint" and constraints):
        return []
    tags: list[str] = []
    detail = detail or ""
    if reason == "not_converged":
        # detail = "BLOCK1: msg | line ; BLOCK2: ..." (see extract_error_keywords)
        for seg in detail.split(" ; "):
            seg = seg.strip()
            if not seg or ": " not in seg:
                continue
            block_name, rest = seg.split(": ", 1)
            rest_u = rest.upper()
            mech = next((m for pat, m in _MECHANISM_PATTERNS if pat in rest_u), "unknown")
            tags.append(f"block:{block_name.strip()}:{mech}")
        if not tags:
            tags.append("not_converged")
    elif reason == "constraint":
        # detail = "constraint violated: NAME=val (viol=...); NAME2=..."
        body = detail.split(":", 1)[1] if ":" in detail else detail
        for part in body.split(";"):
            name = part.split("=", 1)[0].strip()
            if name:
                tags.append(f"constraint:{name}")
        if not tags:
            tags.append("constraint")
    else:
        tags.append(reason)  # set_fail / com_error / run_fail / obj_read_fail
    seen: list[str] = []
    for t in tags:
        if t not in seen:
            seen.append(t)
    return seen


def extract_error_keywords(app, max_len: int = 300) -> str:
    """Return a compact, single-line summary of Aspen block error keywords.

    Used by the optimizers / grid search to record *why* an evaluation failed
    (e.g. ``COL1: COLUMN NOT IN MASS BALANCE``) into evaluations.csv. Scans every
    block; for those with ``BLKSTAT != 0`` it collects the short ``BLKMSG``
    headline plus any ``PER_ERROR`` line matching a known error keyword. The
    result is whitespace-collapsed, de-duplicated and length-capped so it fits
    cleanly in one CSV cell. Returns "" when no block reports an error.
    """
    out: list[str] = []
    try:
        blocks_node = app.Tree.FindNode(r"\Data\Blocks")
        if blocks_node is None:
            return ""
        els = blocks_node.Elements
        for i in range(els.Count):
            block_name = els.Item(i).Name
            try:
                stat_node = app.Tree.FindNode(
                    rf"\Data\Blocks\{block_name}\Output\BLKSTAT"
                )
                if stat_node is None or stat_node.Value is None or stat_node.Value == 0:
                    continue
                parts: list[str] = []
                msg_node = app.Tree.FindNode(
                    rf"\Data\Blocks\{block_name}\Output\BLKMSG"
                )
                if msg_node is not None and msg_node.Value:
                    parts.append(" ".join(str(msg_node.Value).split()))
                per_node = app.Tree.FindNode(
                    rf"\Data\Blocks\{block_name}\Output\PER_ERROR"
                )
                if per_node is not None:
                    per_els = per_node.Elements
                    for j in range(per_els.Count):
                        line = " ".join(str(per_els.Item(j).Value).split())
                        if line and any(k in line.upper() for k in _ERROR_KEYWORDS):
                            parts.append(line)
                seen: list[str] = []
                for p in parts:
                    if p and p not in seen:
                        seen.append(p)
                if seen:
                    out.append(f"{block_name}: " + " | ".join(seen))
            except Exception:
                logger.debug("extract_error_keywords: block %d failed", i, exc_info=True)
                continue
    except Exception:
        logger.debug("extract_error_keywords failed", exc_info=True)
        return ""
    result = " ; ".join(out)
    if len(result) > max_len:
        result = result[: max_len - 3] + "..."
    return result


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
    """Save the session's model: to the file on record for it, or (Save As) to ``file_path``,
    which the session is then bound to. An existing file is backed up first
    (tools/checkpoints.py); if that backup fails nothing is written."""
    if manager.get_app(session_name) is None:
        return f"No active session named '{session_name}'."
    try:
        if file_path:
            res = manager.save_as(session_name, file_path)
        else:
            res = manager.save(session_name)
    except SaveError as exc:
        return str(exc)
    except Exception as exc:
        logger.error("Failed to save session '%s': %s", session_name, exc, exc_info=True)
        return f"Failed to save session '{session_name}'. Error: {exc}"
    return "\n".join(filter(None, (f"Session '{session_name}' saved to {res['path']}.",
                                    checkpoints.note(res["backup"]))))


def check_inputs(manager, session_name: str) -> str:
    """Check if all required inputs are complete before running.

    Scans for the COMPSTATUS incomplete bit and details each flagged object
    (tools/inputs_check.py): unset and zero-valued fields with prompts, mode
    switches, GUI catalog rules, port connectivity.
    """
    app = manager.get_app(session_name)
    if app is None:
        return f"No active session named '{session_name}'."
    return inputs_check.render(inputs_check.report(app, fault=fault_note(manager, session_name, "check_inputs"),
                                                   folders=_model_dirs(manager, session_name)))


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
        kids = knowledge_tools._children(node.Elements)     # never Item(i): it can fault Aspen
        if not kids:
            return f"'{aspen_path}' has no children."
        children = []
        for i, child in enumerate(kids):
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
        return f"Children of '{aspen_path}' ({len(kids)}):\n" + "\n".join(children)
    except Exception as exc:
        logger.error("Error listing '%s': %s", aspen_path, exc, exc_info=True)
        return f"Error listing '{aspen_path}': {exc}"
