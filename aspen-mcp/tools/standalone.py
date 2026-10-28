"""The standalone workbench: ``aspen-mcp --workbench [model.bkp ...] [--hidden] [--lang zh|en]``.

The workbench with no AI client and no network: this process holds the Aspen sessions and runs
the workbench's sync loop, as the MCP server does, but serves no MCP. Everything the window does
by itself works -- values, runs, block programs, restore points, the + menu's Open Aspen model;
Ask AI requests wait for an AI client.

With no file the window opens on the tabs it had, and a model one of those tabs shows that a
running Aspen still has open -- left by an AI client that has gone, or by this workbench's last
run -- is taken back. A file a running Aspen already has open is taken as it is. It ends when
the window is closed, or when an AI client's server takes the sessions and the window over
(tools/handoff.py); Aspen is left open either way, so nothing unsaved is lost.
"""
from __future__ import annotations

import asyncio
import os
import sys


def _args(argv: list[str]) -> tuple[list[str], bool, str | None]:
    files, hidden, lang = [], False, None
    it = iter(argv)
    for a in it:
        if a == "--hidden":
            hidden = True
        elif a == "--lang":
            lang = next(it, None)
        elif not a.startswith("--"):
            files.append(os.path.abspath(a))
    return files, hidden, lang


def _left_open(wb, ws, manager) -> list[str]:
    """Sessions a model tab shows whose file a running, visible Aspen still has open: attached."""
    import aspen_manager

    if not aspen_manager.attach_on():
        return []
    shown = {t.get("session") for t in ws.state.get("tabs") or [] if t.get("kind") == "model"}
    files = {}
    for name in shown - set(manager.session_names()):
        f = ((ws.state["sessions"].get(name) or {}).get("model") or {}).get("file")
        if f:
            files[os.path.normcase(os.path.abspath(f))] = (name, f)
    if not files:
        return []
    out = []
    for d in aspen_manager.running_documents():
        hit = files.get(os.path.normcase(d["path"]))
        try:
            visible = bool(d["app"].Visible)
        except Exception:
            visible = False
        if hit is None or not visible:
            continue
        name, f = hit
        if manager.attach(f, session_name=name, pid=d["pid"]) is not None and name in manager.session_names():
            out.append(name)
    return out


async def _main(files: list[str], hidden: bool, lang: str | None) -> int:
    import server                                  # wires the manager, the journal and the brakes
    from tools import handoff, main_tools
    from tools import workbench_tools as wb

    manager = server.manager
    other = wb._owner_other()
    if other is not None:
        print(f"The workbench window is already served by another Aspen server (pid {other.get('pid')}).\n"
              "Close that window, or the AI client that started it, first.")
        return 2
    wb.STANDALONE = True

    for path in files:
        before = manager.session_names()
        res = main_tools.open_or_attach(manager, path, visible=not hidden)
        print(res)
        name = manager._session_name(path)
        if name in manager.session_names():
            wb.auto_open(manager, before, name, mode="workbench")
            wb.open_workbench_now(manager, name, lang=lang if lang in wb._LANGS else None)

    ws = wb._workspace()
    for name in _left_open(wb, ws, manager):
        print(f"Took back '{name}', still open in Aspen.")
        wb.open_workbench_now(manager, name, lang=lang if lang in wb._LANGS else None)
    if not ws.window_alive():                      # no model given, or none opened: the window alone
        ws.drain()
        if lang in wb._LANGS:
            ws.state["lang"] = lang
        ws.state["open_sessions"] = manager.session_names()
        ws.save()
        ws.beat()
        err = wb._launch(ws)
        if err:
            print(f"Cannot open the workbench window: {err}.")
            return 1
    wb._serve(ws, manager)

    print("\nServing the workbench. Close the window to stop.", flush=True)
    while ws.task is not None and not ws.task.done():
        if await handoff.serve(wb, manager, ws):
            print("An AI client took the workbench and its Aspen sessions over.")
            return 0
        await asyncio.sleep(0.4)
    print("The workbench window closed. Aspen Plus is left open: save or close it there.")
    return 0


def main(argv: list[str]) -> int:
    files, hidden, lang = _args(argv)
    try:
        code = asyncio.run(_main(files, hidden, lang))
    except KeyboardInterrupt:
        code = 130
    sys.stdout.flush()
    os._exit(code)          # no COM teardown: Aspen stays open for the user or the server that took it
