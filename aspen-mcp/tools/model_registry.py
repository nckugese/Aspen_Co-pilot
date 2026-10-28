"""Model identity that survives Save As, a reopen, a server restart and a moved file.

A model's id used to be a hash of its file's path, so a Save As, a rename or a copy turned
it into another model and everything keyed on the id (the workbench's manual layout) was
lost. The id now lives in a sidecar registry, ``~/.aspen-mcp/models.json``; nothing is
written into the user's model::

    {"v": 1, "models": {"m3f2a9c01be": {
        "path": "C:\\...\\column.bkp",     # the file the model is bound to (None: lost)
        "history": ["C:\\...\\column-old.bkp"], # earlier paths, newest first, at most 20
        "parent": null,                     # the model this one was copied from
        "created": 1790000000.0, "seen": 1790000500.0,
        "sha1": "...", "size": 5123456,     # content when the server last opened or wrote it
        "written": {"size": 5123456, "mtime_ns": ...,      # the server's last write
                    "side": {".apw": [size, mtime_ns]}}}}}   # (+ files written with it)

``identify(path)`` answers, in order: the model bound to that path; a model with the same
content whose file is gone (a move or rename: rebound, same id) or still there (a copy: a
new id with ``parent`` set); a new model. ``fresh(path)`` skips the content match for a
file the server has just created. A path seen for the first time gets
``legacy_id(path)``, the old path-hash formula, so ids stored before the registry existed
still match. A Save As in Aspen's own window is invisible to the server: the new file is a
new model unless its content still matches.

Nothing here raises. When the registry cannot be locked, read or written, the id falls back
to the path lookup or the old formula and the failure is logged. Two servers may share the
file: each change re-reads it under ``models.json.lock`` and replaces it atomically.

Pure stdlib, no COM, no I/O at import.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import logging
import os
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path.home() / ".aspen-mcp"      # read at call time, so it can be pointed elsewhere
HISTORY_MAX = 20
HASH_MAX_BYTES = 64 * 1024 * 1024      # larger files are matched by path only
LOCK_WAIT_S = 1.0
LOCK_STALE_S = 10.0                    # a lock this old belongs to a process that died


class RegistryUnavailable(Exception):
    """The registry could not be locked, read or written."""


# ---------------------------------------------------------------------------- paths
def _long(path) -> str:
    """Absolute path with 8.3 short components expanded (the file must exist for that)."""
    p = os.path.abspath(os.fspath(path))
    if os.name == "nt":
        try:
            fn = ctypes.windll.kernel32.GetLongPathNameW
            n = fn(p, None, 0)
            if n:
                buf = ctypes.create_unicode_buffer(n)
                if fn(p, buf, n):
                    return buf.value
        except Exception:
            pass
    return p


def key(path) -> str:
    """The form two paths are compared in: absolute, long names, case and slashes folded."""
    return os.path.normcase(_long(path))


def _id_of_key(k: str) -> str:
    return "m" + hashlib.sha1(k.encode("utf-8")).hexdigest()[:10]


def legacy_id(path) -> str:
    """The old path-hash id: what a path gets the first time it is seen, and the fallback."""
    return _id_of_key(key(path))


def _same(a, b) -> bool:
    return bool(a) and bool(b) and os.path.normcase(a) == os.path.normcase(b)


def _exists(p) -> bool:
    return bool(p) and os.path.exists(p)


def _fingerprint(path) -> tuple[str | None, int | None]:
    """(sha1, size) of a file; sha1 is None above HASH_MAX_BYTES or when unreadable."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None, None
    if size > HASH_MAX_BYTES:
        return None, size
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None, size
    return h.hexdigest(), size


# ---------------------------------------------------------------------------- storage
def _file() -> Path:
    return Path(ROOT) / "models.json"


class _Lock:
    """``models.json.lock`` created with O_EXCL; waits up to LOCK_WAIT_S, breaks a stale one."""

    def __init__(self):
        self.path = str(_file()) + ".lock"
        self.fd = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        deadline = time.monotonic() + LOCK_WAIT_S
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(self.fd, str(os.getpid()).encode())   # who holds it, for a human
                except OSError:
                    pass
                return self
            except FileExistsError:
                try:
                    if time.time() - os.stat(self.path).st_mtime > LOCK_STALE_S:
                        os.remove(self.path)
                        logger.warning("model registry: removed a stale lock %s", self.path)
                        continue
                except OSError:
                    pass          # released meanwhile, or being deleted: try again
            except PermissionError:
                pass              # Windows: the previous holder's lock is still being deleted
            if time.monotonic() >= deadline:
                raise RegistryUnavailable(f"{self.path} is held by another process")
            time.sleep(0.01)

    def __exit__(self, *exc):
        try:
            os.close(self.fd)
        finally:
            try:
                os.remove(self.path)
            except OSError:
                pass


def _read(repair: bool = False) -> dict:
    """The registry; an empty one when the file is missing or is not a registry. With
    ``repair`` (under the lock) a damaged file is kept aside as ``models.json.bad``."""
    f = _file()
    for _ in range(10):
        try:
            raw = f.read_bytes()
            break
        except FileNotFoundError:
            return {"v": 1, "models": {}}
        except PermissionError:   # Windows: being replaced this very instant
            time.sleep(0.02)
    else:
        raise RegistryUnavailable(f"cannot read {f}")
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("models"), dict):
            raise ValueError("not a model registry")
    except ValueError as exc:
        logger.warning("model registry %s is damaged (%s); starting a new one", f, exc)
        if repair:
            try:
                os.replace(f, str(f) + ".bad")
            except OSError:
                pass
        return {"v": 1, "models": {}}
    data["models"] = {k: v for k, v in data["models"].items()
                      if isinstance(k, str) and isinstance(v, dict)}
    data.setdefault("v", 1)
    return data


def _write(data: dict) -> None:
    """Write to a temp file beside the registry, then os.replace it over the old one."""
    f = _file()
    tmp = f.with_name(f"{f.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    blob = json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")
    try:
        with open(tmp, "wb") as fh:
            fh.write(blob)
        for _ in range(25):
            try:
                os.replace(tmp, f)
                return
            except PermissionError:   # Windows: a lock-free reader has it open right now
                time.sleep(0.02)
        raise RegistryUnavailable(f"cannot replace {f}")
    finally:
        try:
            os.remove(tmp)            # still there only when the replace failed
        except OSError:
            pass


def _update(change):
    """Run ``change(models)`` on the freshly read registry under the lock and save it."""
    with _Lock():
        data = _read(repair=True)
        result = change(data["models"])
        _write(data)
        return result


# ---------------------------------------------------------------------------- records
def _by_path(models: dict, k: str) -> str | None:
    hits = [(r.get("seen") or 0, mid) for mid, r in models.items()
            if r.get("path") and os.path.normcase(r["path"]) == k]
    return max(hits)[1] if hits else None


def _push_history(rec: dict, old: str) -> None:
    rest = [p for p in rec.get("history") or [] if isinstance(p, str) and not _same(p, old)]
    rec["history"] = [old] + rest[:HISTORY_MAX - 1]


def _bind(rec: dict, path: str) -> None:
    """Bind a record to ``path``; the path it had moves into its history."""
    old = rec.get("path")
    if old and not _same(old, path):
        _push_history(rec, old)
    rec["history"] = [p for p in rec.get("history") or [] if not _same(p, path)]
    rec["path"] = path


def _new(models: dict, k: str, path: str, now: float, parent: str | None) -> str:
    mid = _id_of_key(k)
    if mid in models:             # the path was that model's before (A saved as B, A reopened):
        parent = mid              # a surer lineage than equal content
        while mid in models:
            mid = "m" + uuid.uuid4().hex[:10]
    models[mid] = {"path": path, "history": [], "parent": parent, "created": now,
                   "seen": now, "sha1": None, "size": None, "written": None}
    return mid


# ---------------------------------------------------------------------------- API
def identify(path) -> str:
    """The id of the model in ``path``, registering the path (and its content) if new."""
    try:
        full = _long(path)
        k = os.path.normcase(full)
        sha, size = _fingerprint(full)
        now = time.time()

        def change(models):
            mid = _by_path(models, k)
            if mid is None and sha:
                same = sorted(((r.get("seen") or 0, i) for i, r in models.items()
                               if r.get("sha1") == sha and r.get("size") == size), reverse=True)
                gone = [i for _, i in same if not _exists(models[i].get("path"))]
                if gone:          # its file is gone: moved or renamed outside the server
                    mid = gone[0]
                    logger.info("model %s: %s -> %s (same content)", mid, models[mid].get("path"), full)
                    _bind(models[mid], full)
                elif same:        # its file is still there: a copy
                    mid = _new(models, k, full, now, same[0][1])
            if mid is None:
                mid = _new(models, k, full, now, None)
            models[mid].update(seen=now, sha1=sha, size=size)
            return mid

        return _update(change)
    except Exception as exc:
        logger.warning("model registry: cannot identify %s (%s); using the path lookup", path, exc)
        return _fallback(path)


def fresh(path) -> str:
    """Register ``path`` as a new model whatever its content, for a file the server has just
    created: every copy of the blank template has the same content, so ``identify`` would
    take a new one for an earlier copy that moved, or for a copy of one. A model bound to the
    path before loses it. The id is the old formula unless that is taken."""
    try:
        full = _long(path)
        k = os.path.normcase(full)
        sha, size = _fingerprint(full)
        now = time.time()

        def change(models):
            for r in models.values():
                if _same(r.get("path"), full):
                    _push_history(r, r["path"])
                    r["path"] = None
            mid = _id_of_key(k)
            while mid in models:
                mid = "m" + uuid.uuid4().hex[:10]
            models[mid] = {"path": full, "history": [], "parent": None, "created": now,
                           "seen": now, "sha1": sha, "size": size, "written": None}
            return mid

        return _update(change)
    except Exception as exc:
        logger.warning("model registry: cannot register the new model %s (%s)", path, exc)
        return _fallback(path)


def _fallback(path) -> str:
    try:
        k = key(path)
        return _by_path(_read()["models"], k) or _id_of_key(k)
    except Exception:
        return legacy_id(path)


def find(path) -> str | None:
    """The id bound to ``path`` now, without registering anything; None if none is."""
    try:
        return _by_path(_read()["models"], key(path))
    except Exception as exc:
        logger.warning("model registry: lookup of %s failed (%s)", path, exc)
        return None


def get(model_id: str) -> dict | None:
    """A copy of a model's record (``path``, ``history``, ``written``, ...), or None."""
    try:
        rec = _read()["models"].get(model_id)
        return json.loads(json.dumps(rec)) if rec is not None else None
    except Exception as exc:
        logger.warning("model registry: read of %s failed (%s)", model_id, exc)
        return None


def rebind(model_id: str, new_path) -> bool:
    """After a Save As the server made: bind the model to ``new_path``, its old path into
    ``history``. A model that was bound to ``new_path`` loses its path (its file has just been
    overwritten). False, logged, when the registry could not be updated."""
    try:
        full = _long(new_path)
        now = time.time()

        def change(models):
            for oid, r in models.items():
                if oid != model_id and _same(r.get("path"), full):
                    logger.info("model %s lost its file %s to model %s", oid, full, model_id)
                    _push_history(r, r["path"])
                    r["path"] = None
            rec = models.get(model_id)
            if rec is None:
                models[model_id] = {"path": full, "history": [], "parent": None, "created": now,
                                    "seen": now, "sha1": None, "size": None, "written": None}
            else:
                _bind(rec, full)
                rec["seen"] = now

        _update(change)
        return True
    except Exception as exc:
        logger.warning("model registry: cannot rebind %s to %s (%s)", model_id, new_path, exc)
        return False


def note_written(model_id: str, path, side: dict | None = None) -> bool:
    """Record that the server just wrote ``path`` for this model: ``written`` (size, mtime_ns,
    and ``side``, the stamps of files written with it) and the content fingerprint. False,
    logged, when the registry could not be updated."""
    try:
        full = _long(path)
        st = os.stat(full)
        sha, size = _fingerprint(full)
        now = time.time()

        def change(models):
            rec = models.get(model_id)
            if rec is None:
                rec = models[model_id] = {"path": full, "history": [], "parent": None,
                                          "created": now, "written": None}
            written = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
            if side:
                written["side"] = side
            rec.update(seen=now, sha1=sha, size=size, written=written)

        _update(change)
        return True
    except Exception as exc:
        logger.warning("model registry: cannot record the write of %s (%s)", path, exc)
        return False
