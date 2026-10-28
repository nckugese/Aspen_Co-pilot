import ctypes
import gc
import glob
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from ctypes import wintypes

import win32com.client
import win32com.client.dynamic
import pythoncom

try:
    import win32gui
    import win32con
    import win32process
    _HAS_WIN32GUI = True
except Exception:  # pragma: no cover - pywin32 GUI bindings unavailable
    _HAS_WIN32GUI = False

from searcher import unit_table
from tools import activity, checkpoints, dialogs, dispid, external, journal, model_registry, nodes, recorder
from tools import flowsheet_tools, knowledge_tools, restore_points
from tools.checkpoints import SaveError

logger = logging.getLogger(__name__)

# RPC_E_SERVERFAULT: Aspen threw inside a COM call. Live V15: after one (Elements.Item on a
# binary parameter set's CC Nodes\LBLLE\NRTL: ~20 s, then this) Aspen stays up and answers
# reads, but Run2 never returns and Reinit does not clear it; Export still works, and a fresh
# Aspen opened from the export runs. So a session that saw one has its runs refused.
SERVER_FAULT = -2147417851
_FAULT_MARKS = (str(SERVER_FAULT), "0x80010105")
FAULT_TEXT = ("Aspen reported an internal fault in this session; runs would hang. Export or save a copy, "
              "then close and reopen the model.")


def server_fault(what) -> bool:
    """``what`` -- an exception, or a tool's answer -- carries RPC_E_SERVERFAULT: as the COM
    error's HRESULT, as the exception's scode, or in the text (a tool's "Error ...: (-2147417851,
    ...)")."""
    if isinstance(what, BaseException):
        info = getattr(what, "excepinfo", None)
        if getattr(what, "hresult", None) == SERVER_FAULT or (
                isinstance(info, tuple) and len(info) > 5 and info[5] == SERVER_FAULT):
            return True
        what = str(what)
    return isinstance(what, str) and any(m in what.lower() for m in _FAULT_MARKS)


def _unit_row(node) -> int | None:
    """The unit-table row (physical quantity) of a node, from HAP_UNITROW, or None."""
    try:
        row = int(dispid.get(node, "AttributeValue", 2) or 0)
    except Exception:
        return None
    return row or None


# A field with no unit row of its own may keep its unit in another keyword of the same Input at
# the same index (live V15: HeatX VALUE in SPECUN, MHeatX VALUE\{inlet} in SPECUN\{inlet},
# Classifier PDROP_A in PDROP_UNITS); a unit given to the field itself is dropped without an
# error, so the run uses the unit that keyword holds.
_UNIT_KW = re.compile(r"(?:_UNITS|UNITS|_UNIT|UNIT|_UOM|UOM|UN)$")
_VALUE_KW = re.compile(r"(?:^|_)VAL(?:UE)?$")         # a spec's value: its unit is the spec's (SPEC -> SPECUN)


def _input_split(path: str):
    """(the Input path, the keyword, its index segments) of a field under an Input, or None."""
    head, sep, rest = str(path).rpartition("\\Input\\")
    if not sep or not rest:
        return None
    kw, *idx = rest.split("\\")
    return head + "\\Input", kw, idx


def _keywords(tree, inp: str) -> list[str]:
    node = tree.FindNode(inp)
    if node is None:
        return []
    return [str(k.Name) for k in knowledge_tools._children(node.Elements) if k is not None]


def _beside(tree, path: str, pick):
    """The keyword beside ``path``'s that ``pick(keyword, name, names)`` scores best (a score, or
    None for no match) among those that exist at the same index -- the best score first, a lower
    one only when none of the better exists there (Sep2: FLOW_BASIS beside FLOW\\MIXED\\{stream},
    FLOWBASIS beside FLOWS\\MIXED\\{stream}\\{comp}). (its path or None, the names it was chosen
    from, or that tie; the path of the best one at a shorter index -- a whole table's -- or None)."""
    split = _input_split(path)
    if split is None:
        return None, [], None
    inp, kw, idx = split
    names = _keywords(tree, inp)
    scored = [(s, n) for n in names if n != kw for s in (pick(kw, n, names),) if s is not None]
    if not scored:
        return None, [], None
    levels = sorted({s for s, _ in scored}, reverse=True)
    for level in levels:
        here = [p for s, n in scored if s == level
                for p in ("\\".join([inp, n, *idx]),) if tree.FindNode(p) is not None]
        if len(here) == 1:
            return here[0], [here[0].rpartition("\\Input\\")[2].split("\\")[0]], None
        if here:
            return None, [p.rpartition("\\Input\\")[2].split("\\")[0] for p in here], None
    best = [n for s, n in scored if s == levels[0]]
    if len(best) == 1:
        for k in range(len(idx) - 1, -1, -1):
            p = "\\".join([inp, best[0], *idx[:k]])
            if tree.FindNode(p) is not None:
                return None, best, p
    return None, best, None


def _stream_basis(tree, path: str) -> str | None:
    r"""A stream's composition basis, Input\BASIS\{substream}, for a component of its FLOW: the
    run takes a concentration basis -- and with it SOLVENT -- from there, not from the entries'
    own (live V15: MOLE-CONC entries under BASIS MOLE-FLOW stop at input, STSTRM.21). None
    for any other path."""
    split = _input_split(path)
    if split is None or split[1] != "FLOW" or len(split[2]) != 2 or not (
            "\\" + split[0].strip("\\").upper()).startswith("\\DATA\\STREAMS\\"):
        return None
    p = f"{split[0]}\\BASIS\\{split[2][0]}"
    return p if tree.FindNode(p) is not None else None


def _unit_pick(kw: str, name: str, names) -> int | None:
    m = _UNIT_KW.search(name)
    if not m or name == "Unit Set":
        return None
    stem = name[:m.start()].rstrip("_")
    if not stem:
        return None
    if kw == stem or kw.startswith(stem + "_") or (len(stem) >= 4 and kw.startswith(stem)):
        return len(stem)                                # PDROP_A -> PDROP_UNITS, HEAD_DATA -> HEAD_UNITS
    if _VALUE_KW.search(kw) and stem in names:
        return 0                                        # VALUE -> SPECUN beside SPEC
    return None


def _basis_pick(kw: str, name: str, names) -> int | None:
    """FLOW -> FLOW_BASIS, FLOWS -> FLOWBASIS, BASIS_FLOW -> FLOW_BASIS, BASIS_D -> D_BASIS; the
    keyword's own name scores above a stem of it, "_BASIS" above "BASIS"."""
    stems = [(kw, 2)]
    if kw.startswith("BASIS_"):
        stems.append((kw[6:], 1))
    if len(kw) > 2 and kw.endswith("S"):
        stems.append((kw[:-1], 1))
    return max((2 * w + (suf == "_BASIS") for s, w in stems for suf in ("_BASIS", "BASIS")
                if name == s + suf), default=None)


def _rows(els, dimension: int = 0) -> int:
    """The rows of a table along ``dimension``: Elements.RowCount, else Count. Count is every
    cell -- rows x columns on a 2-D table (RYield MOLE_YIELD: 4 after two components, 16 after
    four), so inserting there runs past the end (AE_UNKERR)."""
    try:
        return int(els.RowCount(dimension))
    except Exception:
        return int(els.Count)


def _options(node) -> list[str]:
    """A node's option list (HAP_OPTIONLIST) as strings; [] when it has none."""
    try:
        ol = node.AttributeValue(5)
        return [str(o.Value) for o in knowledge_tools._children(ol.Elements) if o is not None and o.Value]
    except Exception:
        return []


# ----------------------------------------------------------------------------
# The Aspen processes this server started
# ----------------------------------------------------------------------------
# The server only ever ends an AspenPlus.exe it started itself -- never one opened by hand,
# nor one another server or another script drives. Each document it opens is
# remembered as (pid, creation time), from Aspen's own ProcessId. A PID is reused once its
# process is gone, so before a kill the process behind that PID must still be AspenPlus.exe
# started at that time. A PID that could not be read means nothing is ever killed for it.

_ASPEN_EXE = "aspenplus.exe"
try:
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    _k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    _k32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD))
except Exception:  # pragma: no cover - not Windows
    _k32 = None


def _identity(pid: int) -> tuple[str, int] | None:
    """(image file name in lower case, creation time) of the running process ``pid``, or
    None when no process runs under that PID now (or it cannot be queried)."""
    try:
        handle = _k32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
    except Exception:                                   # no kernel32, a PID out of range
        return None
    if not handle:
        return None
    try:
        code, times = wintypes.DWORD(), [wintypes.FILETIME() for _ in range(4)]
        buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        if (not _k32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259  # STILL_ACTIVE
                or not _k32.GetProcessTimes(handle, *map(ctypes.byref, times))
                or not _k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))):
            return None
        return os.path.basename(buf.value).lower(), times[0].dwHighDateTime << 32 | times[0].dwLowDateTime
    finally:
        _k32.CloseHandle(handle)


def _own_pid(app) -> tuple[int, int] | None:
    """(pid, creation time) of the AspenPlus.exe behind a document the server just started,
    or None when that cannot be told -- then this instance is never force-ended."""
    try:
        pid = int(app.ProcessId)
    except Exception as exc:
        logger.warning("Aspen's ProcessId is unreadable (%s); this instance will never be force-ended", exc)
        return None
    ident = _identity(pid)
    if ident is None or ident[0] != _ASPEN_EXE:
        logger.warning("Process %s behind the Aspen document is %s, not a running AspenPlus.exe; "
                       "it will never be force-ended", pid, ident[0] if ident else "gone")
        return None
    return pid, ident[1]


def _running(proc: tuple[int, int]) -> bool:
    """Whether the process ``proc`` = (pid, creation time) names still runs -- that PID, still
    AspenPlus.exe, started at that time; not a later process that was given its PID."""
    return _identity(proc[0]) == (_ASPEN_EXE, proc[1])


def _taskkill(pid: int) -> None:
    """taskkill /F /T /PID: that one process and its children (apmain.exe, the CefSharp helpers)."""
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(int(pid))],
                       capture_output=True, timeout=10, check=False)
    except Exception:
        logger.debug("taskkill /PID %s failed", pid, exc_info=True)


def _end_own(procs, grace: float = 0.0, timeout: float = 12.0) -> bool:
    """End Aspen processes this server started, given as (pid, creation time); None entries are
    skipped. Waits up to ``grace`` s for them to exit on their own, then force-kills each one
    that -- checked right before -- is still that same process, again every 0.5 s until it is
    gone or ``timeout`` more seconds passed. Nothing else is killed. True when none runs."""
    procs = [p for p in procs if p]
    start = time.time()
    while True:
        left = [p for p in procs if _running(p)]
        waited = time.time() - start
        if not left or waited >= grace + timeout:
            return not left
        if waited < grace:
            pythoncom.PumpWaitingMessages()     # the exiting Aspen's calls back into this STA
            time.sleep(0.1)
            continue
        for pid, _ in left:
            _taskkill(pid)
        time.sleep(0.5)


# ----------------------------------------------------------------------------
# Crash-dialog handling during reopen
# ----------------------------------------------------------------------------
# When we Close()/reopen Aspen shortly after a run, Aspen's GUI dispatcher can
# still have a pending post-run callback (ApwnDocument.AfterRun(CxsMessage)).
# Tearing down the document under it null-derefs inside Aspen and pops a modal
# "Sorry, an error has occurred and Aspen Plus has to shut down" dialog that
# blocks until the user clicks OK. The dialog appears with *variable* latency,
# so a single taskkill at a fixed offset can miss it. The helpers below kill
# the server's own process in a verified loop (_end_own) and run a short
# background watchdog that clicks OK on the dialog whenever it shows up -- only
# on a dialog one of the server's own Aspen processes shows.

_DIALOG_CLASS = "#32770"  # window class of standard Win32 dialog boxes
# Text fragments unique to Aspen's crash dialog — used so we only ever touch
# that dialog, never a healthy Aspen window or an unrelated #32770 prompt.
_CRASH_TEXT_HINTS = ("has to shut down", "error has occurred", "has been produced")


def _dismiss_aspen_crash_dialogs(pids) -> int:
    """Click OK / close an Aspen 'has to shut down' crash dialog shown by a process in
    ``pids`` (the server's own Aspen instances); any other process's windows are left alone.

    Returns the number of dialogs dismissed. Idempotent and safe to call
    repeatedly; it only acts on windows whose text matches the crash dialog.
    """
    if not _HAS_WIN32GUI or not pids:
        return 0
    dismissed = 0

    def _on_window(hwnd, _):
        nonlocal dismissed
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.GetClassName(hwnd) != _DIALOG_CLASS:
                return True
            if win32process.GetWindowThreadProcessId(hwnd)[1] not in pids:
                return True
            if "aspen" not in (win32gui.GetWindowText(hwnd) or "").lower():
                return True

            children: list[tuple[int, str, str]] = []

            def _on_child(ch, _):
                try:
                    children.append(
                        (ch, win32gui.GetClassName(ch), win32gui.GetWindowText(ch) or "")
                    )
                except Exception:
                    pass
                return True

            win32gui.EnumChildWindows(hwnd, _on_child, None)
            blob = " ".join(t for _, _, t in children).lower()
            if not any(h in blob for h in _CRASH_TEXT_HINTS):
                return True

            # Click every OK button, then post WM_CLOSE as a fallback. The second caption
            # is the OK button's on a Chinese-locale Windows, where the dialog is localized.
            for ch, cls, txt in children:
                if cls == "Button" and txt.strip().lower().lstrip("&") in ("ok", "確定"):
                    win32gui.PostMessage(ch, win32con.BM_CLICK, 0, 0)
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            dismissed += 1
            logger.info("Dismissed Aspen crash dialog (hwnd=%s)", hwnd)
        except Exception:
            logger.debug("Crash-dialog scan failed for hwnd=%s", hwnd, exc_info=True)
        return True

    try:
        win32gui.EnumWindows(_on_window, None)
    except Exception:
        logger.debug("EnumWindows failed", exc_info=True)
    return dismissed


def _start_crash_dialog_watchdog(pids: set, max_seconds: float = 25.0, poll: float = 0.3) -> None:
    """Fire-and-forget daemon that dismisses the crash dialogs of the Aspen processes in
    ``pids`` for a while. The set is read on every pass, so a PID added after the start
    (the reopened instance) is watched too.

    The crash dialog can surface seconds after Close()/taskkill (even after a
    fresh instance has launched), so we keep watching past the reopen window.
    Reopens are spaced far apart, so at most one watchdog runs at a time;
    overlapping ones would merely be redundant (dismissal is idempotent).
    """
    if not _HAS_WIN32GUI:
        return

    def _run():
        deadline = time.time() + max_seconds
        while time.time() < deadline:
            try:
                _dismiss_aspen_crash_dialogs(pids)
            except Exception:
                logger.debug("watchdog iteration failed", exc_info=True)
            time.sleep(poll)

    try:
        threading.Thread(target=_run, daemon=True, name="aspen-crash-watchdog").start()
    except Exception:
        logger.debug("Failed to start crash-dialog watchdog", exc_info=True)


# ----------------------------------------------------------------------------
# Documents already open (the Running Object Table)
# ----------------------------------------------------------------------------
# Aspen registers every document it has open under the file's path, so another process can
# take the same document without opening the file a second time: the user's own Aspen, or a
# session another server (the standalone workbench) hands over.

ATTACH_ENV = "ASPEN_MCP_ATTACH"         # "0": never attach, always start a new Aspen


def attach_on() -> bool:
    return os.environ.get(ATTACH_ENV, "1").strip().lower() not in ("0", "false", "no", "off")


def running_documents() -> list[dict]:
    """The Aspen Plus documents open on this machine, as the Running Object Table lists them:
    [{"path", "pid", "app"}], one per document (Aspen registers each twice, the second name
    ending in "!\\"). ``path`` is the file Aspen has open -- after a crash that may be its
    own ``X$backup.bkp``. An entry that does not answer as an Aspen document is left out.
    Never raises: [] when the table cannot be read."""
    docs, seen = [], set()
    try:
        pythoncom.CoInitialize()
        rot = pythoncom.GetRunningObjectTable()
        ctx = pythoncom.CreateBindCtx(0)
        monikers = list(rot)
    except Exception:
        logger.debug("the Running Object Table could not be read", exc_info=True)
        return docs
    for mk in monikers:
        try:
            name = mk.GetDisplayName(ctx, None)
        except Exception:
            continue
        if not isinstance(name, str) or name.endswith("!\\") or \
                os.path.splitext(name)[1].lower() not in (".bkp", ".apw", ".apwz"):
            continue
        key = os.path.normcase(os.path.abspath(name))
        if key in seen:
            continue
        try:
            app = win32com.client.dynamic.Dispatch(rot.GetObject(mk).QueryInterface(pythoncom.IID_IDispatch))
            pid = int(app.ProcessId)
        except Exception:
            continue
        ident = _identity(pid)
        if ident is None or ident[0] != _ASPEN_EXE:
            continue
        seen.add(key)
        docs.append({"path": os.path.abspath(name), "pid": pid, "app": app})
    return docs


class AspenPlusManager:
    """Manages multiple Aspen Plus COM connections.

    Responsible only for session lifecycle and low-level COM tree access.
    All business logic (blocks, streams, components, etc.) lives in tools/.
    """

    def __init__(self):
        self._sessions: dict[str, object] = {}
        # Per-session file path + visibility, so we can reopen without re-passing them.
        self._session_files: dict[str, tuple[str, bool]] = {}
        # Per-session model id (tools/model_registry.py): stays with the model across a
        # Save As, a reopen and a server restart, where the file path does not.
        self._session_models: dict[str, str] = {}
        # Per-session (pid, creation time) of the AspenPlus.exe the server started for it
        # (None: unknown). The only processes the server ever force-ends.
        self._pids: dict[str, tuple[int, int] | None] = {}
        # Per-session stamp of the file as the server last loaded or wrote it -- open, reopen,
        # save: {"t", "path", "size", "mtime_ns", "marks"} (tools/restore_points.py: a model
        # unchanged since then is its file, so a restore point is a file copy).
        self._opened: dict[str, dict] = {}
        # Per-session load of its model: "<boot>-<n>", new at every open and reopen (a restore and
        # a file patch reopen too), ``boot`` this manager's own -- so what was said about one load
        # (the workbench's last run of it, kept in state.json) is told from another (load_id).
        self.boot = uuid.uuid4().hex[:8]
        self._loads: dict[str, str] = {}
        self._nload = 0
        # Optional auto-reopen every N evaluations (mitigates Aspen slowdown).
        # Set via ``set_reopen_interval``; checked by ``tools/_common_eval.evaluate_x``.
        self.reopen_every: int | None = None
        self.eval_count: int = 0
        # Per-session internal fault Aspen reported (``note_fault``): {"t", "tool"}. Its runs are
        # refused until the session is opened again (``_loaded``) or closed.
        self._faults: dict[str, dict] = {}

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
            logger.debug("Session '%s' COM object is dead, removing", name)
            del self._sessions[name]
            nodes.forget(name)
            return False

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def session_names(self) -> list[str]:
        """Names of the sessions whose Aspen instance is still alive."""
        return [name for name in list(self._sessions) if self._is_alive(name)]

    def list_sessions(self) -> str:
        """List all active sessions (and the file, when it is not named like the session)."""
        alive = self.session_names()
        if not alive:
            return "No active Aspen Plus sessions."
        lines = []
        for name in alive:
            path = self.session_file(name)
            other = path and self._session_name(path) != name
            lines.append(f"  - {name}" + (f" (file: {os.path.basename(path)})" if other else ""))
        return "Active sessions:\n" + "\n".join(lines)

    def session_file(self, session_name: str) -> str | None:
        """The model file a session is bound to (where the server saves it), or None."""
        info = self._session_files.get(session_name)
        return info[0] if info else None

    def visible(self, session_name: str) -> bool | None:
        """Whether a session was opened visible, or None for an unknown session."""
        info = self._session_files.get(session_name)
        return info[1] if info else None

    def opened(self, session_name: str) -> dict | None:
        """When and in what state the server last loaded or wrote the session's file (open,
        reopen, save): {"t", "path", "size", "mtime_ns", "marks": the journal's latest input
        and Aspen-window record times then (tools/restore_points.marks; None: no journal)}."""
        s = self._opened.get(session_name)
        return dict(s) if s else None

    def _stamp(self, session_name: str, file_path: str) -> None:
        try:
            st = os.stat(file_path)
        except OSError:
            self._opened.pop(session_name, None)
            return
        mid = self._session_models.get(session_name)
        s = journal.summary(mid) if mid and journal.enabled() else None
        self._opened[session_name] = {
            "t": journal.now(), "path": os.path.abspath(file_path), "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "marks": [s.get("last_input_t"), (s.get("ext") or {}).get("t")] if isinstance(s, dict) else None}

    def load_id(self, session_name: str) -> str | None:
        """Which load of the session's model its Aspen holds: a key new at every open and reopen,
        never one another server process gave (``boot``). None: no such session open. No COM."""
        return self._loads.get(session_name) if session_name in self._sessions else None

    def _loaded(self, session_name: str) -> None:
        self._nload += 1
        self._loads[session_name] = f"{self.boot}-{self._nload}"
        self._faults.pop(session_name, None)          # a new Aspen: the old one's fault went with it

    def note_fault(self, session_name: str | None, what, tool: str | None = None) -> bool:
        """Flag a session whose call raised or answered RPC_E_SERVERFAULT (``server_fault``):
        its runs and Reinitialize are refused (``fault``) until it is opened again; reads and
        saves go on. No session named: the only open one. True when it flagged."""
        if not server_fault(what):
            return False
        if session_name is None:
            names = list(self._sessions)
            session_name = names[0] if len(names) == 1 else None
        if session_name not in self._sessions:
            return False
        if session_name not in self._faults:
            self._faults[session_name] = {"t": time.time(), "tool": tool}
            logger.warning("Session '%s': Aspen reported an internal fault (RPC_E_SERVERFAULT, in %s); "
                           "its runs are refused until it is reopened", session_name, tool or "a call")
        return True

    def fault(self, session_name: str | None) -> str | None:
        """Why a run of the session is refused now (``note_fault``), else None. No COM."""
        return FAULT_TEXT if session_name in self._faults else None

    def model_id(self, session_name: str) -> str | None:
        """The id of the model open in a session; it survives Save As and reopen."""
        mid = self._session_models.get(session_name)
        if mid is None:
            path = self.session_file(session_name)
            if path:
                mid = self._session_models[session_name] = self._identify(path)
        return mid

    @staticmethod
    def _identify(file_path: str) -> str:
        """model_registry.identify, which already never raises; the old path hash if it did."""
        try:
            return model_registry.identify(file_path)
        except Exception:
            logger.warning("model identity lookup failed for %s", file_path, exc_info=True)
            return model_registry.legacy_id(file_path)

    def bind_file(self, session_name: str, file_path: str) -> str | None:
        """Point a session at the file its model now lives in, after a Save As the server
        made and verified. The session keeps its name and its model id; the old file goes
        into the model's history. reopen and the tools that reopen from the file follow.
        Returns the model id (None for an unknown session)."""
        visible = self.visible(session_name)
        if visible is None:
            return None
        mid = self.model_id(session_name)
        file_path = os.path.abspath(file_path)
        self._session_files[session_name] = (file_path, visible)
        model_registry.rebind(mid, file_path)
        return mid

    # ------------------------------------------------------------------
    # Saving: back up, write the file on record, confirm (tools/checkpoints.py)
    # ------------------------------------------------------------------

    def save(self, session_name: str, tool: str = "save_simulation") -> dict:
        """Write the session's model to the file on record for it -- never plain Save, which
        follows wherever Aspen's document last went (a Save As in Aspen's own window, which
        the server cannot see). The file is backed up first unless the server wrote it
        itself, and the write is confirmed by its mtime moving. Returns {"path", "model",
        "backup"}; raises SaveError with the file and the session left as they were."""
        app, path = self._saving(session_name)
        mid = self.model_id(session_name)
        backup = self._guard(mid, path, mid, tool, session_name)
        self._write(app, session_name, mid, path, tool, backup)
        self._stamp(session_name, path)
        checkpoints.after_write(mid, path, tool=tool, session=session_name, backup=backup)
        return {"path": path, "model": mid, "backup": backup}

    def save_as(self, session_name: str, file_path: str, tool: str = "save_simulation") -> dict:
        """Save the session's model to ``file_path`` and bind the session to it: same session
        name, same model id, the old file into the model's history. A file already there is
        backed up under its own model first. Same result and errors as ``save``."""
        app, own = self._saving(session_name)
        path = os.path.abspath(file_path)
        if os.path.isdir(path):
            raise SaveError(f"{path} is a folder; give the model file's full name.")
        if model_registry.key(path) == model_registry.key(own):
            return self.save(session_name, tool)
        mid = self.model_id(session_name)
        # A file there (or only its X.apw / X.def, which Aspen's save overwrites too) is
        # backed up under the model it belongs to; sidecars no model owns go under this one.
        owner = model_registry.find(path) or (self._identify(path) if os.path.exists(path) else mid)
        backup = self._guard(owner, path, mid, tool, session_name)
        self._write(app, session_name, mid, path, tool, backup)
        self.bind_file(session_name, path)
        self._stamp(session_name, path)
        checkpoints.after_write(mid, path, tool=tool, session=session_name, backup=backup)
        return {"path": path, "model": mid, "backup": backup}

    def checkpoint(self, session_name: str, reason: str = "manual", name: str | None = None,
                   tool: str | None = None) -> dict:
        """Keep the live model as a checkpoint through Export(1): the session's file and
        Aspen's document binding stay as they are. ``name`` makes it permanent."""
        app, path = self._saving(session_name)
        return checkpoints.export_checkpoint(app, self.model_id(session_name), reason=reason,
                                             tool=tool, session=session_name, name=name, orig=path)

    def _saving(self, session_name: str):
        app, path = self.get_app(session_name), self.session_file(session_name)
        if app is None or path is None:
            raise SaveError(f"No active session named '{session_name}'.")
        return app, path

    @staticmethod
    def _guard(owner: str, path: str, writer: str, tool: str, session_name: str):
        try:
            return checkpoints.guard_overwrite(owner, path, writer_id=writer, tool=tool,
                                               session=session_name)
        except Exception as exc:
            raise checkpoints.BackupError(
                f"Refused to overwrite {path}: {exc}. Nothing was written; "
                f"session '{session_name}' is unchanged.") from exc

    @staticmethod
    def _write(app, session_name: str, mid: str, path: str, tool: str, backup) -> None:
        """app.SaveAs(path) with dialogs suppressed, then check the file really changed."""
        def mtime():
            try:
                return os.stat(path).st_mtime_ns
            except OSError:
                return None

        before, err = mtime(), None
        try:
            try:
                old = app.SuppressDialogs
            except Exception:
                old = 0
            app.SuppressDialogs = 1
            try:
                app.SaveAs(path)
            finally:
                try:
                    app.SuppressDialogs = old
                except Exception:
                    pass
        except Exception as exc:
            err = f"Failed to save session '{session_name}' to {path}. Error: {exc}"
        if err is None:
            after = mtime()
            if after is None or after == before:
                err = (f"Aspen reported saving session '{session_name}', but {path} was not "
                       "written; nothing was closed or reopened.")
        if err:
            logger.error(err)
            checkpoints.record_write(mid, path, tool=tool, session=session_name, ok=False,
                                     backup=(backup or {}).get("id"), error=err)
            raise SaveError("\n".join(filter(None, (err, checkpoints.note(backup)))))

    def patch_file(self, session_name: str, edit, tool: str, keep: bool = False) -> dict:
        """For tools that change a model by editing its .bkp text: save the session to its
        file (``save``: backup, confirmed write), pass the file's bytes to ``edit`` and, when
        it returns other bytes, close the session, write them and reopen the session from the
        file -- same name, visibility and model id. ``edit`` returns None to change nothing
        (the session stays open). ``keep``: before writing the edit, a restore point of the
        model as saved (``_keep``: its file now, so a copy) -- "restore_point" in the result.
        Returns ``save``'s dict plus "changed", "reopened" and "opened" (open_with_file's
        message). Raises SaveError, the session still open, when the file is not a .bkp or
        cannot be saved or read."""
        path = self.session_file(session_name)
        if path and os.path.splitext(path)[1].lower() != ".bkp":
            raise SaveError(f"{os.path.basename(path)} is not a .bkp file, and this edits the .bkp "
                            "text. Save the model as .bkp first (save_simulation with file_path).")
        res = self.save(session_name, tool)
        path, mid, visible = res["path"], res["model"], self.visible(session_name)
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            raise SaveError(f"Saved, but cannot read {path} ({exc}); nothing was changed.") from exc
        new = edit(data)
        out = {**res, "changed": False, "reopened": False, "opened": None}
        if new is None or new == data:
            return out
        if keep:
            out["restore_point"] = self._keep(session_name, tool)
        guard = self._guard(mid, path, mid, tool, session_name)   # the save just made: no copy
        self.close(session_name)
        err = None
        try:
            with open(path, "wb") as fh:
                fh.write(new)
        except OSError as exc:
            err = f"Could not write the edited {path} ({exc}); it was put back as saved."
            try:
                with open(path, "wb") as fh:
                    fh.write(data)
            except OSError as exc2:
                err = f"Could not write the edited {path} ({exc}), nor put it back ({exc2})."
        if err is None:
            checkpoints.after_write(mid, path, tool=tool, session=session_name, backup=guard)
        else:
            checkpoints.record_write(mid, path, tool=tool, session=session_name, ok=False, error=err)
        time.sleep(2.0)                      # let the closed Aspen release the file
        opened = self.open_with_file(path, visible, session_name=session_name, model_id=mid)
        if "successfully" not in opened:
            time.sleep(5.0)
            opened = self.open_with_file(path, visible, session_name=session_name, model_id=mid)
        if err:
            raise SaveError(f"{err} Session '{session_name}': {opened}")
        return {**out, "changed": True, "reopened": "successfully" in opened, "opened": opened}

    def _keep(self, session_name: str, tool: str) -> dict:
        """patch_file(keep=True): a restore point of the model just saved (
        tools/restore_points.ensure, reason before-patch): the file is the model, so a copy --
        or the change group's own point, which already holds it. A record of its own in the
        call's change group, ahead of the call's. Never raises; ``note``: the line for the AI
        when none was made."""
        cur = recorder.current()
        group = getattr(cur, "group", None)
        try:
            with recorder.scope(actor=getattr(cur, "actor", None) or "ai", via=getattr(cur, "via", None),
                                session=session_name, model=self.model_id(session_name), group=group,
                                tool=tool) as s:
                s.manager = self
                return restore_points.ensure(self, session_name, "before-patch", group=group, tool=tool)
        except Exception as exc:
            logger.warning("restore point before %s of %s failed: %r", tool, session_name, exc)
            return {"status": "failed", "why": "failed", "error": str(exc), "note": ""}

    # ------------------------------------------------------------------
    # Putting a model back to one of its restore points, in place
    # ------------------------------------------------------------------

    def restore(self, session_name: str, checkpoint_id: str, *, before=None, tool: str = "restore",
                actor: str = "user", via: str | None = "window", group=None, act: dict | None = None,
                call: str | None = None, fields: dict | None = None) -> dict:
        """Put the session's model back to one of its restore points, in place: the user's own file takes the point's content -- backed up first, and its .apw / .def
        too when the point kept them -- and the session reopens from it under the same name,
        visibility and model id, so Aspen's Ctrl+S, ``reopen`` and ``patch_file`` go on with that
        file (a working copy elsewhere would take Ctrl+S where nobody looks).

        ``before``: called once the restore is known possible, to keep the model as it is first
        (a restore point: restore_points.ensure's dict); its id is ``before_cp``, what "undo this
        restore" restores, and a failure refuses the restore with nothing changed. None: nothing
        is kept first, and the restore cannot be undone. If the point's model will not open, the
        model is reopened from ``before_cp`` -- your file then holds it -- else from your file as
        it was: the session is never left closed unless Aspen opens neither.

        Journals one record of op ``restore`` (``target.checkpoint`` -- not a program's restore of
        its loops' values), with the file backed up, ``before_cp``, ``reopened`` and ``now`` (and
        ``fields``: more of its own, an undo's ``revert_of``; ``call``: its call id, else a new one);
        ``act``: fields of the activity "restore" (phase aspen, ``est_s``: restore_points.
        restore_estimate) the heartbeat shows while Aspen closes and loads -- 7-9 s in all for a
        typical model (the copy 1-3 ms, a new Aspen and its load ~5 s), and the load as long
        as an Export for one full of sensitivity results (127 s measured). Returns {"status":
        done | recovered | failed | refused,
        "code" (why not done), "text", "point", "before", "before_cp", "backup", "reopened",
        "now": restored | before_cp | original | closed | unchanged, "secs", "copy_ms", "open_s",
        "record"}. Never raises."""
        t0 = time.perf_counter()
        cid = str(checkpoint_id or "")
        out = {"status": "refused", "code": None, "session": session_name, "checkpoint": cid, "point": None,
               "before_cp": None, "backup": None, "reopened": False, "now": "unchanged"}

        def refuse(code, text, error=None):
            out.update(code=code, text=text, error=error)
            return out

        app, path = self.get_app(session_name), self.session_file(session_name)
        if app is None or path is None:
            return refuse("no_session", f"No active session named '{session_name}'.")
        if activity.holder(session_name) is not None:
            return refuse("busy", f"Session '{session_name}' is being changed by a program or an optimization; "
                                  "restore it when that ends.")
        if os.path.splitext(path)[1].lower() != ".bkp":
            return refuse("not_bkp", f"{os.path.basename(path)} is not a .bkp file. Save the model as .bkp first "
                                     "(save_simulation with file_path), then restore.")
        mid = self.model_id(session_name)
        cp = checkpoints.get(mid, cid) if mid else None
        if cp is None:
            return refuse("not_found", f"Restore point {cid} is not one of this model's, or no longer there.")
        out["point"] = {k: cp[k] for k in ("id", "t", "name", "reason", "state", "class", "fresh")
                        if cp.get(k) is not None}
        if not self._whole(cp):
            return refuse("damaged", f"Restore point {cid} is incomplete on disk ({checkpoints.display(cp['path'])}).")
        if before is not None:
            try:
                rp = before() or {}
            except Exception as exc:
                rp = {"status": "failed", "error": str(exc)}
            out["before"] = {k: rp[k] for k in ("status", "id", "tier", "state", "secs", "est_s", "why")
                             if rp.get(k) is not None}
            if not rp.get("id") or rp.get("status") not in ("copied", "exported", "reused", "dedup"):
                why = rp.get("error") or {"slow": "too slow"}.get(rp.get("why")) or rp.get("why") or "none was made"
                return refuse("save_failed", f"The model could not be kept first ({why}); nothing was restored.",
                              str(why))
            out["before_cp"] = rp["id"]
            if self.get_app(session_name) is None:
                return refuse("no_session", f"Session '{session_name}' closed while it was being kept.")
        visible = bool(self.visible(session_name))
        est = restore_points.restore_estimate(mid, cp["path"])
        a = activity.begin(actor, tool, session_name, phase="aspen", via=via, **(act or {}),
                           target={"checkpoint": cid, "name": cp.get("name"), "reason": cp.get("reason"), "est_s": est})
        try:
            with recorder.scope(actor=actor, via=via, session=session_name, model=mid, group=group, tool=tool,
                                call=call) as s:
                s.manager, s.file_op = self, "restore"
                self._put_back(session_name, mid, path, visible, cp, out)
                out["secs"] = round(time.perf_counter() - t0, 2)
                done = out["status"] == "done"
                tg = {"checkpoint": cid, "path": path, **{k: cp[k] for k in ("name", "t", "reason", "state", "class")
                                                        if cp.get(k) is not None}}
                s.file_extra = {**(fields or {}), "target": tg, "before_cp": out["before_cp"],
                                "reopened": out["reopened"], "now": out["now"], "fresh": cp.get("fresh"),
                                "secs": out["secs"], "writes": None,
                                "backup": (out["backup"] or {}).get("id"), "status": "changed" if done else "failed",
                                "result": None if done else out.get("error")}
                recs = s.flush(ms=(time.perf_counter() - t0) * 1e3)
                out["record"] = next((r.get("id") for r in recs if r.get("op") == "restore"), None)
        except Exception as exc:                  # (nothing above should raise; the session must not be lost)
            logger.error("restore of %s to %s failed: %r", session_name, cid, exc, exc_info=True)
            out.setdefault("error", str(exc))
            if self.get_app(session_name) is None:
                out["status"], out["now"] = "failed", "closed"
        finally:
            activity.end(a, "ok" if out["status"] == "done" else "error")
        if out["reopened"]:
            self._stamp(session_name, path)      # the file as loaded, with the journal's marks after the record
            external.WATCH.forget(session_name)  # the model is another one: what the external-change watch knew of it is not so now
            restore_points.forget(mid)
        out["text"] = self._restore_text(session_name, path, cp, out)
        return out

    @staticmethod
    def _whole(cp: dict) -> bool:
        """A checkpoint's .bkp is there and as large as when it was kept."""
        try:
            size = os.path.getsize(cp["path"])
        except (OSError, KeyError, TypeError):
            return False
        want = cp.get("size")
        return os.path.splitext(cp["path"])[1].lower() == ".bkp" and size > 0 and \
            (not isinstance(want, int) or size == want)

    def _put_back(self, session_name, mid, path, visible, cp, out) -> None:
        """``restore``'s steps 3-7: back up the file, close, copy the point in, reopen -- and if the
        model will not open, reopen from before_cp, else from the file as it was."""
        try:
            guard = checkpoints.guard_overwrite(mid, path, writer_id=mid, tool="restore", session=session_name)
        except Exception as exc:
            out.update(code="backup_failed", error=str(exc),
                       text=f"{path} could not be backed up ({exc}); nothing was restored.")
            return
        out["backup"] = {"id": guard["id"], "path": guard["path"]} if guard else None
        own = self._pids.get(session_name)
        self.close(session_name)
        if not own:
            time.sleep(2.0)                      # no PID to wait on: let the closed Aspen let go of the file
        kept: dict = {}                          # file -> its copy as it was (.restore.old), None: there was none
        t1 = time.perf_counter()
        try:
            self._swap(self._files_of(cp, path), kept)
            err = None
        except OSError as exc:
            err = f"the restore point could not be copied into {path} ({exc})"
        out["copy_ms"] = round((time.perf_counter() - t1) * 1e3, 1)
        if err is None:
            checkpoints.after_write(mid, path, tool="restore", session=session_name, backup=guard,
                                    sidecars=bool(cp.get("sidecars")))
            t2 = time.perf_counter()
            opened = self.open_with_file(path, visible, session_name=session_name, model_id=mid)
            if "successfully" not in opened:
                time.sleep(5.0)
                opened = self.open_with_file(path, visible, session_name=session_name, model_id=mid)
            out["open_s"] = round(time.perf_counter() - t2, 2)
            if "successfully" in opened:
                out.update(status="done", reopened=True, now="restored")
                self._unkeep(kept)
                return
            err = f"Aspen did not open it ({opened.split('Error:', 1)[-1].strip()[:300]})"
        out.update(code="open_failed" if "Aspen did not" in err else "swap_failed", error=err)
        logger.warning("restore of %s: %s; reopening it as it was", session_name, err)
        prior = checkpoints.get(mid, out["before_cp"]) if out["before_cp"] else None
        if prior is not None and self._whole(prior):          # the model as it was in Aspen, unsaved edits too
            try:
                self._swap(self._files_of(prior, path), kept)
                checkpoints.record_write(mid, path, tool="restore", session=session_name)
                if "successfully" in self.open_with_file(path, visible, session_name=session_name, model_id=mid):
                    out.update(status="recovered", reopened=True, now="before_cp")
                    self._unkeep(kept)
                    return
            except OSError as exc:
                logger.warning("restore of %s: before_cp not copied back (%s)", session_name, exc)
        bad = self._unswap(kept)                               # the file as it was
        if bad is None:
            checkpoints.record_write(mid, path, tool="restore", session=session_name)
        opened = self.open_with_file(path, visible, session_name=session_name, model_id=mid)
        if "successfully" not in opened:
            time.sleep(5.0)
            opened = self.open_with_file(path, visible, session_name=session_name, model_id=mid)
        if "successfully" in opened:
            out.update(status="recovered", reopened=True, now="original")
        else:
            out.update(status="failed", now="closed", error=f"{err}; reopening it failed too ({opened[:300]})"
                                                             + (f"; {bad}" if bad else ""))

    @staticmethod
    def _files_of(cp: dict, path: str) -> list:
        """(source, destination) of a checkpoint's .bkp and the .apw / .def kept with it."""
        stem = os.path.splitext(path)[0]
        return [(cp["path"], path)] + [(src, stem + ext) for ext, src in sorted((cp.get("sidecars") or {}).items())]

    @staticmethod
    def _swap(files, kept: dict) -> None:
        """Copy each source over its destination: beside it first (``.restore.tmp``, its size
        checked), what the destination held kept as ``.restore.old`` the first time (``kept``),
        then ``os.replace`` -- 1-2 ms. Raises OSError, the copies not yet in place
        removed; ``_unswap`` puts back what was replaced."""
        tmp = None
        try:
            for src, dest in files:
                tmp = dest + ".restore.tmp"
                shutil.copyfile(src, tmp)
                if os.path.getsize(tmp) != os.path.getsize(src):
                    raise OSError(f"the copy of {os.path.basename(src)} is incomplete")
                if dest not in kept:
                    kept[dest] = None
                    if os.path.exists(dest):
                        shutil.copy2(dest, dest + ".restore.old")
                        kept[dest] = dest + ".restore.old"
                os.replace(tmp, dest)
                tmp = None
        finally:
            if tmp is not None:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    @staticmethod
    def _unswap(kept: dict) -> str | None:
        """Put back what ``_swap`` replaced (the copies keep their mtime: the file is as it was;
        one that was not there is removed). None, or what could not be put back."""
        bad = []
        for dest, old in kept.items():
            try:
                if old is not None:
                    os.replace(old, dest)
                elif os.path.exists(dest):
                    os.remove(dest)
            except OSError as exc:
                bad.append(f"{os.path.basename(dest)} not put back ({exc}; it is at {old})")
        kept.clear()
        return "; ".join(bad) or None

    @staticmethod
    def _unkeep(kept: dict) -> None:
        for old in kept.values():
            if old is not None:
                try:
                    os.remove(old)
                except OSError:
                    logger.debug("restore: %s left behind", old)
        kept.clear()

    @staticmethod
    def _restore_text(session_name, path, cp, out) -> str:
        """``restore``'s result in a line (English; the workbench words its own)."""
        if out["status"] == "refused":
            return out.get("text") or "Nothing was restored."
        label = f"restore point {cp.get('id')}" + (f" \"{cp['name']}\"" if cp.get("name") else "")
        name, why = os.path.basename(path), out.get("error") or "?"
        if out["status"] == "done":
            text = f"Restored session '{session_name}' to {label}: {name} now holds it"
            text += " (the file before it was backed up first)." if out.get("backup") else "."
            return text + (f" Restore point {out['before_cp']} holds the model as it was before, so this restore "
                           "can be undone." if out.get("before_cp") else " Nothing was kept first: this restore "
                           "cannot be undone.")
        if out["status"] == "recovered":
            where = (f"the restore point kept just before ({out['before_cp']}), which {name} now holds"
                     if out["now"] == "before_cp" else f"{name} as it was")
            return f"Could not restore {label}: {why}. Session '{session_name}' was reopened from {where}."
        return (f"Could not restore {label}: {why}. Session '{session_name}' is closed; {name} is as it was "
                "-- open it again.")

    def open_with_file(self, file_path: str, visible: bool = True,
                       session_name: str | None = None, model_id: str | None = None) -> str:
        """Open Aspen Plus and load a .bkp file.

        ``visible=False`` runs Aspen hidden — noticeably faster for long
        optimizations (no flowsheet redraw / property grid refresh).
        ``session_name`` (default: the file name without extension) and
        ``model_id`` let a tool that closes and reopens a session keep the
        name and model id it had.
        """
        file_path = os.path.abspath(file_path)
        name = session_name or self._session_name(file_path)

        if self._is_alive(name):
            return f"Session '{name}' is already open."

        if not os.path.exists(file_path):
            return f"Failed: cannot find file: {file_path}"

        pythoncom.CoInitialize()

        proc = None
        try:
            aspen = win32com.client.dynamic.Dispatch("Apwn.Document")
            proc = _own_pid(aspen)
            # No dialogs.suppressed here: a document not yet shown reads SuppressDialogs 1, so
            # InitFromFile2 already runs without dialogs, and Visible = True turns them on --
            # unless the property was set, which would leave a visible session silent (V15).
            aspen.InitFromFile2(file_path)
            aspen.Visible = visible
            nodes.forget(name)
            self._sessions[name] = aspen
            self._loaded(name)
            self._session_files[name] = (file_path, visible)
            self._session_models[name] = model_id or self._identify(file_path)
            self._pids[name] = proc
            self._stamp(name, file_path)
            return (f"Aspen Plus opened successfully. Session: '{name}'"
                    + ("" if visible else " (hidden)"))
        except Exception as exc:
            logger.error("Failed to launch Aspen Plus: %s", exc, exc_info=True)
            aspen = None
            _end_own([proc], timeout=5.0)      # the instance it started is not left behind
            return f"Failed to launch Aspen Plus. Error: {exc}"

    def attach(self, file_path: str | None = None, session_name: str | None = None,
               model_id: str | None = None, pid: int | None = None) -> str | None:
        """Take a document a running Aspen already has open (``running_documents``) as a session,
        without opening the file again: the one open on ``file_path``, or the one of process
        ``pid``. The session is then this server's as one it opened is -- saved, reopened and
        closed by it. Returns open_with_file's kind of answer, or None when no running Aspen
        has it (nothing changed: open it instead)."""
        want = os.path.normcase(os.path.abspath(file_path)) if file_path else None
        doc = None
        for d in running_documents():
            if (pid is not None and d["pid"] == pid) or \
                    (pid is None and want is not None and os.path.normcase(d["path"]) == want):
                doc = d
                break
        if doc is None:
            return None
        path = os.path.abspath(file_path) if file_path else doc["path"]
        name = session_name or self._session_name(path)
        if self._is_alive(name):
            return f"Session '{name}' is already open."
        app = doc["app"]
        try:
            visible = bool(app.Visible)
        except Exception:
            visible = True
        nodes.forget(name)
        self._sessions[name] = app
        self._loaded(name)
        self._session_files[name] = (path, visible)
        self._session_models[name] = model_id or self._identify(path)
        self._pids[name] = _own_pid(app)
        self._opened.pop(name, None)       # what Aspen holds may not be what the file holds
        return (f"Aspen Plus opened successfully. Session: '{name}' (attached to the Aspen already "
                f"open on {os.path.basename(doc['path'])}, pid {doc['pid']}; no second copy was opened)")

    def release(self, session_name: str) -> dict | None:
        """Let go of a session without closing its Aspen: the document stays open for the user
        or for the server that takes it next (``attach``). Returns {"session", "path", "model",
        "visible", "pid"} to attach by, or None for an unknown session."""
        if session_name not in self._sessions:
            return None
        info = self._session_files.get(session_name)
        proc = self._pids.pop(session_name, None)
        out = {"session": session_name, "path": info[0] if info else None,
               "model": self._session_models.get(session_name),
               "visible": info[1] if info else True, "pid": proc[0] if proc else None}
        nodes.forget(session_name)
        self._sessions.pop(session_name, None)
        self._session_files.pop(session_name, None)
        self._session_models.pop(session_name, None)
        self._opened.pop(session_name, None)
        self._faults.pop(session_name, None)
        self._loads.pop(session_name, None)
        gc.collect()
        return out


    def reopen(self, session_name: str) -> str:
        """Close and reopen a session, preserving file path and visibility.

        Used to reset Aspen's internal state (history, solver cache, fortran
        scratch) that accumulates over many runs and slows things down.

        Race condition note: Aspen's Document.Close() returns before the
        underlying process fully releases its COM/license/file locks. Calling
        InitFromFile2() too soon raises a "cannot open file" warning that
        requires a manual click. To avoid this we (1) drop our COM reference,
        (2) force GC to release win32com proxies, (3) pump the COM message
        queue so Windows finishes the close handshake, and (4) sleep briefly.
        """
        info = self._session_files.get(session_name)
        if info is None:
            return f"No file info recorded for session '{session_name}'; cannot reopen."
        file_path, visible = info
        # Only this session's own Aspen is ever ended or has its dialogs clicked:
        # never one opened by hand or by another server or script.
        old = self._pids.pop(session_name, None)
        watch = {old[0]} if old else set()
        nodes.forget(session_name)            # its Tree goes with the Aspen about to close

        # Start a background watchdog that clicks OK on Aspen's "has to shut
        # down" crash dialog for the duration of the reopen. The dialog can
        # surface with variable latency, so this covers cases a single taskkill
        # would miss (see _start_crash_dialog_watchdog).
        _start_crash_dialog_watchdog(watch, max_seconds=25.0)

        # --- Step 1: let the previous run's GUI callback drain, then close ----
        if self._is_alive(session_name):
            doc = self._sessions[session_name]
            try:
                # Suppress any "save changes?" dialog from the GUI side
                try:
                    doc.SuppressDialogs = 1
                except Exception:
                    pass
                # Aspen's GUI fires AfterRun(CxsMessage) asynchronously after a
                # run; closing while it's still queued null-derefs inside Aspen
                # and pops the crash dialog. Give the GUI thread time to drain
                # the pending post-run callback before we tear the document down.
                settle = time.time() + 1.5
                while time.time() < settle:
                    pythoncom.PumpWaitingMessages()
                    time.sleep(0.1)
                doc.Close()
            except Exception:
                logger.debug("Reopen: close failed for '%s'", session_name, exc_info=True)
            # Drop our reference so win32com can release its proxy
            self._sessions.pop(session_name, None)
            del doc

        # --- Step 2: force COM proxy cleanup + pump pending messages ---------
        gc.collect()
        deadline = time.time() + 2.0  # drain pending COM events on our side
        while time.time() < deadline:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.1)

        # --- Step 2b: verified force-kill of this session's lingering Aspen --
        # Close() above only closes the document; if Aspen's internal state has
        # corrupted (common after hundreds of evals), the process stays alive
        # (often behind the crash dialog the watchdog is clicking through). Kill
        # in a loop until the process is actually gone, rather than once at a
        # fixed offset that can race the dialog's appearance.
        if old is None:
            logger.warning("Reopen '%s': the PID of its Aspen is unknown, so no process is "
                           "force-ended", session_name)
        elif not _end_own([old], timeout=12.0):
            logger.warning("Reopen '%s': its AspenPlus.exe (pid %s) is still running after "
                           "the kill loop", session_name, old[0])
        # Brief wait so Windows releases the license / file handles
        time.sleep(1.0)

        # --- Step 3: clean up stray Aspen lock/work files near .bkp ----------
        # Aspen sometimes leaves $-prefixed lock files that block re-open. Only this model's
        # own files match: the stem is exact, so model "col" never touches column2.appdf.
        try:
            base_dir = os.path.dirname(file_path)
            stem = glob.escape(os.path.splitext(os.path.basename(file_path))[0])
            for pattern in (f"~${stem}.*", f"${stem}.*", f"{stem}.apt", f"{stem}.appdf"):
                for stale in glob.glob(os.path.join(base_dir, pattern)):
                    try:
                        os.remove(stale)
                        logger.debug("Removed stale Aspen file: %s", stale)
                    except OSError:
                        pass
        except Exception:
            logger.debug("Stale-file cleanup failed", exc_info=True)

        # --- Step 4: re-open with retry loop ---------------------------------
        last_exc = None
        for attempt in range(3):
            proc = None
            try:
                aspen = win32com.client.dynamic.Dispatch("Apwn.Document")
                proc = _own_pid(aspen)
                if proc:
                    watch.add(proc[0])
                aspen.SuppressDialogs = 1  # silence "file in use" if anything lingers
                aspen.InitFromFile2(file_path)
                aspen.Visible = visible
                if visible:     # a hidden one keeps 1, as open_with_file's does: nobody could click
                    aspen.SuppressDialogs = 0
                self._sessions[session_name] = aspen
                self._loaded(session_name)
                self._pids[session_name] = proc
                self._stamp(session_name, file_path)
                return f"Session '{session_name}' reopened."
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Reopen attempt %d failed for '%s': %s; retrying after backoff",
                    attempt + 1, session_name, exc,
                )
                aspen = None
                _end_own([proc], timeout=5.0)    # the failed attempt's own instance
                time.sleep(2.0 * (attempt + 1))  # 2s, 4s, 6s backoff
        logger.error("Reopen failed for '%s' after retries: %s",
                     session_name, last_exc, exc_info=True)
        return f"Reopen failed: {last_exc}"

    def set_reopen_interval(self, interval: int | None) -> str:
        """Reopen Aspen every ``interval`` evaluations during optimization -- only the
        session's own Aspen process; other Aspen instances are never touched.

        Set to ``None`` to disable. Call with e.g. 100 to cycle every 100 runs.
        Resets the eval counter.
        """
        self.reopen_every = interval if (interval and interval > 0) else None
        self.eval_count = 0
        if self.reopen_every is None:
            return "Auto-reopen disabled."
        return f"Auto-reopen set: every {self.reopen_every} evaluations."

    # ------------------------------------------------------------------
    # Engine files (Run Settings > Engine Files): not tree nodes, so set_value cannot reach
    # them. IHAPEngine.EngineFilesSettings(IAP_ENGINEFILES) -- happ.tlb's enum, 0..9 in this
    # order. The put needs a raw DISPATCH_PROPERTYPUT Invoke: win32com has no syntax for an
    # indexed property put. The .bkp keeps them (linker options: `submitdata dlopt "<path>"`).
    # ------------------------------------------------------------------
    ENGINE_FILES = ("pp1a", "pp1b", "pp2a", "pp2b", "pp2c", "insert_lib", "cost", "stream_lib",
                    "run_def", "linker_options")

    def _engine_kind(self, kind) -> int | None:
        k = str(kind).strip().lower().replace("-", "_").replace(" ", "_")
        if k.isdigit() and int(k) < len(self.ENGINE_FILES):
            return int(k)
        return self.ENGINE_FILES.index(k) if k in self.ENGINE_FILES else None

    def get_engine_files(self, session_name: str) -> dict | str:
        """{kind: file} of every engine-files setting ("" when unset), or the error text."""
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            eng = app.Engine
            return {k: str(eng.EngineFilesSettings(i) or "") for i, k in enumerate(self.ENGINE_FILES)}
        except Exception as exc:
            logger.error("Reading engine files of '%s' failed: %s", session_name, exc, exc_info=True)
            return f"Error reading the engine files: {exc}"

    def set_engine_file(self, session_name: str, kind, file_path: str) -> str:
        """Set one engine-files setting (``kind``: a name of ENGINE_FILES or its number) to
        ``file_path`` -- an existing file, or "" to clear it -- and read it back."""
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        idx = self._engine_kind(kind)
        if idx is None:
            return f"Unknown engine file '{kind}'. Kinds: {', '.join(self.ENGINE_FILES)}."
        path = str(file_path or "").strip()
        if path:
            path = os.path.abspath(os.path.expanduser(path))
            if not os.path.isfile(path):
                return f"File not found: {path}; the {self.ENGINE_FILES[idx]} setting was not changed."
        name = self.ENGINE_FILES[idx]
        try:
            eng = app.Engine
            was = str(eng.EngineFilesSettings(idx) or "")
            ole = eng._oleobj_
            ole.Invoke(ole.GetIDsOfNames("EngineFilesSettings"), 0, pythoncom.DISPATCH_PROPERTYPUT, False,
                       idx, path)
            now = str(eng.EngineFilesSettings(idx) or "")
        except Exception as exc:
            logger.error("Setting engine file %s of '%s' failed: %s", name, session_name, exc, exc_info=True)
            return f"Error setting the {name} engine file: {exc}"
        if os.path.normcase(now) != os.path.normcase(path):
            return f"Aspen did not keep the {name} engine file: it holds {now!r} (was {was!r})."
        return (f"Engine file {name} = {now or '(none)'} (was {was or '(none)'}); "
                "the model file keeps it once saved.")

    def close(self, session_name: str = None) -> str:
        """Close an Aspen Plus session by name, or close all if no name given."""
        if session_name:
            if not self._is_alive(session_name):
                proc = self._pids.pop(session_name, None)
                self._opened.pop(session_name, None)
                self._faults.pop(session_name, None)
                if proc and _running(proc):      # its own Aspen, hung: COM dead, process not
                    _end_own([proc], timeout=5.0)
                    return (f"Session '{session_name}' no longer responded; its Aspen "
                            f"(pid {proc[0]}) was ended.")
                return f"No active session named '{session_name}'."
            return self._close_one(session_name)

        # Close all sessions
        if not self._sessions:
            return "No active Aspen Plus sessions to close."
        return "\n".join(self._close_one(name) for name in list(self._sessions))

    def _close_one(self, name: str) -> str:
        """Close a session's document, then wait for its own Aspen process to exit -- Close()
        returns before it does -- and end that process (only it) if it is still there 10 s on."""
        proc = self._pids.pop(name, None)
        self._opened.pop(name, None)
        self._faults.pop(name, None)
        nodes.forget(name)
        try:
            try:
                self._sessions[name].SuppressDialogs = 1    # a question on close would hang the call
            except Exception:
                pass
            self._sessions[name].Close()
            del self._sessions[name]
            self._session_files.pop(name, None)
            self._session_models.pop(name, None)
            msg = f"Session '{name}' closed successfully."
        except Exception as exc:
            logger.warning("Failed to close session '%s': %s", name, exc, exc_info=True)
            self._sessions.pop(name, None)
            msg = f"Failed to close session '{name}'. Error: {exc}"
        if proc and not _end_own([proc], grace=10.0, timeout=5.0):
            logger.warning("Session '%s': its AspenPlus.exe (pid %s) is still running", name, proc[0])
        return msg

    # ------------------------------------------------------------------
    # COM object access
    # ------------------------------------------------------------------

    def get_app(self, session_name: str):
        """Return the COM application object or None."""
        if not self._is_alive(session_name):
            return None
        return self._sessions[session_name]

    # ------------------------------------------------------------------
    # Generic table-row helper (used by side duties, reactions, etc.)
    # ------------------------------------------------------------------

    def ensure_node(self, session_name: str, aspen_path: str):
        """Ensure a node exists at *aspen_path*, creating missing table
        rows along the way via InsertRow/SetLabel (or Elements.Add as
        fallback).

        Returns the COM node object, or None on failure.

        Example:
            node = manager.ensure_node(session, r'\\...\\COEF\\1\\ETHYLENE')
            node.Value = -1
        """
        app = self.get_app(session_name)
        if app is None:
            return None

        # Already exists?
        node = app.Tree.FindNode(aspen_path)
        if node is not None:
            return node

        # Walk up to find the deepest existing ancestor
        parts = aspen_path.split("\\")
        existing_depth = len(parts)
        ancestor = None
        while existing_depth > 1:
            existing_depth -= 1
            ancestor = app.Tree.FindNode("\\".join(parts[:existing_depth]))
            if ancestor is not None:
                break
        if ancestor is None:
            return None

        # Create each missing level
        for depth in range(existing_depth, len(parts)):
            label = parts[depth]
            elems = ancestor.Elements

            # Check if child already exists
            child = None
            try:
                for i in range(elems.Count):
                    if elems.Item(i).Name == label:
                        child = elems.Item(i)
                        break
            except Exception:
                logger.warning("ensure_node: failed to enumerate children at depth %d for '%s'",
                               depth, "\\".join(parts[:depth+1]), exc_info=True)
                return None

            if child is None:
                child = self._try_create_child(app, elems, label, parts, depth)
                if child is None:
                    return None
            ancestor = child

        return ancestor

    @staticmethod
    def _try_create_child(app, elems, label, parts, depth):
        """Try InsertRow/SetLabel first, then Elements.Add as fallback."""
        child_path = "\\".join(parts[: depth + 1])

        # Strategy 1: InsertRow / SetLabel, at the end of dimension 0 (_rows)
        try:
            idx = _rows(elems, 0)
            elems.InsertRow(0, idx)
            elems.SetLabel(0, idx, False, label)
            child = app.Tree.FindNode(child_path)
            if child is not None:
                return child
            return elems.Item(elems.Count - 1)
        except Exception:
            logger.debug("_try_create_child: InsertRow/SetLabel failed for '%s'", child_path, exc_info=True)

        # Strategy 2: Elements.Add
        try:
            elems.Add(label)
            child = app.Tree.FindNode(child_path)
            if child is not None:
                return child
        except Exception:
            logger.debug("_try_create_child: Elements.Add failed for '%s'", child_path, exc_info=True)

        return None

    # ------------------------------------------------------------------
    # Low-level node value access (shared by block/stream/properties tools)
    # ------------------------------------------------------------------
    # A node's members go through tools/dispid.py: one Invoke by DISPID each, where
    # win32com's attribute access first binds the name on every fresh node. The node is looked
    # up by path on every call through the session's kept Tree (tools/nodes.py), never kept.

    def get_node_value(self, session_name: str, aspen_path: str) -> str:
        """Read a value from the Aspen Plus simulation tree."""
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = nodes.find(session_name, app, aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"
            value = dispid.get(node, "Value")
            if value is None:
                return f"Node '{aspen_path}' has no value."
            # Append unit string if the node has one
            unit_str = None
            try:
                unit_str = dispid.get(node, "UnitString")
            except Exception:
                logger.debug("Could not read UnitString for '%s'", aspen_path)
            self._seen(session_name, aspen_path, value, unit_str)
            if unit_str:
                return f"{value} (unit: {unit_str})"
            return str(value)
        except Exception as exc:
            nodes.forget(session_name)
            logger.error("Error reading '%s': %s", aspen_path, exc, exc_info=True)
            return f"Error reading '{aspen_path}': {exc}"

    def _seen(self, session_name: str, aspen_path: str, value, unit) -> None:
        """An input read is one the AI now relies on -- the next compare looks at it first
        (tools/external.py, ``seen``; a dict update, no COM). Never fails the read."""
        if "Input" not in aspen_path:                  # a result: nothing to watch (the usual read)
            return
        try:
            external.WATCH.seen(session_name, aspen_path, value, unit, model=self.model_id(session_name))
        except Exception:
            logger.debug("external watch: the read of '%s' not noted", aspen_path, exc_info=True)

    def set_node_value(
        self, session_name: str, aspen_path: str,
        value=None, unit: str = None, basis: str = None,
    ) -> str:
        """Write a value to the Aspen Plus simulation tree.

        Smart dispatch based on which arguments are provided:
          - value only                → node.Value = value
          - value + unit (no basis)   → SetValueAndUnit(value, unitcol, force)
          - anything with basis       → SetValueUnitAndBasis(value, unitcol, basis, force)
            (a unit with a new basis: the basis written first, the unit then looked up in
            that basis's unit row -- kg/hr is not a unit of a MOLE flow)
          - unit only / basis only    → reads current value first, then sets

        Inside a recording scope (tools/recorder.py) the write is measured on the node found
        here -- before and after -- whatever its outcome.
        """
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        rec = recorder.current()
        node = before = None
        try:
            node = nodes.find(session_name, app, aspen_path)
            if node is None:
                res, how = f"Node not found: {aspen_path}", "refused"
            else:
                if rec is not None and (value is not None or unit is not None or basis is not None):
                    before = rec.before(session_name, aspen_path, node, unit, basis)
                res, how = self._write_node(node, aspen_path, value, unit, basis, app)
        except Exception as exc:
            nodes.forget(session_name)
            res, how = self._write_error(aspen_path, value, exc), "error"
        if rec is not None:
            rec.value(self, session_name, aspen_path, node, before, (value, unit, basis), res, how)
        return res

    @staticmethod
    def _write_node(node, aspen_path: str, value, unit, basis, app=None) -> tuple[str, str]:
        """set_node_value's write on a found node: (result text, "written" | "refused").
        ``app``: for a field that keeps its unit in another keyword (``_unit_beside``).
        COM errors propagate."""
        has_value = value is not None
        has_unit = unit is not None
        has_basis = basis is not None

        if not has_value and not has_unit and not has_basis:
            return "Nothing to set -- provide at least one of: value, unit, basis.", "refused"

        # Check enterable via HAP_ENTERABLE (attr 7): 0 = not enterable
        try:
            if not dispid.get(node, "AttributeValue", 7):
                return f"Node '{aspen_path}' is not enterable.", "refused"
        except Exception:
            logger.debug("HAP_ENTERABLE not available for '%s'", aspen_path)

        # Simple case: value only, no unit/basis change
        if has_value and not has_unit and not has_basis:
            dispid.put(node, "Value", value)
            return f"Set '{aspen_path}' = {value}", "written"

        # Resolve unitcol within the node's own dimension: a unit name such as "bar"
        # sits in several dimensions (pressure, pressure drop) at columns that differ -- never
        # across all of them: a unit the node cannot hold is dropped by Aspen without an error.
        # A field that never held a value may have no unit row yet (live V15: Sep2
        # FLOW\MIXED\{stream} gets one once a value is in), so the value goes in first.
        # A basis is likewise only held once there is a value (attribute 13 empty before).
        row = _unit_row(node)
        fresh = False
        if has_value and (has_unit or has_basis) and dispid.get(node, "Value") is None and (
                row is None or (has_basis and not AspenPlusManager._basis_now(node))):
            dispid.put(node, "Value", value)
            row, fresh = _unit_row(node), True
        if has_unit and row is None:
            return AspenPlusManager._unit_beside(app, node, aspen_path, value, unit, basis, fresh)

        # Resolve the value to use
        v = float(value) if has_value else float(dispid.get(node, "Value"))
        if has_basis:
            basis = AspenPlusManager._basis_for(node, basis)
        back = None
        if has_unit and has_basis:
            row, back = AspenPlusManager._basis_first(node, v, row, basis)
        if has_unit:
            unitcol = unit_table.lookup_unit(unit, row) if row else None
            if unitcol is None:
                how = "refused" if back is None or AspenPlusManager._basis_back(node, aspen_path, back) else "written"
                near = (f" ({unit_table.dimension_name(row)}); closest: "
                        + ", ".join(unit_table.closest(unit, row))) if row else ""
                return (f"Unit '{unit}' does not fit '{aspen_path}'"
                        + (f" with basis {basis}" if has_basis else "") + near +
                        ". Use get_node_unit_info to see available units."), how
        else:
            # Keep current unit — look up unitcol from current UnitString
            try:
                current_unit = dispid.get(node, "UnitString")
                unitcol = (unit_table.lookup_unit(current_unit, row) if row else
                           unit_table.lookup_unit(current_unit)) if current_unit else 0
            except Exception:
                logger.debug("Could not read current UnitString for '%s', defaulting unitcol=0", aspen_path)
                unitcol = 0

        # Dispatch: use SetValueAndUnit when no basis, SetValueUnitAndBasis when basis involved
        if has_basis:
            dispid.call(node, "SetValueUnitAndBasis", v, unitcol, basis, False)
        else:
            dispid.call(node, "SetValueAndUnit", v, unitcol, False)

        text = AspenPlusManager._written(app, node, aspen_path, v, unit, basis)
        if has_basis and app is not None:
            text += AspenPlusManager._basis_beside(app, aspen_path, basis)
        return text, "written"

    @staticmethod
    def _basis_beside(app, aspen_path: str, basis) -> str:
        r"""The basis also written to the basis keyword beside the field at the same index, which
        the engine may follow instead of the field's own (live V15: Sep2 FLOW\MIXED\{stream}
        3000 kg/hr MASS ran as 3000 kmol/hr until FLOW_BASIS\MIXED\{stream} was MASS), or a
        stream's composition basis (``_stream_basis``). A note for the reply ("" when there is none)."""
        tree = app.Tree
        try:
            target = _beside(tree, aspen_path, _basis_pick)[0] or _stream_basis(tree, aspen_path)
        except Exception:
            logger.debug("set_node_value: no basis keyword looked up beside '%s'", aspen_path, exc_info=True)
            return ""
        if target is None:
            return ""
        kw = tree.FindNode(target)
        kind = str(basis).strip().upper()
        opts = _options(kw)
        bare = kind.partition("-")[0]
        name = next((o for o in opts if o.upper() in (kind, bare)), None) if opts else bare
        if name is None:
            return f" (not written to '{target}' beside it: it takes {', '.join(opts)})"
        try:
            if str(dispid.get(kw, "Value") or "").upper() != name.upper():
                dispid.put(kw, "Value", name)
            held = dispid.get(tree.FindNode(target), "Value")
        except Exception as exc:
            logger.warning("set_node_value: basis not written to '%s'", target, exc_info=True)
            return f" -- the basis keyword beside it, '{target}', was not written ({exc}): set it to {name} too"
        if str(held or "").upper() != name.upper():
            return f" -- the basis keyword beside it, '{target}', holds {held!r}, not {name}: set it too"
        return f"; basis keyword '{target}' = {name} as well"

    @staticmethod
    def _written(app, node, aspen_path: str, v, unit, basis) -> str:
        """The reply to a write with a unit or a basis: the unit and basis Aspen holds now, read
        back through a fresh lookup, with any that is not the one asked for named."""
        try:
            back = (app.Tree.FindNode(aspen_path) if app is not None else None) or node
        except Exception:
            back = node
        parts, off = [f"Set '{aspen_path}' = {v}"], []
        try:
            got = str(dispid.get(back, "UnitString") or "").strip()
        except Exception:
            logger.debug("Could not read back UnitString after set for '%s'", aspen_path)
            got = None
        if got:
            parts.append(got)
        if unit is not None and got is not None and got.lower() not in (
                str(unit).strip().lower(), unit_table.canonical(unit).lower()):
            off.append(f"unit {got or 'none'}, not {unit}")
        if basis is not None:
            try:
                held = str(dispid.get(back, "AttributeValue", 13) or "").strip()
            except Exception:
                held = None
            if held:
                parts.append(f"(basis: {held})")
            if held is not None and held.upper() != str(basis).strip().upper():
                off.append(f"basis {held or 'none'}, not {basis}")
        text = " ".join(parts)
        return text + (f" -- Aspen holds {' and '.join(off)}: check the field before relying on it."
                       if off else "")

    @staticmethod
    def _unit_beside(app, node, aspen_path: str, value, unit, basis, fresh) -> tuple[str, str]:
        """A unit for a field with no unit row: written to the keyword beside it that holds its
        unit (``_beside``), then the value; else refused, with what to do instead. ``fresh``:
        the value went in just now to give the field its row (none came) -- taken out again
        when refused."""
        def refuse(text):
            if fresh:
                try:
                    dispid.put(node, "Value", "")
                except Exception:
                    logger.warning("set_node_value: '%s' not emptied again", aspen_path, exc_info=True)
            return f"Unit '{unit}' does not fit '{aspen_path}', nothing written: {text}", "refused"

        tree = app.Tree if app is not None else None
        target, best, whole = _beside(tree, aspen_path, _unit_pick) if tree is not None else (None, [], None)
        if target is None:
            then = " Set that keyword to the unit, then write the value without unit=."
            if len(best) > 1:
                why = f"; several keywords beside it could hold it ({', '.join(best)}).{then}"
            elif whole:
                why = f"; its table keeps one unit for every entry, in '{whole}'.{then}"
            else:
                why = ", nor a keyword beside it. Write the value without unit=, in the unit the field uses."
            return refuse(f"it has no unit of its own{why}")
        if basis is not None:
            return refuse(f"it keeps its unit in '{target}'; write the unit and the basis "
                          "in separate calls.")
        kw = tree.FindNode(target)
        name, why = AspenPlusManager._unit_name_for(kw, unit)
        if name is None:
            return refuse(f"it keeps its unit in '{target}', which does not take it{why}.")
        dispid.put(kw, "Value", name)
        kept = dispid.get(tree.FindNode(target), "Value")
        if str(kept or "").strip().lower() != name.lower():
            return refuse(f"it keeps its unit in '{target}', which did not keep {name} "
                          f"(it holds {kept!r}).")
        where = f"the unit went to '{target}', where this field keeps it"
        if value is None:
            return f"Set the unit of '{aspen_path}' to {name} -- {where}.", "written"
        v = float(value)
        dispid.put(node, "Value", v)
        return f"Set '{aspen_path}' = {v} {name} -- {where}.", "written"

    @staticmethod
    def _unit_name_for(kw, unit) -> tuple[str | None, str]:
        """(``unit`` as the unit keyword ``kw`` takes it, "") or (None, why not): from its option
        list, else from the dimension of the unit it holds now, else from the unit table."""
        want = {str(unit).strip().lower(), unit_table.canonical(unit).lower()}
        opts = _options(kw)
        if opts:
            hit = next((o for o in opts if o.lower() in want), None)
            return (hit, "") if hit else (None, f"; it takes {', '.join(opts[:12])}")
        cur = dispid.get(kw, "Value")
        index = unit_table.get_unit_index()
        held = str(cur).strip().lower() if isinstance(cur, str) else ""
        rows = list(dict.fromkeys(e["dimension_row"] for e in index.get(held, []))) if held else []
        for r in rows:
            col = unit_table.lookup_unit(unit, r)
            if col:
                return unit_table.unit_at(r, col), ""
        if rows:
            return None, (f" (it holds {cur}, {unit_table.dimension_name(rows[0])}); closest: "
                          + ", ".join(unit_table.closest(unit, rows[0])))
        for w in want:
            for e in index.get(w, []):
                return unit_table.unit_at(e["dimension_row"], e["col"] + 1), ""
        return None, " (not a unit Aspen lists)"

    @staticmethod
    def _basis_now(node) -> str:
        try:
            return str(dispid.get(node, "AttributeValue", 13) or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _basis_for(node, basis):
        r"""``basis`` named in the node's own family: V15 calls a stream's component flows'
        basis MOLE-FLOW / MASS-FLOW (-FRAC for fractions) and TOTFLOW's MOLE / MASS, and ignores
        a name of the other family without an error (live: MASS on FLOW\MIXED\X left it MOLE-FLOW)."""
        try:
            cur = str(dispid.get(node, "AttributeValue", 13) or "").strip().upper()
        except Exception:
            return basis
        kind, _, rest = str(basis).strip().upper().partition("-")
        suffix = cur.partition("-")[2]
        if not cur or bool(suffix) == bool(rest):
            return basis
        return f"{kind}-{suffix}" if suffix else kind

    @staticmethod
    def _basis_first(node, v, row, basis):
        """A unit written with a new basis is one of that basis's units (kg/hr with MASS), and a
        node's unit row follows its basis (HAP_UNITROW: MOLE-FLOW while MOLE, MASS-FLOW once
        MASS), so the node's row now is the wrong one to look it up in. The basis is written
        first -- with the row's first unit, which every row has -- and the row read again.
        Returns (the row to look the unit up in, what puts the node back: (value, unitcol,
        basis), or None when nothing was written: the basis is already that one or unknown)."""
        try:
            cur = dispid.get(node, "AttributeValue", 13)
        except Exception:
            cur = None
        if cur in (None, "") or str(cur).strip().upper() == str(basis).strip().upper():
            return row, None
        was = dispid.get(node, "Value")
        try:
            unit_now = dispid.get(node, "UnitString")
        except Exception:
            unit_now = None
        col = (unit_table.lookup_unit(unit_now, row) if row else unit_table.lookup_unit(unit_now)) if unit_now else None
        dispid.call(node, "SetValueUnitAndBasis", v, 1, basis, False)
        return _unit_row(node), (was, col or 1, cur)

    @staticmethod
    def _basis_back(node, aspen_path: str, back) -> bool:
        """Undo _basis_first's write (the unit then did not fit the new basis either)."""
        was, col, basis = back
        try:
            dispid.call(node, "SetValueUnitAndBasis", "" if was is None else was, col, basis, False)
            return True
        except Exception:
            logger.warning("set_node_value: basis of '%s' not put back to %s", aspen_path, basis, exc_info=True)
            return False

    @staticmethod
    def _write_error(aspen_path: str, value, exc: Exception) -> str:
        """set_node_value's result for an exception, with a hint for the common COM errors.
        Call it inside the ``except`` (it logs the traceback)."""
        logger.error("Error writing '%s': %s", aspen_path, exc, exc_info=True)
        err_str = str(exc)
        # Provide actionable hints for common COM errors
        if "Invalid symbol value" in err_str:
            hint = (f" Hint: '{value}' is not a valid option for this field."
                    " Use list_node_children to see the current value,"
                    " or check documentation for valid values.")
            return f"Error writing '{aspen_path}': {exc}{hint}"
        if "AE_UNDERSPEC" in err_str:
            hint = (" Hint: this path may be a table node (e.g. FEED_STAGE\\{stream})"
                    " or the node is not user-enterable in the current state."
                    " Use list_node_children to inspect the node structure.")
            return f"Error writing '{aspen_path}': {exc}{hint}"
        if "Sum of fractions" in err_str:
            hint = " Hint: set all component fractions in a single batch call, or set the last component so the total ≤ 1."
            return f"Error writing '{aspen_path}': {exc}{hint}"
        return f"Error writing '{aspen_path}': {exc}"

    def get_node_unit_info(self, session_name: str, aspen_path: str) -> str:
        """Return unit information for a node: current unit, dimension, and available units."""
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = nodes.find(session_name, app, aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"

            try:
                unit_str = dispid.get(node, "UnitString")
            except Exception:
                logger.debug("UnitString not available for '%s'", aspen_path)
                return f"Node '{aspen_path}' has no unit information."

            if not unit_str:
                return f"Node '{aspen_path}' has no unit information."

            # The node's own dimension; the unit name alone is ambiguous (psia is listed
            # under pressure, but a pressure-drop field can report it too).
            dim_row = _unit_row(node) or unit_table.find_dimension_by_unit(unit_str)

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
            nodes.forget(session_name)
            logger.error("Error reading unit info for '%s': %s", aspen_path, exc, exc_info=True)
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
            node = nodes.find(session_name, app, aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"

            attr_num = self._resolve_attr(attribute)
            if attr_num is None:
                return f"Unknown attribute '{attribute}'. Known: {', '.join(self.HAP_ATTRS.keys())}"

            val = dispid.get(node, "AttributeValue", attr_num)
            return str(val)
        except Exception as exc:
            nodes.forget(session_name)
            logger.error("Error reading attribute %s on '%s': %s", attribute, aspen_path, exc, exc_info=True)
            return f"Error reading attribute {attribute} on '{aspen_path}': {exc}"

    def set_node_attribute(self, session_name: str, aspen_path: str, attribute: int | str, value) -> str:
        """Write an attribute on a node.

        *attribute* can be an integer (e.g. 13) or a name (e.g. 'BASIS').
        Example: set_node_attribute(session, path, 'BASIS', 'Mass-Flow')
        Inside a recording scope the attribute is measured before and after (its read-back).
        """
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        rec = recorder.current()
        node = attr_num = before = confirmed = None
        how = "refused"
        try:
            node = nodes.find(session_name, app, aspen_path)
            attr_num = None if node is None else self._resolve_attr(attribute)
            if node is None:
                res = f"Node not found: {aspen_path}"
            elif attr_num is None:
                res = f"Unknown attribute '{attribute}'. Known: {', '.join(self.HAP_ATTRS.keys())}"
            else:
                if rec is not None:
                    before = rec.attr_before(session_name, aspen_path, node, attr_num)
                # COM indexed property PUT: AttributeValue(attrnumber, force) = value
                dispid.put(node, "AttributeValue", attr_num, False, value)
                # Read back through a fresh lookup: Aspen may keep a write only on the node object
                # while it lives (live V15: an empty stream FLOW\MIXED's BASIS reverts on release)
                node = None
                node = nodes.find(session_name, app, aspen_path)
                confirmed = dispid.get(node, "AttributeValue", attr_num)
                how = "written"
                res = f"Set attribute {attribute} (#{attr_num}) on '{aspen_path}' = {confirmed}"
                if str(confirmed).strip().upper() != str(value).strip().upper():
                    res += (f" -- Aspen did not keep {value}"
                            + (": a stream's flow basis holds only once a flow is entered; set one with "
                               "set_value(..., basis=...) instead" if attr_num == 13 else "") + ".")
        except Exception as exc:
            nodes.forget(session_name)
            logger.error("Error setting attribute %s on '%s': %s", attribute, aspen_path, exc, exc_info=True)
            res, how = f"Error setting attribute {attribute} on '{aspen_path}': {exc}", "error"
        if rec is not None:
            rec.attr(self, session_name, aspen_path, node, attr_num, attribute, value, before,
                     confirmed, res, how)
        return res

    def _resolve_attr(self, attribute: int | str) -> int | None:
        """Resolve an attribute name or number to an integer."""
        if isinstance(attribute, int):
            return attribute
        upper = str(attribute).upper().replace(" ", "_").replace("-", "_")
        return self.HAP_ATTRS.get(upper)

    # ------------------------------------------------------------------
    # Generic Elements operations
    # ------------------------------------------------------------------

    def list_elements(self, session_name: str, aspen_path: str) -> str:
        """List all elements under a node: index, name, and value."""
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"
            kids = knowledge_tools._children(node.Elements)    # never Item(i): it can fault Aspen
            if not kids:
                return f"'{aspen_path}' has 0 elements."
            lines = [f"'{aspen_path}' has {len(kids)} element(s):"]
            for i, el in enumerate(kids):
                name = el.Name if el else "(null)"
                try:
                    val = el.Value
                except Exception:
                    logger.debug("Could not read value for element %d at '%s'", i, aspen_path)
                    val = None
                lines.append(f"  [{i}] {name} = {val}")
            return "\n".join(lines)
        except Exception as exc:
            err_str = str(exc)
            # Leaf nodes don't have Elements — return value instead of erroring
            if "list node on a leaf node" in err_str:
                try:
                    val = node.Value
                    return f"'{aspen_path}' is a leaf node (not a list/table). Current value: {val}"
                except Exception:
                    pass
            logger.error("Error listing elements at '%s': %s", aspen_path, exc, exc_info=True)
            return f"Error listing elements at '{aspen_path}': {exc}"

    @dialogs.quiet
    def add_element(self, session_name: str, aspen_path: str, name: str) -> str:
        """Add an element to a node's Elements collection via Elements.Add(name).

        Use 'NAME!TYPE' syntax for typed elements (e.g. 'B1!Heater', 'R1!POWERLAW').
        """
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"
            el, bang, typ = str(name).partition("!")
            if str(aspen_path).rstrip("\\").rpartition("\\")[0].upper().endswith("\\PORTS"):
                name = el.strip().upper() + bang + typ      # a stream onto a port: streams are upper-case
            else:                                           # a name that is taken, in any case: refused
                given, el = el, flowsheet_tools.aspen_name(aspen_path, el)
                name = el + bang + typ
                taken = flowsheet_tools.name_taken(app, aspen_path, el)
                if taken is not None:
                    return flowsheet_tools.taken_text("Element", given, el, taken,
                                                      f"not added at '{aspen_path}'", "remove_element")
            node.Elements.Add(name)
            return f"Added element '{name}' at '{aspen_path}'."
        except Exception as exc:
            logger.error("Error adding element '%s' at '%s': %s", name, aspen_path, exc, exc_info=True)
            return f"Error adding element '{name}' at '{aspen_path}': {exc}"

    @dialogs.quiet
    def remove_element(self, session_name: str, aspen_path: str, name: str) -> str:
        """Remove an element from a node's Elements collection by name."""
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"
            if str(aspen_path).rstrip("\\").rpartition("\\")[0].upper().endswith("\\PORTS"):
                name = str(name).strip().upper()            # named as add_element names them
            else:
                name = flowsheet_tools.aspen_name(aspen_path, name)
            node.Elements.Remove(name)
            return f"Removed element '{name}' from '{aspen_path}'."
        except Exception as exc:
            logger.error("Error removing element '%s' from '%s': %s", name, aspen_path, exc, exc_info=True)
            return f"Error removing element '{name}' from '{aspen_path}': {exc}"

    @dialogs.quiet
    def insert_row(self, session_name: str, aspen_path: str,
                   dimension: int = 0) -> str:
        """Insert a new row in a table node.

        Equivalent to: Elements.InsertRow(dimension, RowCount(dimension)).
        Returns the index of the newly inserted row -- the one set_label then takes.
        """
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"
            els = node.Elements
            idx = _rows(els, dimension)
            els.InsertRow(dimension, idx)
            return f"Inserted row at '{aspen_path}' dim={dimension} index={idx}."
        except Exception as exc:
            logger.error("Error inserting row at '%s': %s", aspen_path, exc, exc_info=True)
            return f"Error inserting row at '{aspen_path}': {exc}"

    @dialogs.quiet
    def set_label(self, session_name: str, aspen_path: str,
                  index: int, label: str, dimension: int = 0) -> str:
        """Set the label of a row in a table node.

        Equivalent to: Elements.SetLabel(dimension, index, False, label).
        """
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"
            els = node.Elements
            els.SetLabel(dimension, index, False, label)
            return f"Set label '{label}' at '{aspen_path}' dim={dimension} index={index}."
        except Exception as exc:
            logger.error("Error setting label at '%s': %s", aspen_path, exc, exc_info=True)
            return f"Error setting label at '{aspen_path}': {exc}"

    @dialogs.quiet
    def remove_row(self, session_name: str, aspen_path: str,
                   index: int, dimension: int = 0) -> str:
        """Remove a row from a table node by index.

        Equivalent to: Elements.RemoveRow(dimension, index).
        """
        app = self.get_app(session_name)
        if app is None:
            return f"No active session named '{session_name}'."
        try:
            node = app.Tree.FindNode(aspen_path)
            if node is None:
                return f"Node not found: {aspen_path}"
            els = node.Elements
            kids = knowledge_tools._children(els)    # never Item(i): it can fault Aspen
            if not 0 <= index < len(kids):
                return f"Index {index} out of range (count={len(kids)})."
            kid = kids[index]                        # its name, for the confirmation
            name = str(dispid.get(kid, "Name") or index) if kid is not None else str(index)
            els.RemoveRow(dimension, index)
            return f"Removed row [{index}] '{name}' from '{aspen_path}'."
        except Exception as exc:
            logger.error("Error removing row %d from '%s': %s", index, aspen_path, exc, exc_info=True)
            return f"Error removing row {index} from '{aspen_path}': {exc}"
