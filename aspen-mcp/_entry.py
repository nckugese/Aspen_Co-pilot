"""Console-script entry point for the `aspen-mcp` command.

The modules in this project import each other by top-level name (`from aspen_manager
import ...`, `from tools import ...`), which works when `server.py` is run directly
because Python puts the script's own directory on `sys.path`. The wheel installs the same
files under an `aspen_mcp/` package directory, so this shim reproduces that condition:
put our own directory first on `sys.path`, then import `server` exactly as before.

Doing it this way keeps the wheel out of the top-level namespace (no site-packages-wide
`tools` or `docs` package) without rewriting every import in the project.

`aspen-mcp --check` prints an installation report and exits instead of serving. Its real
job is to be run once, by hand, straight after installing: under `uvx` that first run is
what downloads the interpreter and every dependency, and MCP clients give a server about
60 seconds to start -- not enough for a cold ~200 MB resolve. Doing it in a terminal turns
a silent client-side timeout into a visible progress bar.

`aspen-mcp --extract-strings` reads Aspen's own field and option names from the local
installation now, in the foreground (tools/aspen_strings.py; otherwise the workbench does it
in the background on first use).

`aspen-mcp --workbench [model.bkp ...]` opens the workbench with no AI client (tools/standalone.py).
"""
from __future__ import annotations

import os
import sys

# Import name -> which extra ships it, for the --check report.
_EXTRAS = {
    "opt": ["numpy", "scipy", "pymoo", "skopt"],
    "bo": ["torch", "botorch", "gpytorch"],
}


def _prepare_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    return here


def _check() -> int:
    import importlib.metadata
    import importlib.util

    _prepare_path()
    try:
        version = importlib.metadata.version("aspen-mcp")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"

    print(f"aspen-mcp {version}")
    print(f"python    {sys.version.split()[0]}  ({sys.executable})")

    import server  # noqa: E402  -- after _prepare_path

    print(f"docs      {server._DOCS_ROOT}")
    print(f"user data {server._USER_DATA}")

    ok = os.path.isfile(os.path.join(server._DOCS_ROOT, "aspen.md"))
    print(f"docs index{'' if ok else ' MISSING'}: {'ok' if ok else 'aspen.md not found'}")

    for extra, mods in _EXTRAS.items():
        missing = [m for m in mods if importlib.util.find_spec(m) is None]
        state = "installed" if not missing else f"absent (missing {', '.join(missing)})"
        print(f"extra [{extra}]: {state}")

    from tools import pinch_tools

    if pinch_tools._VENV_PY.exists():
        backend = "local .venv-pinch"
    elif pinch_tools._find_uv():
        backend = "uv (provisions Python 3.14 + OpenPinch on first use)"
    else:
        backend = "NONE -- install uv to enable pinch analysis"
    print(f"pinch     {backend}")
    _print_model_stores()
    _print_brakes()

    from tools import aspen_strings, gui_sheets

    print(aspen_strings.check_line())
    print(gui_sheets.check_line())

    import asyncio

    from tools import intercept

    _, classified, reason = intercept.stats(server.mcp)
    print(f"tools     {len(asyncio.run(server.mcp.list_tools()))} registered, "
          f"{classified} classified ({reason} take reason)")
    return 0 if ok else 1


def _print_model_stores() -> None:
    """Where the per-model records live (identity, backups, change journal) and how big."""
    from pathlib import Path

    from tools import checkpoints, journal, model_registry

    def mb(n: int) -> str:
        return f"{n / 1048576:.1f} MB"

    try:
        n = len(model_registry._read()["models"])
        models = f"{n} models"
    except Exception as exc:  # noqa: BLE001 -- a report line, never a failed check
        models = f"unreadable: {exc}"
    print(f"models    {model_registry._file()} ({models})")

    base = Path(checkpoints.ROOT) / "checkpoints"
    dirs, size = [], 0
    try:
        dirs = [d for d in base.iterdir() if d.is_dir()] if base.is_dir() else []
        size = sum(f.stat().st_size for d in dirs for f in d.iterdir() if f.is_file())
        state = f"{len(dirs)} models, {mb(size)}"
    except OSError as exc:
        state = f"unreadable: {exc}"
    print(f"checkpoints {base} ({state})")
    _print_restore_points(dirs, size, mb)

    use = journal.usage()
    if use:
        print(f"journal   {use['root']} ({use['models']} models, {mb(use['bytes'])}, "
              f"{'on' if use['on'] else 'off'}, {_writable(Path(use['root']))})")
    else:
        print(f"journal   {Path(journal.ROOT) / 'journal'} (unreadable)")
    _print_activity()


def _print_restore_points(dirs, size: int, mb) -> None:
    """How many restore points are on disk (automatic ones rotate, the rest stay until removed
    by hand), their size against the cap, and when an automatic one is skipped as too slow."""
    from tools import checkpoints, restore_points

    try:
        auto = kept = 0
        for d in dirs:
            if not checkpoints._SAFE_ID.match(d.name):
                continue
            for c in checkpoints.list_checkpoints(d.name):
                if c.get("class") == "named" or c.get("pinned"):
                    kept += 1
                else:
                    auto += 1
        print(f"restore   {auto + kept} restore points ({auto} automatic, the newest {checkpoints.AUTO_KEEP} "
              f"kept per model; {kept} kept for good), {mb(size)} of the {checkpoints.CAP_BYTES // 1048576} MB cap; "
              f"an automatic one is skipped when saving it would take over {restore_points.max_s():g} s "
              f"({restore_points.ENV_MAX})")
    except Exception as exc:  # noqa: BLE001 -- a report line, never a failed check
        print(f"restore   unreadable: {exc}")


def _writable(folder) -> str:
    """Whether the server can write in ``folder`` (or the nearest folder above it that exists,
    where it would create it): a temporary file made and removed there."""
    import tempfile

    at = folder
    while not at.exists() and at.parent != at:
        at = at.parent
    try:
        with tempfile.TemporaryFile(dir=at):
            pass
        return "writable"
    except OSError as exc:
        return f"NOT WRITABLE: {exc}"


def _print_activity() -> None:
    """The workbench heartbeat (who is working on which session, written while a window is
    served) and how long the AI's changing calls wait for a session's writer."""
    import json
    import time

    from tools import activity, workbench_tools

    beat = workbench_tools._ROOT / "heartbeat"
    try:
        st = beat.stat()
    except OSError:
        state = "none yet: no window served"
    else:
        age = max(0.0, time.time() - st.st_mtime)
        try:
            hb = json.loads(beat.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            hb = None
        if isinstance(hb, dict):
            pid = hb.get("pid")
            alive = "alive" if isinstance(pid, int) and workbench_tools._pid_alive(pid) else "gone"
            state = (f"last beat {age:.0f} s ago by pid {pid} ({alive}), "
                     f"{len(hb.get('act') or [])} calls in flight, {len(hb.get('holders') or {})} sessions held")
        else:
            state = f"last beat {age:.0f} s ago by a server before activity reports"
    print(f"activity  {beat} ({state}; the AI waits {activity.WRITER_WAIT_S:.0f} s for a session's writer)")


def _print_brakes() -> None:
    """The workbench's review controls on the AI: on or off, the mode the window last chose,
    how long a held call waits per client, and which server serves the window (owner.json)."""
    import json

    from tools import brake, workbench_tools

    try:
        mode = brake.DEFAULT_MODE
        try:
            st = json.loads((workbench_tools._ROOT / "state.json").read_text(encoding="utf-8"))
            mode = (st.get("brake") or {}).get("mode") or mode
        except (OSError, ValueError):
            pass
        holds = " / ".join(f"{brake.hold_s(c):g} s {n}" for c, n in
                           (("claude-code", "claude-code"), ("codex-mcp-client", "codex"), (None, "other")))
        over = " (ASPEN_MCP_HOLD_S)" if os.environ.get("ASPEN_MCP_HOLD_S") else ""
        switch = "on" if brake.enabled() else "OFF (ASPEN_MCP_BRAKE=0)"
        print(f"brake     {switch}; mode {mode}; a held call waits {holds}{over}")
    except Exception as exc:  # noqa: BLE001 -- a report line, never a failed check
        print(f"brake     unreadable: {exc}")
    try:
        o = workbench_tools._owner()
        if o is None:
            state = "none: no server serves the window"
        else:
            alive = "alive" if workbench_tools._pid_alive(o["pid"]) else "gone"
            state = f"pid {o['pid']} {alive}, running from {o.get('root') or o.get('srv') or '?'}"
        print(f"owner     {workbench_tools._ROOT / 'owner.json'} ({state})")
    except Exception as exc:  # noqa: BLE001
        print(f"owner     unreadable: {exc}")


def _extract_strings() -> int:
    """Read the field and option names from the local Aspen now, in the foreground."""
    import time

    _prepare_path()
    from tools import aspen_strings

    t0 = time.time()
    st = aspen_strings.extract(force=True)
    print(f"{aspen_strings.check_line()}  [{time.time() - t0:.1f} s]")
    return 0 if st.get("state") == "ok" else 1


def main() -> None:
    if "--check" in sys.argv[1:]:
        raise SystemExit(_check())
    if "--extract-strings" in sys.argv[1:]:
        raise SystemExit(_extract_strings())
    if "--workbench" in sys.argv[1:]:
        _prepare_path()
        from tools import standalone

        raise SystemExit(standalone.main([a for a in sys.argv[1:] if a != "--workbench"]))

    _prepare_path()
    from server import mcp  # noqa: E402  -- import only after sys.path is prepared

    mcp.run()


if __name__ == "__main__":
    main()
