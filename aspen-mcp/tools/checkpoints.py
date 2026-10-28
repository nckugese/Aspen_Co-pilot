"""Checkpoints: a copy of a model kept before the server overwrites its file, and a log of
every file the server writes.

    ~/.aspen-mcp/checkpoints/<model id>/     (the id from tools/model_registry.py)
        meta.json      {"model", "path", "name"}: which model this is, for a human
        index.jsonl    one event per line, append only:
            checkpoint {"id", "t", "class": "auto"|"named", "reason", "tool", "session",
                        "source": "file-copy"|"export", "orig", "file", "size", "sha1",
                        "pinned", "name", "sidecars": {".apw": "c...apw", ".def": ...},
                        "secs": seconds the copy / Export took,
                        restore points (tools/restore_points.py) also: "state": "saved" (the
                        file as last opened / saved) | "live" (the model in Aspen), "group",
                        "fresh" (results in step with the inputs), "journal_t", "est_s"}
            named      {"t", "id", "name"}: that checkpoint is kept for good (class named)
            write      {"t", "tool", "session", "path", "ok", "size", "backup", "error"}
            pruned     {"t", "ids", "why"}
        (fields an older event lacks are unknown, not false)
        c20260926-101500-ab12.bkp  (+ .apw / .def: the sidecars copied with it)

Aspen's save of ``X.bkp`` also rewrites ``X.apw`` and ``X.def`` beside it (Aspen V15), so a
backup copies the ones that exist into the same checkpoint; they count toward the cap and
go with it.

``guard_overwrite`` runs before the server overwrites a file: it copies the file (and its
sidecars) unless the server wrote them itself and nobody has touched them since, and raises
BackupError when the copy fails, so the caller writes nothing. ``after_write`` records the write (registry
``written`` + a ``write`` event). ``export_checkpoint`` keeps a live model through
``Export(1, path)`` (HAPEXP_BACKUP), which leaves the session's own file alone.

Retention: the newest AUTO_KEEP ``auto`` checkpoints of each model; ``named`` ones and each
model's first copy of its original file (``pinned``) are never removed automatically; above
CAP_BYTES in total the oldest ``auto`` ones go first, never the one just made.

Pure stdlib, no COM (the app object is passed in), no I/O at import.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from tools import model_registry, recorder

logger = logging.getLogger(__name__)

ROOT = Path.home() / ".aspen-mcp"      # read at call time, so it can be pointed elsewhere
AUTO_KEEP = 20
CAP_BYTES = 1 << 30
HASH_MAX_BYTES = 64 * 1024 * 1024      # larger copies are checked by size only
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SIDECARS = (".apw", ".def")            # rewritten beside X.bkp by every Aspen save of it


class SaveError(Exception):
    """A save was refused or did not happen; the message says why, for the tool result."""


class BackupError(SaveError):
    """The file could not be backed up, so it must not be overwritten."""


# ---------------------------------------------------------------------------- storage
def _dir(model_id: str) -> Path:
    if not isinstance(model_id, str) or not _SAFE_ID.match(model_id):
        raise ValueError(f"not a model id: {model_id!r}")
    return Path(ROOT) / "checkpoints" / model_id


def _new_id(folder: Path, ext: str) -> str:
    while True:
        cid = f"c{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        if not any((folder / f"{cid}{e}").exists() for e in (ext, *SIDECARS)):
            return cid


def _sidecars(path) -> dict:
    """{ext: path} of the X.apw / X.def beside the model file X.bkp that exist now."""
    stem, ext = os.path.splitext(os.path.abspath(str(path)))
    return {e: stem + e for e in SIDECARS if e != ext.lower() and os.path.isfile(stem + e)}


def stamps(path) -> dict:
    """{ext: [size, mtime_ns]} of the model file's sidecars, as the registry keeps them."""
    out = {}
    for e, p in _sidecars(path).items():
        try:
            st = os.stat(p)
        except OSError:
            continue
        out[e] = [st.st_size, st.st_mtime_ns]
    return out


def _append(model_id: str, event: dict) -> None:
    folder = _dir(model_id)
    folder.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"v": 1, **event}, ensure_ascii=False) + "\n"
    with open(folder / "index.jsonl", "a", encoding="utf-8") as f:
        f.write(line)


def _events(model_id: str) -> list[dict]:
    try:
        raw = (_dir(model_id) / "index.jsonl").read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return []
    out = []
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            out.append(ev)
    return out


def _live(model_id: str) -> list[dict]:
    """The checkpoints still on disk, oldest first, each with its ``path`` and ``sidecars``
    ({ext: path} of the X.apw / X.def copied with it); one a ``named`` event names is class
    ``named`` (kept for good) with that name."""
    evs = _events(model_id)
    gone = {i for e in evs if e.get("kind") == "pruned" for i in e.get("ids") or []}
    names = {e.get("id"): e.get("name") for e in evs if e.get("kind") == "named"}
    folder = _dir(model_id)
    out = []
    for n, e in enumerate(evs):
        if e.get("kind") != "checkpoint" or e.get("id") in gone or not e.get("file"):
            continue
        p = folder / os.path.basename(e["file"])
        if p.is_file():
            side = {x: folder / os.path.basename(f) for x, f in (e.get("sidecars") or {}).items()}
            if e.get("id") in names:
                e = {**e, "class": "named", "name": names[e["id"]] or e.get("name")}
            out.append({**e, "path": str(p), "_order": (e.get("t") or 0, n),
                        "sidecars": {x: str(f) for x, f in side.items() if f.is_file()}})
    out.sort(key=lambda e: e["_order"])
    return out


def _meta(model_id: str, path) -> None:
    """meta.json names the model's file, so a person browsing the folder knows whose it is."""
    try:
        f = _dir(model_id) / "meta.json"
        want = {"model": model_id, "path": str(path), "name": os.path.basename(str(path))}
        try:
            if json.loads(f.read_text(encoding="utf-8")) == want:
                return
        except (OSError, ValueError):
            pass
        tmp = f.with_name(f"meta.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp")
        tmp.write_text(json.dumps(want, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, f)
    except Exception as exc:
        logger.warning("checkpoints: cannot write meta.json of %s (%s)", model_id, exc)


def _sha1(path) -> str | None:
    try:
        if os.path.getsize(path) > HASH_MAX_BYTES:
            return None
        h = hashlib.sha1()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def display(path) -> str:
    """A path as a tool result shows it: under the home folder as ``~\\...``."""
    p, home = os.path.abspath(str(path)), os.path.abspath(str(Path.home()))
    if os.path.normcase(p).startswith(os.path.normcase(home) + os.sep):
        return "~" + p[len(home):]
    return p


# ---------------------------------------------------------------------------- checkpoints
def _record(model_id, cid, dest: Path, *, klass, reason, tool, session, source, orig, name,
            pinned, sidecars=None, extra=None) -> dict:
    ev = {"kind": "checkpoint", "id": cid, "t": time.time(), "class": klass, "reason": reason,
          "tool": tool, "session": session, "source": source, "orig": str(orig) if orig else None,
          "file": dest.name, "size": dest.stat().st_size, "sha1": _sha1(dest)}
    if pinned:
        ev["pinned"] = True
    if name:
        ev["name"] = name
    if sidecars:
        ev["sidecars"] = sidecars
    for k, v in (extra or {}).items():
        if v is not None and k not in ev:
            ev[k] = v
    try:
        _append(model_id, ev)
    except Exception as exc:     # the copy is good; only the index lost a line
        logger.warning("checkpoints: %s kept but not indexed (%s)", dest, exc)
    if orig:
        _meta(model_id, orig)
    warning = prune(model_id, protect=(cid,))
    side = {x: str(dest.with_name(f)) for x, f in (sidecars or {}).items()}
    recorder.event("checkpoint", model=model_id, **{k: v for k, v in ev.items() if k not in ("kind", "t")})
    return {**ev, "path": str(dest), "sidecars": side, "warning": warning}


def backup_file(model_id: str, path, *, reason: str = "before-overwrite", tool: str | None = None,
                session: str | None = None, klass: str = "auto", name: str | None = None,
                extra: dict | None = None) -> dict:
    """Copy ``path`` and its existing sidecars (X.apw, X.def) into the model's checkpoint
    folder. Returns the checkpoint event plus ``path`` (the copy), ``sidecars`` ({ext: copy})
    and ``warning`` (None, or the over-cap notice); ``extra``: more fields for the event (a
    restore point's state, group...). Raises BackupError when a copy cannot be made and
    verified; no partial copy is left behind."""
    src = os.path.abspath(str(path))
    folder = _dir(model_id)
    ext = os.path.splitext(src)[1] or ".bkp"
    made, side = [], {}
    t0 = time.perf_counter()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        cid = _new_id(folder, ext)
        for x, s in [(ext, src), *_sidecars(src).items()]:
            dest = folder / f"{cid}{x}"
            made.append(dest)
            shutil.copy2(s, dest)
            if dest.stat().st_size != os.path.getsize(s):
                raise OSError(f"the copy of {os.path.basename(s)} is incomplete")
            if x != ext:
                side[x] = dest.name
    except Exception as exc:
        for d in made:
            try:
                d.unlink()
            except OSError:
                pass
        raise BackupError(f"could not back up {src} to {display(folder)} ({exc})") from exc
    first = klass == "auto" and reason == "before-overwrite" and not any(
        e.get("pinned") for e in _events(model_id) if e.get("kind") == "checkpoint")
    extra = {"secs": round(time.perf_counter() - t0, 3), **(extra or {})}
    return _record(model_id, cid, made[0], klass=klass, reason=reason, tool=tool, session=session,
                   source="file-copy", orig=src, name=name, pinned=first, sidecars=side, extra=extra)


def export_checkpoint(app, model_id: str, *, reason: str = "manual", tool: str | None = None,
                      session: str | None = None, name: str | None = None, orig=None,
                      extra: dict | None = None) -> dict:
    """Keep the live model: ``app.Export(1, path)`` writes it to a .bkp -- 0.02 s for a small
    model, minutes for one full of results -- without touching the session's own file or
    rebinding the document; the event's ``secs`` is how long Aspen took. ``name`` makes it a
    permanent ``named`` checkpoint; ``extra``: more event fields. Raises BackupError when
    Aspen writes nothing."""
    folder = _dir(model_id)
    dest = None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        cid = _new_id(folder, ".bkp")
        dest = folder / f"{cid}.bkp"
        try:
            old = app.SuppressDialogs
        except Exception:
            old = 0
        app.SuppressDialogs = 1
        t0 = time.perf_counter()
        try:
            app.Export(1, str(dest))
        finally:
            secs = time.perf_counter() - t0
            try:
                app.SuppressDialogs = old
            except Exception:
                pass
        if not dest.is_file() or dest.stat().st_size == 0:
            raise OSError("Aspen wrote no file")
    except Exception as exc:
        if dest is not None:
            for d in (dest, *(dest.with_suffix(x) for x in SIDECARS)):
                try:
                    d.unlink()
                except OSError:
                    pass
        raise BackupError(f"could not export a checkpoint to {display(folder)} ({exc})") from exc
    side = {x: f"{cid}{x}" for x in SIDECARS if (folder / f"{cid}{x}").is_file()}  # if Aspen wrote any
    extra = {"secs": round(secs, 3), **(extra or {})}
    return _record(model_id, cid, dest, klass="named" if name else "auto", reason=reason, tool=tool,
                   session=session, source="export", orig=orig, name=name, pinned=False, sidecars=side,
                   extra=extra)


def list_checkpoints(model_id: str) -> list[dict]:
    """The model's checkpoints on disk, newest first: each event plus ``path`` and
    ``sidecars`` ({".apw"|".def": path}; a restore puts those beside the .bkp too)."""
    try:
        live = _live(model_id)
    except ValueError:
        return []
    return [{k: v for k, v in e.items() if k != "_order"} for e in reversed(live)]


def get(model_id: str, cid: str) -> dict | None:
    """One checkpoint still on disk (as ``list_checkpoints`` has it), or None."""
    try:
        return next(({k: v for k, v in e.items() if k != "_order"} for e in _live(model_id)
                     if e.get("id") == cid), None)
    except ValueError:
        return None


def keep(model_id: str, cid: str, name: str | None = None) -> dict | None:
    """Keep a checkpoint for good (the workbench's "Keep"): a ``named`` event makes it class
    ``named``, out of the AUTO_KEEP rotation, with ``name`` if given. Returns it, or None
    when no such checkpoint is on disk."""
    if get(model_id, cid) is None:
        return None
    ev = {"kind": "named", "t": time.time(), "id": cid}
    if name:
        ev["name"] = str(name)[:120]
    _append(model_id, ev)
    return get(model_id, cid)


def last_export(model_id: str) -> dict | None:
    """The model's latest checkpoint made by Export(1) that says how long it took (``secs``,
    ``size``) -- pruned or not: the time is what matters (tools/restore_points.estimate)."""
    try:
        evs = _events(model_id)
    except ValueError:
        return None
    return next((e for e in reversed(evs) if e.get("kind") == "checkpoint" and e.get("source") == "export"
                 and isinstance(e.get("secs"), (int, float))), None)


# ---------------------------------------------------------------------------- retention
def _remove(model_id: str, doomed: list[dict], why: str) -> int:
    freed, ids = 0, []
    for e in doomed:
        kept = False
        for p in [*(e.get("sidecars") or {}).values(), e["path"]]:     # the .bkp last
            try:
                size = os.path.getsize(p)
                os.remove(p)
            except FileNotFoundError:   # another server pruned it first
                continue
            except OSError as exc:
                logger.warning("checkpoints: cannot remove %s (%s)", p, exc)
                kept = True
                break
            freed += size
        if not kept:
            ids.append(e["id"])
    if ids:
        try:
            _append(model_id, {"kind": "pruned", "t": time.time(), "ids": ids, "why": why})
        except Exception as exc:
            logger.warning("checkpoints: prune of %s not indexed (%s)", model_id, exc)
    return freed


def _rotating(e: dict) -> bool:
    return e.get("class") == "auto" and not e.get("pinned")


def prune(model_id: str | None = None, protect=()) -> str | None:
    """Keep the newest AUTO_KEEP rotating checkpoints of ``model_id``, then bring the whole
    store under CAP_BYTES by removing the oldest rotating ones of any model. Checkpoints in
    ``protect`` stay. Returns a notice when named / pinned copies alone exceed the cap."""
    try:
        if model_id is not None:
            rot = [e for e in _live(model_id) if _rotating(e)]
            extra = len(rot) - AUTO_KEEP
            if extra > 0:
                old = [e for e in rot if e["id"] not in protect][:extra]
                _remove(model_id, old, f"auto>{AUTO_KEEP}")
        base = Path(ROOT) / "checkpoints"
        if not base.is_dir():
            return None
        total = 0
        for d in base.iterdir():
            if d.is_dir():
                for f in d.iterdir():
                    if f.is_file() and f.name.startswith("c"):
                        total += f.stat().st_size
        if total <= CAP_BYTES:
            return None
        pool = []
        for d in base.iterdir():
            if d.is_dir() and _SAFE_ID.match(d.name):
                pool += [(e["_order"][0], d.name, e) for e in _live(d.name)
                         if _rotating(e) and e["id"] not in protect]
        pool.sort(key=lambda x: x[0])
        for _, mid, e in pool:
            if total <= CAP_BYTES:
                break
            total -= _remove(mid, [e], "cap")
        if total > CAP_BYTES:
            return (f"checkpoints use {total / 2**20:.0f} MB, over the {CAP_BYTES / 2**20:.0f} MB "
                    f"cap, in named or pinned copies only: remove some under {display(base)}")
    except Exception as exc:
        logger.warning("checkpoints: prune failed (%s)", exc)
    return None


# ---------------------------------------------------------------------------- write guard
def guard_overwrite(owner_id: str, path, *, writer_id: str | None = None, tool: str | None = None,
                    session: str | None = None) -> dict | None:
    """Call before the server overwrites ``path``, which belongs to model ``owner_id``.
    Backs the file and its sidecars up unless they are exactly what the server last wrote for
    that same model (then there is nothing of the user's to lose); with no file, the sidecars
    alone (Aspen overwrites a user's X.apw when it saves X.bkp). A write for another model
    (``writer_id``, e.g. a Save As over someone else's file) always backs up. Returns the
    checkpoint, or None when none was needed; raises BackupError when one failed."""
    path = os.path.abspath(str(path))
    try:
        st = os.stat(path)
    except FileNotFoundError:
        side = _sidecars(path)
        if not side:
            return None
        return backup_file(owner_id, side.get(".apw") or next(iter(side.values())),
                           reason="before-overwrite", tool=tool, session=session)
    except OSError as exc:
        raise BackupError(f"cannot read {path} ({exc})") from exc
    if writer_id in (None, owner_id):
        rec = model_registry.get(owner_id) or {}
        w = rec.get("written") or {}
        if (rec.get("path") and model_registry.key(rec["path"]) == model_registry.key(path)
                and w.get("size") == st.st_size and w.get("mtime_ns") == st.st_mtime_ns
                and (w.get("side") or {}) == stamps(path)):
            return None
    return backup_file(owner_id, path, reason="before-overwrite", tool=tool, session=session)


def record_write(model_id: str, path, *, tool: str | None = None, session: str | None = None,
                 ok: bool = True, backup: str | None = None, error: str | None = None) -> None:
    """Log that the server wrote (or failed to write) ``path`` -- in the model's index and,
    inside a recording scope, in the journal. Never raises."""
    try:
        path = os.path.abspath(str(path))
        recorder.event("write", model=model_id, path=path, ok=bool(ok), backup=backup,
                       error=error and str(error), tool=tool, session=session)
        ev = {"kind": "write", "t": time.time(), "tool": tool, "session": session, "path": path,
              "ok": bool(ok), "size": os.path.getsize(path) if os.path.exists(path) else None,
              "backup": backup}
        if error:
            ev["error"] = str(error)[:500]
        _append(model_id, ev)
        _meta(model_id, path)
    except Exception as exc:
        logger.warning("checkpoints: cannot log the write of %s (%s)", path, exc)


def after_write(model_id: str, path, *, tool: str | None = None, session: str | None = None,
                backup: dict | None = None, sidecars: bool = True) -> None:
    """The server just wrote ``path`` for this model: registry ``written`` + a write event.
    ``sidecars=False``: the write left the sidecars alone (a file copy, not an Aspen save),
    so any there now are not the server's."""
    model_registry.note_written(model_id, path, side=stamps(path) if sidecars else None)
    record_write(model_id, path, tool=tool, session=session, backup=(backup or {}).get("id"))


def note(backup: dict | None) -> str:
    """The line a tool result adds when a save made a backup ('' when it did not)."""
    if not backup:
        return ""
    line = f"(backup of the previous file: {display(backup['path'])})"
    return line + (f"\nNote: {backup['warning']}" if backup.get("warning") else "")
