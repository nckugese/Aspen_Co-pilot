"""Aspen Workbench window: a native desktop window (pywebview on Edge WebView2).

Runs in its own process, like the optimizer progress window, so the MCP server never
blocks on a GUI loop. The window and the server share nothing but a workspace folder:

  state.json    written only by the server: flowsheet, program, notes, messages, run log
  heartbeat     written by the server while it is alive and syncing: when, and what it is doing
                (tools/activity.py; a number from a server before it)
  events.jsonl  appended only by this window: the user's edits and run requests
  prefs.json    written only by this window: the page's panel sizes, drafts and one-time
                hints (WebView2 runs in private mode on a new port each launch, so the
                page's localStorage never outlives the window)

A watcher thread pushes every new state.json into the page, which is what makes an
edit made by the LLM show up in the window within a fraction of a second, and tells it
whether the heartbeat is fresh and what the heartbeat says (see _beat).

Usage: python window.py <workspace_dir> [title]
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time

import webview

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:      # tools/ sits beside workbench/ (source tree and wheel)
    sys.path.insert(1, os.path.dirname(HERE))
try:                                           # pure stdlib, no I/O at import
    from tools import aspen_labels, aspen_strings, journal
    _TOOLS_ERROR = None
except Exception as exc:  # noqa: BLE001 -- the Changes tab says why; the rest of the window works
    aspen_labels = aspen_strings = journal = None
    _TOOLS_ERROR = f"{type(exc).__name__}: {exc}"
try:                                           # the change report; stdlib too, apart so a fault stays its own
    from tools import report
    _REPORT_ERROR = None
except Exception as exc:  # noqa: BLE001
    report = None
    _REPORT_ERROR = f"{type(exc).__name__}: {exc}"
try:                                           # restore points; stdlib, apart too
    from tools import checkpoints, model_registry, restore_points
    _CP_ERROR = None
except Exception as exc:  # noqa: BLE001
    checkpoints = model_registry = restore_points = None
    _CP_ERROR = f"{type(exc).__name__}: {exc}"
try:                                           # the run-failure card; stdlib, apart too
    from tools import diagnose
    _DG_ERROR = None
except Exception as exc:  # noqa: BLE001
    diagnose = None
    _DG_ERROR = f"{type(exc).__name__}: {exc}"
try:                                           # the principle cards; stdlib, apart too
    from tools import principles
    _PRN_ERROR = None
except Exception as exc:  # noqa: BLE001
    principles = None
    _PRN_ERROR = f"{type(exc).__name__}: {exc}"
# The help cards (tools/fieldhelp.py) are imported by a warm-up thread (_warm, started in main),
# not here: their rule catalog (tools/gui_rules.py) parses ~50,000 lines at import, ~0.3 s the
# window would otherwise open later. Api.fieldhelp waits on the lock while it imports (or imports
# it itself: headless, or a card asked for before the thread got there).
_FH = {"mod": None, "error": None}
_FH_LOCK = threading.Lock()


def _fieldhelp():
    """tools.fieldhelp once imported (None, with _FH["error"], when it cannot be)."""
    with _FH_LOCK:
        if _FH["mod"] is None and _FH["error"] is None:
            try:
                from tools import fieldhelp
                _FH["mod"] = fieldhelp
            except Exception as exc:  # noqa: BLE001 -- the card says why; the rest of the window works
                _FH["error"] = f"{type(exc).__name__}: {exc}"
        return _FH["mod"]


def _warm():
    """The warm-up thread: import the help cards and read what the first card reads."""
    fh = _fieldhelp()
    try:
        if fh is not None:
            fh.warm()
    except Exception:  # noqa: BLE001 -- the first card reads it instead
        pass


POLL_S = 0.25
STALE_S = 6.0        # no heartbeat for this long = the server is gone
LAG_S = 2.5          # its loop this far behind the heartbeat = the server is held up (app-conn.js LAG_S)


def _beat(beat):
    """The heartbeat for the page (``wb.setServer``) and what tells it from the last one: all
    of it but its times, and whether the server's loop is behind (a long Aspen call holds it
    up while the beacon thread keeps writing). So the page hears of a call starting or ending
    and of the loop stalling or coming back, not of every beat. A number (a server before the
    activity heartbeat) or nothing: None."""
    if not isinstance(beat, dict):
        return None, "null"
    t, loop = beat.get("t"), beat.get("loop")
    behind = (isinstance(t, (int, float)) and isinstance(loop, (int, float)) and t - loop > LAG_S)
    rest = {k: v for k, v in beat.items() if k not in ("t", "loop")}
    return beat, json.dumps([rest, behind], sort_keys=True, default=str)


_LOGGED: set = set()


def _log_once(msg: str) -> None:
    """A line in window.log (the window's stderr), once per distinct message: a panel that fails on
    every update is written once, not once a second."""
    key = msg[:300]
    if key in _LOGGED or len(_LOGGED) >= 200:
        return
    _LOGGED.add(key)
    print(f"[workbench window {time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _push(window, call: str, what: str) -> None:
    """Hand the page one update (``call``: wb.applyState, wb.setServer or wb.setConnected) and log what
    failed in it: the page keeps each panel's error and hands them over once (wb.takeFaults). An
    exception thrown back here (pywebview re-raises the page's as JavascriptException) is logged
    and the watcher goes on: one used to end this thread, and the page then never heard of a
    state, a heartbeat or the connection again while it looked alive."""
    try:
        out = window.evaluate_js(f"{call}; window.wb && wb.takeFaults ? wb.takeFaults() : null")
    except Exception as exc:  # noqa: BLE001 -- the page threw; the next update still goes
        _log_once(f"{what}: {type(exc).__name__}: {exc}")
        return
    if isinstance(out, list):
        for fault in out:
            _log_once(f"page ({what}): {fault}")


def _read_json(path: str):
    for _ in range(5):              # the server replaces the file; retry a torn read
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, PermissionError):
            time.sleep(0.05)
    return None


class Api:
    """Methods the page calls as ``pywebview.api.<name>(...)``."""

    def __init__(self, workspace: str):
        self._ws = workspace
        self._lock = threading.Lock()
        self._window = None

    def state(self):
        return _read_json(os.path.join(self._ws, "state.json"))

    # What the page saves and opens: CSV from the Results panel (UTF-8 with a BOM, so Excel
    # reads the units), workbench files (a tab's blocks and results as JSON) and the change
    # report (Markdown, or one HTML page).
    _KINDS = {"csv": (("CSV (*.csv)", "All files (*.*)"), "utf-8-sig"),
              "awb": (("Aspen Workbench (*.awb)", "All files (*.*)"), "utf-8"),
              "md": (("Markdown (*.md)", "All files (*.*)"), "utf-8"),
              "html": (("HTML (*.html)", "All files (*.*)"), "utf-8"),
              "svg": (("SVG (*.svg)", "All files (*.*)"), "utf-8")}

    def _dialog(self, kind: str, **kw):
        dialogs = getattr(webview, "FileDialog", None)
        mode = getattr(dialogs, kind, None) or getattr(webview, f"{kind}_DIALOG")
        chosen = self._window.create_file_dialog(mode, **kw)
        if not chosen:
            return None
        return chosen if isinstance(chosen, str) else chosen[0]

    def save_file(self, name: str, text: str, kind: str = "csv"):
        """Ask where to save ``text`` and write it. Returns the path, or None when the user
        cancels."""
        types, encoding = self._KINDS.get(kind, self._KINDS["csv"])
        path = self._dialog("SAVE", save_filename=name, file_types=types)
        if not path:
            return None
        with open(path, "w", encoding=encoding, newline="") as f:
            f.write(text)
        return path

    def open_file(self, kind: str = "awb"):
        """Ask for a file to open. Returns {"path", "name", "text"}, or None when the user
        cancels."""
        types, _ = self._KINDS.get(kind, self._KINDS["awb"])
        path = self._dialog("OPEN", allow_multiple=False, file_types=types)
        if not path:
            return None
        with open(path, encoding="utf-8-sig") as f:
            return {"path": path, "name": os.path.basename(path), "text": f.read()}

    def pick_models(self):
        """Ask for Aspen model files to open (the + menu's Open Aspen model). Returns their
        paths, or None when the user cancels; the page posts them as an ``open_model`` event."""
        dialogs = getattr(webview, "FileDialog", None)
        mode = getattr(dialogs, "OPEN", None) or getattr(webview, "OPEN_DIALOG")
        chosen = self._window.create_file_dialog(
            mode, allow_multiple=True, file_types=("Aspen Plus model (*.bkp;*.apw;*.apwz)", "All files (*.*)"))
        if not chosen:
            return None
        return [chosen] if isinstance(chosen, str) else list(chosen)

    @staticmethod
    def _progress_file(path):
        """An optimizer's own progress file (opt_progress_*.json in the temp folder), else None."""
        path = os.path.abspath(str(path or ""))
        name = os.path.basename(path)
        mine = (name.startswith("opt_progress_") and name.endswith(".json")
                and os.path.dirname(path) == os.path.abspath(tempfile.gettempdir()))
        return path if mine and os.path.isfile(path) else None

    def progress(self, path):
        """A running optimization's progress, as its optimizer writes it."""
        path = self._progress_file(path)
        return _read_json(path) if path else None

    def cancel_progress(self, path):
        """Ask the optimization to stop: the marker file next to its progress file."""
        path = self._progress_file(path)
        if not path:
            return False
        open(path + ".cancel", "w").close()
        return True

    def prefs(self):
        """The page's own conveniences, {key: text}, as set_prefs last left them."""
        data = _read_json(os.path.join(self._ws, "prefs.json"))
        return data if isinstance(data, dict) else {}

    def set_prefs(self, changes: dict):
        """Merge {key: text | None} into prefs.json (None forgets the key)."""
        path = os.path.join(self._ws, "prefs.json")
        with self._lock:
            data = self.prefs()
            for key, value in dict(changes or {}).items():
                if value is None:
                    data.pop(str(key), None)
                else:
                    data[str(key)] = str(value)
            try:
                with open(path + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                os.replace(path + ".tmp", path)
            except OSError:
                return False
        return True

    def journal(self, req=None):
        """Changes tab: req {model, limit, before, after, actors, obj, types, note, note_group, group} ->
        journal.page() with loc/show; with per_path (a count): {"paths": latest_by_path(obj)}; with net:
        journal.net(after, group), before -> now. A failure is {"error": why}."""
        if journal is None:
            return {"error": _TOOLS_ERROR}
        try:
            req = dict(req or {})
            model, types = req.get("model"), req.get("types")
            if req.get("per_path"):
                paths = journal.latest_by_path(model, req.get("obj"), per=int(req["per_path"]))
                for recs in paths.values():
                    aspen_labels.decorate(recs, types)
                return {"paths": paths}
            if req.get("net"):
                out = journal.net(model, after=req.get("after"), group=req.get("group"))
                aspen_labels.decorate(out.get("inputs") or [], types)
                return out
            page = journal.page(model, limit=int(req.get("limit") or 100), before=req.get("before"),
                                after=req.get("after"), actors=req.get("actors"), obj=req.get("obj"),
                                note=req.get("note"), group=req.get("group"), note_group=req.get("note_group"))
            aspen_labels.decorate(page["records"], types)
            return page
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    def report(self, req=None):
        """Change report: req {model, span ("all" | "today" | "since" | "group"), fmt ("md" |
        "html"), lang, types, coverage, after (span since: the seen mark), group (span group)} ->
        report.build(): {"name", "text", "n", "more", "tally"}; the page then calls
        save_file(name, text, fmt). ``types`` and ``coverage`` default to state.json's (the
        flowsheet of a session on that model; the catalog's). A failure is {"error": why}."""
        if report is None:
            return {"error": _REPORT_ERROR}
        try:
            req = dict(req or {})
            model, types, cov = req.get("model"), req.get("types"), req.get("coverage")
            if not types or not isinstance(cov, dict):
                st = self.state() or {}
                if not isinstance(cov, dict):
                    cov = (st.get("catalog") or {}).get("coverage")
                if not types:
                    types = {str(b.get("name")): b.get("type")
                             for s in (st.get("sessions") or {}).values() if isinstance(s, dict)
                             for fs in [s.get("flowsheet") or {}] if fs.get("model") == model
                             for b in fs.get("blocks") or [] if isinstance(b, dict) and b.get("name")}
            return report.build(model, span=req.get("span") or "all", fmt=req.get("fmt") or "md",
                                lang=req.get("lang") or "en", types=types, coverage=cov,
                                after=req.get("after"), group=req.get("group"))
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    # a restore point's fields the page gets: when, what for, its name, how kept, how big
    _CP_FIELDS = ("id", "t", "class", "name", "reason", "state", "source", "tool", "size", "secs", "fresh",
                  "group", "pinned", "journal_t")

    def checkpoints(self, req=None):
        """Restore points of a model, read from its checkpoint index -- so the list
        shows while Aspen calculates: req {model, path?} -> {"points": newest first, each
        {id, t, class (auto | named), name, reason, state (saved | live), source, tool, size (with
        its .apw / .def), secs, fresh, group, pinned, journal_t, kept (never removed
        automatically), restore_s (about how long restoring it in place takes, from what it holds:
        restore_points.restore_estimate)}, "n", "bytes", "auto_keep", "cap_bytes", "estimate":
        restore_points.estimate {"s", "how", "size", "rows2"} of saving one now (the "save a
        restore point" button's "about 3 s"), "restore_s": restoring one, from the live model's
        estimate (a point's own comes first)}. ``path``: the model's file (default: the
        registry's). A failure is {"error": why}."""
        if checkpoints is None:
            return {"error": _CP_ERROR}
        try:
            req = dict(req or {})
            model = req.get("model")
            points, total = [], 0
            for c in checkpoints.list_checkpoints(model) if model else ():
                size = 0
                for p in (c.get("path"), *(c.get("sidecars") or {}).values()):
                    try:
                        size += os.path.getsize(p)
                    except (OSError, TypeError):
                        pass
                total += size
                e = {k: c[k] for k in self._CP_FIELDS if c.get(k) is not None}
                e["size"], e["kept"] = size or c.get("size"), c.get("class") == "named" or bool(c.get("pinned"))
                try:                                  # restoring this one: its own results, not the live model's
                    e["restore_s"] = restore_points.restore_estimate(model, c.get("path"))
                except Exception:  # noqa: BLE001 -- the box then gives the model's
                    e["restore_s"] = None
                points.append(e)
            path = req.get("path") or ((model_registry.get(model) or {}).get("path") if model else None)
            est = restore_points.estimate(model, path) if model else {"s": None, "how": None}
            return {"points": points, "n": len(points), "bytes": total, "auto_keep": checkpoints.AUTO_KEEP,
                    "cap_bytes": checkpoints.CAP_BYTES, "estimate": est,
                    "restore_s": restore_points.RESTORE_BASE_S + est["s"] if est.get("s") is not None else None}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    def labels(self, req=None):
        """{path: loc} for req {paths, types}."""
        if aspen_labels is None:
            return {"error": _TOOLS_ERROR}
        req = dict(req or {})
        return aspen_labels.labels(list(req.get("paths") or [])[:500], req.get("types"))

    def fieldhelp(self, req=None):
        """A field's help card (tools/fieldhelp.card): req {path, type | types, row, info, prompt,
        now, record, stmt, lang} -> the card; {options: "all"} -> every option; {ref} -> a docs
        passage. Reads files only, never Aspen, so it answers while Aspen calculates; a card with
        ``need_prompt`` wants the event field_info posted, then this again with the tab's
        ``field_info`` as ``info``. A block path with no type takes it from state.json's
        flowsheet. A failure is {"error": why}."""
        fh = _fieldhelp()
        if fh is None:
            return {"error": _FH["error"]}
        try:
            req = dict(req or {})
            path = str(req.get("path") or "")
            segs = [s for s in path.split("\\") if s]
            if not req.get("type") and not isinstance(req.get("types"), dict) and len(segs) > 2 and segs[1] == "Blocks":
                req["type"] = next((b.get("type") for s in ((self.state() or {}).get("sessions") or {}).values()
                                    if isinstance(s, dict) for b in (s.get("flowsheet") or {}).get("blocks") or []
                                    if isinstance(b, dict) and b.get("name") == segs[2]), None)
            return fh.card(req)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    help = fieldhelp          # the same, by its short name

    def diagnosis(self, req=None):
        """Why a run failed (tools/diagnose.session_card): req {session | model, run, lang,
        status, run_msgs, pm, sim, missing, flowsheet} -> the card. What the
        page does not give comes from state.json's session (by name, else the one holding
        ``model``); ``run`` (a run record id; default the one the session's ``diag`` is about)
        other than the session's latest is read from the journal and carded by its own blocks and
        messages. Reads files only (state.json, the journal, the error histories), never Aspen,
        so it answers while Aspen calculates. A failure is {"error": why}."""
        if diagnose is None:
            return {"error": _DG_ERROR}
        try:
            req = dict(req or {})
            sessions = (self.state() or {}).get("sessions") or {}
            sess = sessions.get(req.get("session")) if req.get("session") else None
            if not isinstance(sess, dict):
                sess = next((s for s in sessions.values() if isinstance(s, dict) and req.get("model")
                             and (s.get("model") or {}).get("id") == req["model"]), None) or {}
            sess = dict(sess, **{k: req[k] for k in ("status", "run_msgs", "pm", "sim", "missing", "flowsheet")
                                 if req.get(k) is not None})
            model = req.get("model") or (sess.get("model") or {}).get("id")
            d = sess.get("diag") if isinstance(sess.get("diag"), dict) else {}
            latest = (d.get("run") or {}).get("id")
            rid = req.get("run") or latest
            rec = None
            if rid and rid != latest and model and journal is not None:
                rec = journal.find(model, rid)
            if rec is None and rid:
                rec = dict(d.get("run") or {}, id=rid) if rid == latest else {"id": rid}
            c = diagnose.session_card(sess, rec, req.get("lang") or d.get("lang") or "en", model,
                                      latest=not rid or rid == latest)
            if rid == latest and d.get("fixed"):
                c["fixed"] = d["fixed"]
            return c
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    def principle(self, key=None):
        """A principle card (tools/principles.card): {key, title {en, zh}, idea, eq,
        sym {en, zh} each, related [keys], ref}. ``key`` must be lower-case letters, digits and _
        and listed in docs/principles/index.md -- no other name reaches a file. Reads the
        package's files only (cached), never Aspen. A key that is not one: {"error": "unknown"}."""
        if principles is None:
            return {"error": _PRN_ERROR}
        try:
            c = principles.card(key if isinstance(key, str) else None)
            return c if c is not None else {"error": "unknown"}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    def strings(self):
        """Extraction state (state/aspen/why) + labels_mtime / learned_mtime; never starts an extraction."""
        if aspen_strings is None:
            return {"state": "none", "error": _TOOLS_ERROR}
        try:
            return {**aspen_strings.status(), **aspen_labels.sources()}
        except Exception as exc:  # noqa: BLE001
            return {"state": "failed", "error": f"{type(exc).__name__}: {exc}"}

    def post(self, event: dict):
        event = dict(event or {})
        event["t"] = time.time()
        line = json.dumps(event, ensure_ascii=False)
        with self._lock:
            with open(os.path.join(self._ws, "events.jsonl"), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return True


def _watch(window, workspace: str, stop: threading.Event):
    state_path = os.path.join(workspace, "state.json")
    beat_path = os.path.join(workspace, "heartbeat")
    last_mtime, last_alive = None, None
    beat_mtime, beat_sig = None, None
    while not stop.is_set():
        try:
            mtime = os.stat(state_path).st_mtime_ns
        except OSError:             # (gone, or held for a moment while the server replaces it)
            mtime = None
        if mtime is not None and mtime != last_mtime:
            state = _read_json(state_path)
            if state is not None:
                last_mtime = mtime
                payload = json.dumps(json.dumps(state, ensure_ascii=False))
                _push(window, f"window.wb && wb.applyState(JSON.parse({payload}))", "state")
        try:
            st = os.stat(beat_path)
            alive, bm = (time.time() - st.st_mtime) < STALE_S, st.st_mtime_ns
        except OSError:
            alive, bm = False, None
        if bm != beat_mtime:        # read only a new heartbeat: about once a second
            content = _read_json(beat_path) if bm is not None else None
            if bm is None or content is not None:         # (a read that failed: again next time)
                beat_mtime = bm
                content, sig = _beat(content)
                if sig != beat_sig:
                    beat_sig = sig
                    payload = json.dumps(json.dumps(content, ensure_ascii=False, default=str))
                    _push(window, f"window.wb && wb.setServer && wb.setServer(JSON.parse({payload}))", "heartbeat")
        if alive != last_alive:
            last_alive = alive
            _push(window, f"window.wb && wb.setConnected({'true' if alive else 'false'})", "connection")
        stop.wait(POLL_S)


def main() -> None:
    workspace = os.path.abspath(sys.argv[1])
    title = sys.argv[2] if len(sys.argv) > 2 else "Aspen Workbench"
    threading.Thread(target=_warm, name="fieldhelp-warm", daemon=True).start()
    api = Api(workspace)
    window = webview.create_window(
        title, url=os.path.join(HERE, "static", "index.html"), js_api=api,
        width=1480, height=900, min_size=(1000, 640),
    )
    api._window = window
    stop = threading.Event()

    def on_closing():
        stop.set()
        api.post({"type": "closed"})

    window.events.closing += on_closing
    pid_file = os.path.join(workspace, "window.pid")
    with open(pid_file, "w", encoding="utf-8") as f:      # lets a restarted server find us
        f.write(str(os.getpid()))
    try:
        webview.start(lambda: _watch(window, workspace, stop), debug="--debug" in sys.argv)
    finally:
        try:
            os.remove(pid_file)
        except OSError:
            pass


if __name__ == "__main__":
    main()
