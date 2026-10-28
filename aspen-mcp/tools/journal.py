"""Operation journal and change groups: every change to a model, as the server
measured it, in one append-only file per model.

    ~/.aspen-mcp/journal/<model id>/      (the id from tools/model_registry.py)
        meta.json           {"model", "path", "name"}: which model this is, for a human
        journal.jsonl       one JSON record per line, UTF-8, append only
        journal-<t0>.jsonl  the file above, renamed once it passed ROTATE_BYTES
        spill-<pid>.jsonl   records written while the journal was locked elsewhere; the next
                            write that gets the lock moves them into journal.jsonl
        journal.lock        O_CREAT|O_EXCL; waits LOCK_WAIT_S, breaks one older than LOCK_STALE_S

Records (v1) come from ``entry()``: ``change`` (op, target, before/after, status, reason...),
``group`` (a change group's header; a later one with the same id updates its title),
``begin`` (a long call started: an optimization, a loop, a program run -- written when it
starts, so a server that dies in the middle leaves it) and ``end`` (such a call ended without
a change record of its own). A begin is ended by any later record with its ``call``; readers
(``groups``, ``page``) mark one without as ``open``, and ``line`` says "started, no end
recorded". ``append()`` writes one call's records in one write after
ending any line a crash left torn; ``read()`` pages newest first; ``groups()`` folds records
under their group; ``summary()`` is the fixed-size digest for state.json -- with what changed
since the last run (``stale``) and since the file was last in step with Aspen (``unsaved``),
kept per target so a change undone is no change; ``pending()`` hands the stale changes to a
run record; ``digest()`` the
newest groups as short lines for the AI (``line()`` renders one record; a caller may name
fields in words: tools/aspen_labels.named); ``others()`` counts what this process's AI did
not write, the quick check of tools/brief.py. ``page()``, ``find()``, ``latest_by_path()``
and ``net()`` (before -> now over a stretch: inputs net, the runs' results chained) serve the
workbench window's timeline, which reads these files itself (workbench/window.py): only
reading, so the timeline works while Aspen holds the server. ``suspects()``, what changed since
the last good run, is the failure card's (tools/diagnose.py), read the same way.
``listen(fn)`` has ``fn(model, records)`` called after each append.

``Groups`` decides which group a change joins; its clock is the module's ``now``, kept as a
module attribute so it can be overridden. ``ASPEN_MCP_JOURNAL=0`` stops all writing; grouping and reading still work.

Nothing here raises: a failure is logged and the call degrades (a spill file, then the
records are dropped). Pure stdlib, no COM, no I/O at import.
"""
from __future__ import annotations

import functools
import json
import logging
import math
import numbers
import os
import re
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path.home() / ".aspen-mcp"      # read at call time, so it can be pointed elsewhere
SERVER = "aspen-mcp"                   # this server's name in each record's "srv"; server.py sets it
ROTATE_BYTES = 8 << 20
ARCHIVE_CAP = 200 << 20                # rotated files of all models above this in total lose
ARCHIVE_AGE_S = 180 * 86400            # ... their oldest files older than this
LOCK_WAIT_S = 1.0
LOCK_STALE_S = 10.0                    # a lock this old belongs to a process that died
IDLE_S = 90.0                          # an actor quiet this long starts a new group
DIAG_TTL_S = 600.0                     # a failed run starts the AI's diagnose group this long after it at most
DIAG_TITLE = "Diagnose and fix"       # ... its title, then ": " and the failing blocks (at most DIAG_NAMES);
                                       # older journals hold a Chinese title (workbench/static/changes.js reads both)
DIAG_NAMES = 3
CHUNK = 64 * 1024                      # read() reads files backwards this much at a time
SLACK = 256                            # records read past a page: appends are only roughly in time order
VALUE_MAX, RESULT_MAX, REASON_MAX, TITLE_MAX = 500, 300, 500, 80
DIGEST_MAX = 3000                      # characters of lines digest() hands workbench_read
RUN_MSGS, RUN_MSG_WIDTH = 8, 160       # run-status lines summary()["run"] keeps, characters of each
INPUT_OPS = frozenset({"value", "attr", "add", "remove", "connect", "patch", "restore", "summary"})
RUN_OPS = frozenset({"run", "reinit"})
RAN = frozenset({"ok", "warn", "error"})        # a run record's status when Aspen did run
SYNC_OPS = frozenset({"save", "patch", "open"})  # after one the file holds what Aspen holds
TABLE_MAX = 2000                       # targets the stale / unsaved tables keep each (then "more")
LOAD_MIN, LOAD_MAX = 2000, 5000        # records a reload folds; up to MAX to reach the last run and sync
TOP_MAX, PATH_MAX = 3, 200             # summary()["stale"]["top"]: entries, characters of a path
_NO_CHANGE = frozenset({"unchanged", "failed", "refused", "error"})
_OBJ_OPS = ("add", "remove")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_JSON = {"ensure_ascii": False, "separators": (",", ":"), "allow_nan": False}
_CHANGE = re.compile(rb'"kind":"change"[^\n]*\}\n')   # a complete change line (a torn one lacks the })
_ACTOR = re.compile(rb'"actor":"([a-z_]+)"')           # a change line's own actor comes before any nested one
_UNSEEN = object()
ACTORS = ("ai", "user", "program", "optimizer", "external")     # summary()["by"], fixed
PAGE_KINDS = ("change", "begin")                                 # what page() lists

now = time.time                        # the clock of records and groups (a module attribute, so it can be overridden)


def _safe(default=None):
    """Never raise into the caller: log, return ``default`` (called when callable)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            try:
                return fn(*a, **k)
            except Exception as exc:
                logger.warning("journal: %s failed: %r", fn.__name__, exc)
                return default() if callable(default) else default
        return wrapper
    return deco


def enabled() -> bool:
    """False when ``ASPEN_MCP_JOURNAL`` is 0 / off / false / no (read at every call)."""
    return os.environ.get("ASPEN_MCP_JOURNAL", "1").strip().lower() not in ("0", "off", "false", "no")


def _cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n]


def srv() -> str:
    return f"{SERVER}:{os.getpid()}"


# ---------------------------------------------------------------------------- records
_idlock, _seq = threading.Lock(), [0, 0]          # [last ms, counter]


def new_id(prefix: str = "e", t: float | None = None) -> str:
    """``e<date>-<time>-<ms>-<n>`` a record (strictly increasing within the process),
    ``c<date>-<time>-<n>`` a tool call, ``g<date>-<time>-<n><hex>`` a group."""
    t = now() if t is None else t
    with _idlock:
        ms = max(int(t * 1000), _seq[0])
        _seq[1] = (_seq[1] + 1) % 10000
        if _seq[1] == 0:
            ms += 1                                # the counter wrapped: keep the order
        _seq[0], n = ms, _seq[1]
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(ms // 1000))
    if prefix == "e":
        return f"e{stamp}-{ms % 1000:03d}-{n:04d}"
    if prefix == "g":
        return f"g{stamp}-{n:04d}{uuid.uuid4().hex[:2]}"
    return f"{prefix}{stamp}-{n:04d}"


def clean(v, limit: int = VALUE_MAX):
    """A JSON-safe copy: NaN/inf -> "nan"/"inf", bytes and foreign types (COM, datetime) -> str,
    strings cut to ``limit`` with ``"trunc": true`` in the dict that holds them."""
    return _clean(v, limit, 0)[0]


def _clean(v, limit, depth):
    if v is None or isinstance(v, (bool, str)):
        pass
    elif isinstance(v, numbers.Integral):
        return int(v), False
    elif isinstance(v, numbers.Real):
        f = float(v)
        return (f if math.isfinite(f) else str(f)), False
    elif isinstance(v, (bytes, bytearray)):
        v = bytes(v).decode("utf-8", "replace")
    elif isinstance(v, (dict, list, tuple, set, frozenset)) and depth < 8:
        items = list(v.items()) if isinstance(v, dict) else [(None, x) for x in v]
        cut, out = len(items) > 1000, []
        for k, x in items[:1000]:
            y, c = _clean(x, limit, depth + 1)
            out.append((k, y))
            cut |= c
        if not isinstance(v, dict):
            return [y for _, y in out], cut
        out = {str(k): y for k, y in out}
        if cut:
            out["trunc"] = True
        return out, False
    else:
        try:
            v = str(v)
        except Exception:
            v = f"<{type(v).__name__}>"
    if isinstance(v, str) and len(v) > limit:
        return v[:limit], True
    return v, False


def entry(kind: str = "change", **fields) -> dict:
    """One record: ``v``, ``kind``, ``id``, ``t``, ``srv``, then ``fields`` (None dropped);
    ``result`` cut to RESULT_MAX, ``reason`` to REASON_MAX, values through ``clean()``."""
    t = fields.pop("t", None)
    t = now() if t is None else float(t)
    rec = {"v": 1, "kind": kind, "id": fields.pop("id", None) or new_id("e", t),
           "t": round(t, 3), "srv": srv()}
    for k, x in fields.items():
        if x is not None:
            rec[k] = _cut(str(x), RESULT_MAX if k == "result" else REASON_MAX) \
                if k in ("result", "reason") else x
    return clean(rec)


_ATTR_KEY = re.compile(r"^(.*[^\\])#(\d+)$", re.S)


def split_key(key) -> tuple[str, int | None]:
    r"""A written field's key: (path, n) for attribute n's ("path#n"), (path, None) for a
    value's. Aspen's own segment "#n" (a table's n-th element: ...\CID\#0) is path, not attribute."""
    m = _ATTR_KEY.match(str(key))
    return (m.group(1), int(m.group(2))) if m else (str(key), None)


def label(path) -> dict:
    """``{"path", "block"|"stream"|"rxnset"|"chemistry": name, "field"}`` of a tree path; the
    field is what follows Input/Output (``TEMP\\MIXED``), else the last segment."""
    p = str(path or "")
    s = [x for x in p.split("\\") if x]
    out, rest = {"path": p}, s
    if len(s) >= 3 and s[0] == "Data" and s[1] in ("Blocks", "Streams"):
        out["block" if s[1] == "Blocks" else "stream"], rest = s[2], s[3:]
    elif len(s) >= 4 and s[0] == "Data" and s[1] == "Reactions":
        out["rxnset" if s[2] == "Reactions" else "chemistry"], rest = s[3], s[4:]
    io = next((i for i, x in enumerate(rest) if x in ("Input", "Output")), None)
    if io is not None and io + 1 < len(rest):
        out["field"] = "\\".join(rest[io + 1:])
    elif rest:
        out["field"] = rest[-1]
    return out


# ---------------------------------------------------------------------------- files
def _dir(model) -> Path:
    if not isinstance(model, str) or not _SAFE_ID.match(model):
        raise ValueError(f"not a model id: {model!r}")
    return Path(ROOT) / "journal" / model


class _Busy(Exception):
    """The journal's lock is held by another writer."""


class _Lock:
    """``journal.lock`` created with O_EXCL; waits up to LOCK_WAIT_S, breaks a stale one."""

    def __init__(self, folder: Path):
        self.path, self.fd = str(folder / "journal.lock"), None

    def __enter__(self):
        deadline = time.monotonic() + LOCK_WAIT_S
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(self.fd, str(os.getpid()).encode())   # who holds it, for a human
                except OSError:
                    pass
                return self
            except FileNotFoundError:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)   # the model's first record
                if os.path.isdir(os.path.dirname(self.path)):
                    continue
            except FileExistsError:
                try:
                    if time.time() - os.stat(self.path).st_mtime > LOCK_STALE_S:
                        os.remove(self.path)
                        logger.warning("journal: removed a stale lock %s", self.path)
                        continue
                except OSError:
                    pass          # released meanwhile: try again
            except PermissionError:
                pass              # Windows: the previous holder's lock is still being deleted
            if time.monotonic() >= deadline:
                raise _Busy(f"{self.path} is held by another writer")
            time.sleep(0.005)

    def __exit__(self, *exc):
        try:
            os.close(self.fd)
        finally:
            try:
                os.remove(self.path)
            except OSError:
                pass


def _size(f) -> int:
    try:
        return os.stat(f).st_size
    except OSError:
        return -1


def _retry(fn, *a):
    """Windows: a file being renamed or read elsewhere this instant refuses access; retry briefly."""
    for i in range(25):
        try:
            return fn(*a)
        except PermissionError:
            if i == 24:
                raise
            time.sleep(0.01)


_ends: dict = {}                  # file -> its size after this process's last write (ends in \n)


def _put(f, blob: bytes) -> tuple[int, int]:
    """Append ``blob`` in one write, first ending a line a crash left torn: (size before, after).
    The last byte is read only when someone else wrote since this process did: on Windows a
    read-open of a just-written file costs ~5 ms (the virus scanner), a write-only one ~0.05."""
    f = str(f)
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0))
    try:
        size = os.fstat(fd).st_size
        if size and _ends.get(f) != size:
            with open(f, "rb") as fh:
                fh.seek(size - 1)
                if fh.read(1) != b"\n":
                    blob = b"\n" + blob
        view = memoryview(blob)
        while view:
            view = view[os.write(fd, view):]
        _ends[f] = size + len(blob)
        return size, size + len(blob)
    finally:
        os.close(fd)


def _parse(raw: bytes):
    try:
        rec = json.loads(raw)
    except ValueError:
        return None
    return rec if isinstance(rec, dict) else None


def _archives(folder: Path) -> list[Path]:
    """Rotated files, oldest first (the time in the name, then its collision counter)."""
    return sorted(folder.glob("journal-*.jsonl"),
                  key=lambda p: tuple(int(x) for x in re.findall(r"\d+", p.stem)))


def _rotate(folder: Path, f: Path) -> bool:
    """Rename a full journal.jsonl to journal-<time of its first record>.jsonl, then prune."""
    with open(f, "rb") as fh:
        head = fh.read(CHUNK)
    t0 = next((r["t"] for r in map(_parse, head.split(b"\n"))
               if r and isinstance(r.get("t"), (int, float))), None) or time.time()
    ms = int(t0 * 1000)
    stem = f"journal-{time.strftime('%Y%m%d-%H%M%S', time.localtime(ms // 1000))}-{ms % 1000:03d}"
    dest, i = folder / f"{stem}.jsonl", 0
    while dest.exists():
        i += 1
        dest = folder / f"{stem}-{i}.jsonl"
    _retry(os.replace, f, dest)
    _prune()
    return True


def _prune() -> None:
    """Rotated files of all models above ARCHIVE_CAP: remove the oldest past ARCHIVE_AGE_S."""
    files = []
    for f in (Path(ROOT) / "journal").glob("*/journal-*.jsonl"):
        try:
            st = f.stat()
            files.append((st.st_mtime, st.st_size, f))
        except OSError:
            pass
    total, cutoff = sum(x[1] for x in files), time.time() - ARCHIVE_AGE_S
    for mtime, size, f in sorted(files, key=lambda x: x[0]):
        if total <= ARCHIVE_CAP:
            break
        if mtime < cutoff:
            try:
                os.remove(f)
                total -= size
                logger.info("journal: removed old archive %s", f)
            except OSError:
                pass


def _side(folder: Path, *prefixes) -> list[Path]:
    """The spill-* / merge-* files of a model, by name."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return [folder / n for n in sorted(names) if n.startswith(prefixes) and n.endswith(".jsonl")]


def _take_spills(folder: Path) -> tuple[bytes, list]:
    """Under the lock: every spill file's complete lines and the merge-*.jsonl holding them.
    A spill file is renamed first, so its writer (which never locks) starts a new one."""
    side = _side(folder, "spill-", "merge-")
    if not side:
        return b"", []
    for p in side:
        if p.name.startswith("spill-"):
            try:
                os.replace(p, folder / f"merge-{uuid.uuid4().hex[:8]}.jsonl")
            except OSError:
                pass              # its writer has it open right now: next time
    data, done = [], []
    for m in _side(folder, "merge-"):             # + leftovers of a merge that crashed
        try:
            raw = m.read_bytes()
        except OSError:
            continue
        data.append(raw[:raw.rfind(b"\n") + 1])
        done.append(m)
    return b"".join(data), done


def _drop(paths) -> None:
    for p in paths:
        try:
            _retry(os.remove, p)
        except FileNotFoundError:
            pass
        except OSError:
            try:
                open(p, "wb").close()     # a reader holds it: empty it, never merge it twice
            except OSError:
                logger.warning("journal: %s merged but not removed", p)


def _pending(folder: Path) -> list[dict]:
    """The complete records waiting in spill / merge files."""
    out = []
    for p in _side(folder, "spill-", "merge-"):
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        out += [r for r in map(_parse, raw[:raw.rfind(b"\n") + 1].split(b"\n")) if r]
    return out


def _backward(f, retry: bool = False):
    """The complete records of ``f``, last first; a torn last line and bad lines skipped.
    ``retry``: a file being renamed this instant (PermissionError) is tried again briefly."""
    try:
        fh = _retry(open, f, "rb") if retry else open(f, "rb")
    except OSError:
        return
    with fh:
        pos, buf, torn = fh.seek(0, os.SEEK_END), b"", True
        while pos > 0:
            n = min(CHUNK, pos)
            pos -= n
            fh.seek(pos)
            parts = (fh.read(n) + buf).split(b"\n")
            buf = parts.pop(0)
            if parts and torn:
                parts.pop()               # after the last newline: empty, or a torn line
                torn = False
            for raw in reversed(parts):
                rec = _parse(raw)
                if rec is not None:
                    yield rec
        rec = None if torn else _parse(buf)
        if rec is not None:
            yield rec


def _scan(folder: Path, retry: bool = False):
    for f in [folder / "journal.jsonl", *reversed(_archives(folder))]:
        yield from _backward(f, retry)


def _dump(rec: dict) -> bytes:
    try:
        s = json.dumps(rec, **_JSON)
    except (TypeError, ValueError):
        s = json.dumps(clean(rec), **_JSON)
    return (s + "\n").encode("utf-8", "replace")


_metas: dict = {}


def _meta(folder: Path, model: str, path) -> None:
    """meta.json names the model's file, so a person browsing the folder knows whose it is."""
    want = {"model": model, "path": str(path), "name": os.path.basename(str(path))}
    if _metas.get(model) == want:
        return
    try:
        f = folder / "meta.json"
        try:
            same = json.loads(f.read_text(encoding="utf-8")) == want
        except (OSError, ValueError):
            same = False
        if not same:
            tmp = folder / f"meta.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp"
            tmp.write_text(json.dumps(want, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, f)
        _metas[model] = want
    except Exception as exc:
        logger.warning("journal: cannot write meta.json of %s (%s)", model, exc)


# ---------------------------------------------------------------------------- summary
_plock = threading.RLock()        # one writer per process; guards the caches
_sums: dict = {}                  # model -> _cache(): the summary and what advances it
_mine: dict = {}                  # model -> change records this process wrote for MCP calls (via "mcp")
_listeners: list = []             # listen(): told after each append that wrote or spilled


def _blank(model: str) -> dict:
    return {"model": model, "n": 0, "last_t": None, "last_input_t": None, "last_run_t": None,
            "group": None, "last": None, "by": dict.fromkeys(ACTORS, 0)}


def _cache(model: str, size: int) -> dict:
    """A model's summary cache: journal.jsonl's ``size`` when last seen, the summary ``s``,
    group ``titles``, the ``stale`` / ``unsaved`` tables (in memory only), the runs that ran so
    far (``seq``), the model's file as last known, the call of the last sync point and the
    time of the latest record found made in Aspen's own window."""
    return {"size": size, "s": _blank(model), "titles": {}, "stale": _Net(), "unsaved": _Net(),
            "seq": 0, "file": None, "sync_call": None, "ext_t": None}


def _num(x):
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x)
        except ValueError:
            return None
    return None


def _same(a, b) -> bool:
    """Equal as Aspen holds it: "35" and 35.0 are one value."""
    if a == b:
        return True
    x, y = _num(a), _num(b)
    return x is not None and y is not None and math.isclose(x, y, rel_tol=1e-12, abs_tol=0.0)


def _copy(x):
    return dict(x) if isinstance(x, dict) else list(x) if isinstance(x, list) else x


def _differs(e: dict) -> bool:
    """Whether a target is not as it was before its first change since the reset point: a
    value / unit / basis read on both sides differs, a port holds other streams. An object
    added and then removed is no change; any other addition or removal is one."""
    op0, op = e["op0"], e["op"]
    if op0 in _OBJ_OPS or op in _OBJ_OPS:
        return not (op0 == "add" and op == "remove")
    a, b = e["first"], e["last"]
    if isinstance(a, list) and isinstance(b, list):
        return sorted(map(str, a)) != sorted(map(str, b))
    if not isinstance(a, dict) or not isinstance(b, dict):
        return True                     # not measured on both sides: count it
    keys = [k for k in a if k in b]
    return not keys or any(not _same(a[k], b[k]) for k in keys)


class _Net:
    """The targets changed since a reset point (``stale``: the last run that ran; ``unsaved``:
    the last sync point), by key -- a field's path in lower case (``#n`` for an attribute), a
    port's path, ``obj:`` + an object's path -- each {"path", "op0", "op", "first": the state
    before its first change, "last": after its latest, "actor", "t", "n", "tg"}, least recently
    changed first. ``net`` counts those that ``_differs``. Past TABLE_MAX targets new ones are
    not kept and ``more`` is set. ``since`` / ``rid``: the reset point's time and record id;
    ``runs``: runs that ran since (``unsaved``'s runs since the last save)."""
    __slots__ = ("d", "net", "more", "since", "rid", "runs")

    def __init__(self):
        self.reset()

    def reset(self, t=None, rid=None) -> None:
        self.d, self.net, self.more, self.since, self.rid, self.runs = {}, 0, False, t, rid, 0

    def put(self, key, path, op, before, after, actor, t, tg=None) -> None:
        e = self.d.pop(key, None)
        if e is None:
            if len(self.d) >= TABLE_MAX:
                self.more = True
                return
            e, was = {"path": path, "op0": op, "first": _copy(before), "last": None, "n": 0}, False
        else:
            was = _differs(e)
            if isinstance(e["first"], dict) and isinstance(before, dict):
                for k, v in before.items():   # a value-only write read no unit; a later write's before did
                    e["first"].setdefault(k, v)
        last = e["last"]
        e["last"] = {**last, **after} if isinstance(last, dict) and isinstance(after, dict) else _copy(after)
        e.update(op=op, actor=actor, t=t, n=e["n"] + 1)
        if tg:
            e["tg"] = tg
        self.d[key] = e
        self.net += _differs(e) - was

    def drop(self, prefix: str) -> None:
        """Forget the targets under a removed object (``prefix``: its path in lower case + \\)."""
        for k in [k for k in self.d if k.startswith(prefix) or k.startswith("obj:" + prefix)]:
            self.net -= _differs(self.d.pop(k))

    def changes(self):
        """(key, entry) of the targets that differ, the latest changed first."""
        return ((k, e) for k, e in reversed(self.d.items()) if _differs(e))


def _later(a, b):
    return b if b is not None and (a is None or b > a) else a


def _run_of(r: dict, t) -> dict:
    """summary()["run"]: the latest run that ran, whoever made it -- the window's, a program's,
    the AI's run_simulation: {"id", "t", "status", "actor", "via", "tool", "errors", "warnings",
    "secs", "first_warn" (tools/probes.run_warning, after a warn), "msgs": its first RUN_MSGS
    run-status lines} (keys without a value left out)."""
    out = {k: r[k] for k in ("id", "status", "actor", "via", "tool", "errors", "warnings", "secs", "first_warn")
           if r.get(k) is not None}
    out["t"] = t
    msgs = r.get("msgs")
    if isinstance(msgs, list) and msgs:
        out["msgs"] = [_cut(str(m), RUN_MSG_WIDTH) for m in msgs[:RUN_MSGS]]
    return out


def _fold(c: dict, r: dict) -> None:
    """Advance a cached summary by one record written after those it has seen."""
    s, titles = c["s"], c["titles"]
    if r.get("kind") == "group":
        info = titles.setdefault(r.get("id"), {})
        for k in ("title", "actor"):
            if r.get(k):
                info[k] = _cut(str(r[k]), TITLE_MAX)
        if s["group"] and s["group"]["id"] == r.get("id"):
            s["group"]["title"] = info.get("title")
        while len(titles) > 64:
            titles.pop(next(iter(titles)))
        return
    if r.get("kind") != "change":
        return
    t = r.get("t") if isinstance(r.get("t"), (int, float)) else None
    op, st = r.get("op"), r.get("status")
    runs = r.get("runs") if isinstance(r.get("runs"), dict) else {}
    s["n"] += 1
    if r.get("actor") in s["by"]:
        s["by"][r["actor"]] += 1
    s["last_t"] = _later(s["last_t"], t)
    if op in INPUT_OPS and st not in _NO_CHANGE:
        s["last_input_t"] = _later(s["last_input_t"], t)
    if (op in RUN_OPS and st not in ("refused", "failed")) or runs.get("n"):
        s["last_run_t"] = _later(s["last_run_t"], t)
    _track(c, r, t)
    if op == "run" and st in RAN:
        if s.get("run") is None or (t or 0) >= (s["run"].get("t") or 0):
            s["run"] = _run_of(r, t)
        s["run"]["seq"] = c["seq"]
    gid = r.get("group")
    if gid:
        if not s["group"] or s["group"]["id"] != gid:
            info = titles.get(gid, {})
            s["group"] = {"id": gid, "title": info.get("title"),
                          "actor": info.get("actor") or r.get("actor"), "n": 0}
        s["group"]["n"] += 1
    path = (r.get("target") or {}).get("path") if isinstance(r.get("target"), dict) else None
    s["last"] = {"actor": r.get("actor"), "tool": r.get("tool"), "op": op,
                 "path": _cut(str(path), 200) if path else None}


def _dict(r, k) -> dict:
    return r.get(k) if isinstance(r.get(k), dict) else {}


def _ran(runs: dict) -> int:
    """A loop's runs that ran: all but the refused and failed ones."""
    try:
        return max(0, int(runs.get("n") or 0) - int(runs.get("refused") or 0) - int(runs.get("failed") or 0))
    except (TypeError, ValueError):
        return 0


def _is_run(r: dict) -> bool:
    """A run record of a run that ran -- what summary()["run"]["seq"] counts."""
    return r.get("op") == "run" and r.get("status") in RAN


def _track(c: dict, r: dict, t) -> None:
    """Advance the ``stale`` and ``unsaved`` tables, the run count, the last sync
    point (``save``) and the last backup by one change record. A run that ran, or a loop that
    ran the model, resets ``stale``; a sync point (a save, a patch that rewrote the file, an
    open, a save made in Aspen's window, a restore of the model to a restore point -- which also
    resets ``stale`` when that point's results matched its inputs, ``fresh``) resets ``unsaved``; value / attr / add / remove /
    connect records that changed something go into both -- but for ``unsaved`` not those of
    the sync point's own call (a patch that adds chemistry wrote it into the file). A reinit
    runs nothing: it resets neither."""
    op, st, who, s = r.get("op"), r.get("status"), r.get("actor"), c["s"]
    stale, uns = c["stale"], c["unsaved"]
    if who == "external":
        c["ext_t"] = _later(c["ext_t"], t)
    _backup(s, r, t)
    if op in RUN_OPS:
        if _is_run(r):
            c["seq"] += 1
            stale.reset(t, r.get("id"))
            uns.runs += 1
        return
    if _put_back(r):                      # the model put back to a restore point: the file holds it
        _synced(c, r, t, how="restore")
        if r.get("fresh") is True:        # ... with results that matched its inputs then
            stale.reset(t, r.get("id"))
        return
    if op in ("summary", "restore"):
        _loop_writes(c, r, t)
        return
    if st in _NO_CHANGE:
        return
    if op in SYNC_OPS:
        _synced(c, r, t)
        return
    args, gone = _args(r, t)
    if args is None:
        return
    if gone:
        stale.drop(gone)
        uns.drop(gone)
    stale.put(*args)
    if r.get("call") is None or r.get("call") != c["sync_call"]:
        uns.put(*args)


def _args(r: dict, t) -> tuple:
    """(the ``_Net.put`` arguments of a value / attr / add / remove / connect record -- its target's
    key: a field's path in lower case, ``#n`` for an attribute, ``obj:`` + an object's path, a
    port's path -- and, for a removal, the prefix of the targets under the object it took away);
    (None, None) for a record of another op or without a target path."""
    op, tg, who = r.get("op"), _dict(r, "target"), r.get("actor")
    path = str(tg.get("path") or "")
    if not path:
        return None, None
    low = path.lower()
    if op in ("value", "attr"):
        n = tg.get("attr", r.get("attr")) if op == "attr" else None
        return (low if n is None else f"{low}#{n}", path, op, r.get("before"), r.get("after"), who, t), None
    if op in _OBJ_OPS:
        return ("obj:" + low, path, op, None, None, who, t, {k: tg[k] for k in ("kind", "name", "type") if tg.get(k)}), \
            (low + "\\" if op == "remove" else None)
    if op == "connect":
        return (low, path, op, r.get("before"), r.get("after"), who, t,
                {k: tg[k] for k in ("block", "port", "stream") if tg.get(k)}), None
    return None, None


def _writes(r: dict, t):
    """The ``_Net.put`` arguments of each field a loop's, an optimization's or a restore's summary
    left changed in this session's model (its ``writes``: a status given, or before / after differ)."""
    for p, w in _dict(r, "writes").items():
        if not isinstance(w, dict) or w.get("session"):       # another session's model
            continue
        b, a = w.get("before"), w.get("after")
        st = w.get("status")
        if st is None:
            st = "changed" if isinstance(b, dict) and isinstance(a, dict) and \
                any(k in a and not _same(v, a[k]) for k, v in b.items()) else "unchanged"
        if st == "changed":
            p = str(p)
            path, n = split_key(p)
            yield p.lower(), path, "attr" if n is not None else "value", b, a, r.get("actor"), t


def _put_back(r: dict) -> bool:
    """A restore of the whole model to a restore point (``target.checkpoint``) that happened
    -- not a program's restore of the values its loops wrote (op restore too, with ``writes``)."""
    return r.get("op") == "restore" and bool(_dict(r, "target").get("checkpoint")) and \
        r.get("status") not in _NO_CHANGE


def _loop_writes(c: dict, r: dict, t) -> None:
    """A loop's, an optimization's or a restore's summary: runs that ran reset ``stale``, and
    its net writes go there only when it left the results behind its inputs (no run, or a
    report whose re-run is not ok / warn and that did not finish at the last point); its net
    writes go into ``unsaved``, after any save it made."""
    stale, uns = c["stale"], c["unsaved"]
    ran, rep, saves = _ran(_dict(r, "runs")), _dict(r, "report"), _dict(r, "saves")
    if saves.get("ok"):
        files = saves.get("files") if isinstance(saves.get("files"), list) else []
        _synced(c, r, t, how="save", path=files[-1] if files else None)
    if ran:
        stale.reset(t, r.get("id"))
        uns.runs += ran
    behind = not ran or (bool(rep) and rep.get("run") not in ("ok", "warn") and rep.get("state") != "last")
    for args in _writes(r, t):
        uns.put(*args)
        if behind:
            stale.put(*args)


def _fkey(path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _synced(c: dict, r: dict, t, how=None, path=None) -> None:
    """A sync point: ``unsaved`` starts again and ``save`` says {"t", "actor", "via", "file",
    "how": save | saveas (to another file than the last known) | patch | open | external |
    restore (the model put back to a restore point, written into its file)}."""
    c["unsaved"].reset(t, r.get("id"))
    c["sync_call"] = r.get("call")
    op, who = r.get("op"), r.get("actor")
    if path is None:
        ws = r.get("writes") if isinstance(r.get("writes"), list) else []
        path = next((w.get("path") for w in ws if isinstance(w, dict) and w.get("ok") and w.get("path")), None) \
            or _dict(r, "target").get("path") or r.get("file")
    if how is None:
        how = op if op in ("patch", "open") else "external" if who == "external" else \
            "saveas" if path and c["file"] and _fkey(path) != _fkey(c["file"]) else "save"
    if path:
        c["file"] = str(path)
    save = {"t": t, "actor": who, "via": r.get("via"), "file": _cut(_base(path), 80) if path else None, "how": how}
    c["s"]["save"] = {k: v for k, v in save.items() if v is not None}


def _backup(s: dict, r: dict, t) -> None:
    """summary()["backup"]: the latest copy made before the server overwrote the model's file."""
    cps = r.get("checkpoints") if isinstance(r.get("checkpoints"), list) else []
    ws = r.get("writes") if isinstance(r.get("writes"), list) else []
    ids = [x.get("id") for x in cps if isinstance(x, dict) and x.get("reason") == "before-overwrite"]
    ids += [w.get("backup") for w in ws if isinstance(w, dict)]
    bid = next((x for x in reversed(ids) if x), None)
    if bid:
        s["backup"] = {"t": t, "id": _cut(str(bid), 120)}


def _reaches(recs) -> tuple[bool, bool]:
    """Whether records hold a run that ran (a loop's too) and a sync point."""
    run = sync = False
    for r in recs:
        if r.get("kind") != "change":
            continue
        op = r.get("op")
        loop = op in ("summary", "restore")
        back = _put_back(r)
        run = run or _is_run(r) or (loop and _ran(_dict(r, "runs")) > 0) or (back and r.get("fresh") is True)
        sync = sync or (op in SYNC_OPS and r.get("status") not in _NO_CHANGE) or back or \
            (loop and bool(_dict(r, "saves").get("ok")))
        if run and sync:
            break
    return run, sync


def _count(f, by: dict, ran: list) -> int:
    """Complete change records in ``f``, without parsing them; ``by`` counts their actors,
    ``ran[0]`` the run records of runs that ran (only a line with ``"op":"run"`` is parsed)."""
    n, rest = 0, b""
    try:
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                buf = rest + chunk
                cut = buf.rfind(b"\n") + 1
                for m in _CHANGE.finditer(buf, 0, cut):
                    n += 1
                    a = _ACTOR.search(buf, m.start(), m.end())
                    if a is not None:
                        k = a.group(1).decode("ascii")
                        if k in by:
                            by[k] += 1
                    if buf.find(b'"op":"run"', m.start(), m.end()) >= 0:
                        r = _parse(buf[buf.rfind(b"\n", 0, m.start()) + 1:m.end()])
                        ran[0] += r is not None and _is_run(r)
                rest = buf[cut:]
    except OSError:
        pass
    return n


def _load(model: str, folder: Path) -> dict:
    """The cache from the files: the newest LOAD_MIN records folded -- up to LOAD_MAX when those
    do not reach back to the last run and the last sync point (then, when the journal is longer,
    that table says ``more``) -- and, over every file, the change records, their actors and the
    runs that ran."""
    c, kinds, limit = _cache(model, _size(folder / "journal.jsonl")), ("change", "group"), LOAD_MIN
    recs = read(model, limit=limit, kinds=kinds)
    if len(recs) >= limit and not all(_reaches(recs)):
        limit = LOAD_MAX
        recs = read(model, limit=limit, kinds=kinds)
    for r in reversed(recs):
        _fold(c, r)
    if len(recs) >= limit:
        run, sync = _reaches(recs)
        c["stale"].more |= not run
        c["unsaved"].more |= not sync
    by, ran = dict.fromkeys(ACTORS, 0), [0]
    n = sum(_count(f, by, ran) for f in [folder / "journal.jsonl", *_archives(folder)])
    for r in _pending(folder):
        if r.get("kind") == "change":
            n += 1
            if r.get("actor") in by:
                by[r["actor"]] += 1
            ran[0] += _is_run(r)
    c["s"]["n"], c["s"]["by"], c["seq"] = n, by, ran[0]
    if c["s"].get("run"):
        c["s"]["run"]["seq"] = ran[0]
    return c


def _view(c: dict) -> dict:
    """summary(): ``s`` plus, once there are change records, ``stale`` {"n", "top": the latest
    TOP_MAX changed targets [{"path", "actor", "op" (attr / add / remove / connect)}], "since":
    the reset point's time, "more"}, ``unsaved`` {"n", "since", "runs", "more"} and, once one was
    recorded, ``ext`` {"t": the latest record found made in Aspen's window; how many:
    by.external}. A copy."""
    s = c["s"]
    out = dict(s)
    if s["n"]:
        st, un, top = c["stale"], c["unsaved"], []
        for _, e in st.changes():
            item = {"path": _cut(str(e["path"]), PATH_MAX), "actor": e.get("actor")}
            if e["op"] in ("attr", "add", "remove", "connect"):
                item["op"] = e["op"]
            top.append(item)
            if len(top) >= TOP_MAX:
                break
        out["stale"] = {"n": st.net, "top": top, "since": st.since, "more": st.more}
        out["unsaved"] = {"n": un.net, "since": un.since, "runs": un.runs, "more": un.more}
    if c["ext_t"] is not None and s["by"].get("external"):
        out["ext"] = {"t": c["ext_t"]}
    return json.loads(json.dumps(out))


# ---------------------------------------------------------------------------- API
@_safe(None)
def append(model: str, lines, path=None, groups=None) -> str | None:
    """Write one call's records for one model in a single write, after a ``group`` header
    for each group new to this model (or retitled). ``path``, the model's file, goes into
    meta.json; ``groups=False`` writes no headers. Returns "ok", "spill" (the journal was
    locked or unwritable: kept in spill-<pid>.jsonl), or None (off, or nothing written); after
    "ok" or "spill" the ``listen()`` functions are told."""
    if not enabled():
        return None
    folder = _dir(model)
    recs = [r for r in ([lines] if isinstance(lines, dict) else list(lines or ())) if isinstance(r, dict)]
    g = GROUPS if groups is None else groups
    heads = (g.headers(model, recs) or []) if g else []
    recs = heads + recs
    if not recs:
        return None
    blob = b"".join(map(_dump, recs))
    with _plock:
        merged, sizes = [], None
        try:
            with _Lock(folder):
                extra, merged = _take_spills(folder)
                f = folder / "journal.jsonl"
                n = _size(f)
                if n > 0 and n + len(extra) + len(blob) > ROTATE_BYTES:
                    try:
                        _rotate(folder, f)
                    except OSError as exc:
                        logger.warning("journal %s: not rotated (%s)", model, exc)
                sizes = _put(f, extra + blob)
                _drop(merged)
            how = "ok"
        except (_Busy, OSError) as exc:
            logger.log(logging.INFO if isinstance(exc, _Busy) else logging.WARNING,
                       "journal %s: %s; %d records to the spill file", model, exc, len(recs))
            try:
                _retry(_put, folder / f"spill-{os.getpid()}.jsonl", blob)   # a merger may be renaming it
            except OSError as exc2:
                logger.warning("journal %s: %d records lost (%s)", model, len(recs), exc2)
                return None
            how, merged, sizes = "spill", [], None
        me = srv()
        mine = sum(r.get("kind") == "change" and r.get("via") == "mcp" and r.get("srv") == me for r in recs)
        if mine:
            _mine[model] = _mine.get(model, 0) + mine
        if g:
            g.mark(model, heads)
        if path:
            _meta(folder, model, path)
        c = _sums.get(model)
        if c is not None and (merged or (sizes and sizes[0] != c["size"])):
            _sums.pop(model, None)        # someone else wrote meanwhile: reload when asked
        elif c is not None:
            try:
                for r in recs:
                    _fold(c, r)
                if sizes:
                    c["size"] = sizes[1]
            except Exception as exc:       # the records are written: rebuild the summary when asked
                logger.warning("journal: summary of %s not advanced (%r)", model, exc)
                _sums.pop(model, None)
    if _listeners:
        _tell(model, recs)
    if g and hasattr(g, "after_run"):
        for r in recs:                     # a failed run: the AI's next changes are its diagnosis
            if r.get("kind") == "change" and r.get("op") == "run":
                g.after_run(r.get("status"), failing(r), r.get("session"), r.get("t"), r.get("id"))
    return how


_BLOCK_PATH = re.compile(r"\\Data\\Blocks\\([^\\,;\s]+)")


def failing(r: dict) -> list:
    """The blocks a run record names as failing, the first first: its ``first_error``'s block
    (tools/probes), then those its ``blocks`` list in errors; a refused run's, those its answer
    names incomplete (``\\Data\\Blocks\\B1``: a container alone names none)."""
    fe = r.get("first_error") if isinstance(r.get("first_error"), dict) else {}
    out = [str(fe["block"])] if fe.get("block") else []
    blocks = r.get("blocks") if isinstance(r.get("blocks"), dict) else {}
    out += [str(b) for b, lv in blocks.items() if lv == "error"]
    if r.get("status") == "refused":
        out += _BLOCK_PATH.findall(str(r.get("result") or ""))
    return list(dict.fromkeys(out))


@_safe(list)
def read(model: str, limit: int = 200, before=None, kinds=("change",)) -> list[dict]:
    """Up to ``limit`` records of ``kinds`` (None: all), newest first by (t, id), older than
    ``before``: the last record of the previous page, a (t, id) pair or a time. Spilled
    records are included; torn and unparsable lines are skipped."""
    folder = _dir(model)
    cur = None if before is None else (
        (float(before.get("t") or 0), str(before.get("id") or "")) if isinstance(before, dict)
        else (float(before[0]), str(before[1])) if isinstance(before, (list, tuple))
        else (float(before), ""))
    want = set(kinds) if kinds else None

    def key(r):
        t = r.get("t")
        return (float(t) if isinstance(t, (int, float)) else 0.0, str(r.get("id") or ""))

    def ok(r):
        return (want is None or r.get("kind") in want) and (cur is None or key(r) < cur)

    out, n, it = [r for r in _pending(folder) if ok(r)], 0, _scan(folder)
    try:
        for r in it:
            if ok(r):
                out.append(r)
                n += 1
                if n >= limit + SLACK:
                    break
    finally:
        it.close()
    out.sort(key=key, reverse=True)
    return out[:max(0, limit)]


@_safe(list)
def groups(model: str, limit: int = 3, per: int = 20, scan: int = 2000) -> list[dict]:
    """The newest ``limit`` change groups of a model among its last ``scan`` records, newest
    activity first: {"id", "actor", "title", "source", "note", "session", "ai_group", "t0",
    "t1", "n", "ops": {op: count}, "lines": [its last ``per`` records, oldest first]}.
    The group's newest header gives its title; ``title`` None: the reader makes one up. A
    ``begin`` is a line only while nothing ends it (then marked ``open``: the call is still
    running, or the server died in it); ``end`` records are never lines."""
    by, ended = {}, set()
    for r in read(model, limit=scan, kinds=("change", "group", "begin", "end")):
        kind = r.get("kind")
        if kind in ("change", "end") and r.get("call"):
            ended.add(r["call"])                  # newest first: a call's end comes before its begin
        if kind == "end" or (kind == "begin" and r.get("call") in ended):
            continue
        if kind == "begin":
            r = dict(r, open=True)
        head = kind == "group"
        gid = r.get("id") if head else r.get("group")
        if not gid:
            continue
        g = by.setdefault(gid, {"id": gid, "actor": None, "title": None, "source": None,
                                "note": None, "session": None, "ai_group": None, "t0": None,
                                "t1": None, "n": 0, "ops": {}, "lines": [], "_actor": None})
        t = r.get("t") if isinstance(r.get("t"), (int, float)) else None
        g["t0"] = t if g["t0"] is None or (t is not None and t < g["t0"]) else g["t0"]
        if head:              # newest first: the first header seen is the latest one
            for k in ("actor", "title", "source", "note", "session", "ai_group"):
                g[k] = r.get(k) if g[k] is None else g[k]
            continue
        g["t1"] = _later(g["t1"], t)
        g["_actor"] = g["_actor"] or r.get("actor")
        if r.get("kind") == "change":
            g["n"] += 1
            g["ops"][r.get("op")] = g["ops"].get(r.get("op"), 0) + 1
        if len(g["lines"]) < per:
            g["lines"].append(r)
    out = [g for g in by.values() if g["lines"]]
    for g in out:
        g["actor"] = g["actor"] or g.pop("_actor")
        g.pop("_actor", None)
        g["lines"].reverse()
    out.sort(key=lambda g: g["t1"] or 0, reverse=True)
    return out[:limit]


@_safe(None)
def summary(model: str) -> dict | None:
    """{"model", "n", "last_t", "last_input_t", "last_run_t", "group": {"id", "title",
    "actor", "n"}, "last": {"actor", "tool", "op", "path"}, "by": {actor: n}}; once there are
    change records ``stale`` and ``unsaved`` (``_view``: what changed since the last run that
    ran / since the last sync point, net per target); once recorded "run" (``_run_of``: the
    latest run that ran, among the records a reload folds, with ``seq``: runs that ran so far),
    "save" (the last sync point, ``_synced``), "backup" (``_backup``) and "ext". A fixed size,
    for state.json; ``by`` counts the change records of each of ACTORS. Advanced in memory by
    append(); loaded from the files on first use and again when another process has written."""
    with _plock:
        return _view(_summary(model))


def _summary(model: str) -> dict:
    """The model's cached summary, loaded again when journal.jsonl is not the size last seen."""
    folder = _dir(model)
    c = _sums.get(model)
    if c is None or c["size"] != _size(folder / "journal.jsonl"):
        c = _sums[model] = _load(model, folder)
    return c


@_safe(None)
def others(model: str) -> int | None:
    """How many change records of a model were not written for this process's MCP calls:
    the user's, programs', other processes'. One stat while the summary is cached."""
    with _plock:
        return _summary(model)["s"]["n"] - _mine.get(model, 0)


@_safe(None)
def pending(model: str) -> dict | None:
    """The inputs changed since the last run that ran (summary's ``stale``), for the next run
    record's ``inputs``: {"since": that run's time, "run": its record id, "seq": runs that
    ran so far, "more": the table was full, "items": [the targets that differ, the latest
    changed first: {"path", "op" (value | attr | add | remove | connect), "before": as before its
    first change, "after": after its latest, "actor", "t", "n": records; add / remove / connect
    also "target"}]}; "since" and "run" None before any run. A copy; None if it failed."""
    with _plock:
        c = _summary(model)
        st, items = c["stale"], []
        for _, e in st.changes():
            it = {"path": e["path"], "op": e["op"], "actor": e.get("actor"), "t": e.get("t"), "n": e["n"]}
            if e["op"] in _OBJ_OPS:
                it["target"] = e.get("tg") or {}
            else:
                it.update(before=e["first"], after=e["last"])
                if e.get("tg"):
                    it["target"] = e["tg"]
            items.append(it)
        return json.loads(json.dumps({"since": st.since, "run": st.rid, "seq": c["seq"], "more": st.more,
                                      "items": items}))


def listen(fn) -> None:
    """Have ``fn(model, records)`` called after each append() that wrote or spilled records --
    the group headers and records as written (do not change them) -- in the appending thread,
    outside the journal's lock: appends of several threads may reach it out of order (records
    carry ``t`` and ``id``). An exception it raises is logged, never passed on."""
    with _plock:
        if fn not in _listeners:
            _listeners.append(fn)


def unlisten(fn) -> None:
    with _plock:
        if fn in _listeners:
            _listeners.remove(fn)


def _tell(model: str, recs: list) -> None:
    for fn in list(_listeners):
        try:
            fn(model, recs)
        except Exception as exc:
            logger.warning("journal: listener %s failed: %r", getattr(fn, "__name__", fn), exc)


@_safe(None)
def find(model: str, rid, scan: int = 5000) -> dict | None:
    """The record with id ``rid`` -- a change, begin or end record, or a group's newest header --
    among the model's newest ``scan`` records (spilled ones included); None when it is not
    there (older: archived past the scan; or no such id)."""
    rid = str(rid or "")
    if not rid:
        return None
    it, n = _records(_dir(model)), 0
    try:
        for r in it:
            if r.get("id") == rid:
                return r
            n += 1
            if n >= scan:
                break
    finally:
        it.close()
    return None


_STAMP = re.compile(r"^[a-z](\d{8}-\d{6})")


def _born(rid) -> float | None:
    """When a record or group id was made (new_id's stamp, to the second); None: not one of those."""
    m = _STAMP.match(str(rid or ""))
    try:
        return time.mktime(time.strptime(m.group(1), "%Y%m%d-%H%M%S")) if m else None
    except (ValueError, OverflowError):
        return None


def pick(model: str, ids=None, group=None, scan: int = 5000) -> dict:
    """Exactly the records the window's "Turn into blocks" names: those with the
    ``ids`` given and every record of change group ``group`` -- change, begin and end records,
    oldest first by (t, id); a begin carries ``open`` as page() says it. Searched among the
    model's newest ``scan`` records, spilled and archived ones included; the search ends once
    it is a SLACK of records past the time the oldest id asked for (or its group) was made --
    ids carry it. {"records", "heads": {group id: its newest header} of the groups they belong
    to, "missing": the ids not found, "more": ``scan`` records examined before the search was
    done}. Reads only; never raises: a failure is {"error": why} with nothing found."""
    want = _ids(ids) or set()
    gid = str(group) if group else None
    try:
        return _pick(model, want, gid, max(1, int(scan)))
    except Exception as exc:
        logger.warning("journal: pick of %r failed: %r", model, exc)
        return {"records": [], "heads": {}, "missing": sorted(want), "more": False,
                "error": f"{type(exc).__name__}: {exc}"}


def _pick(model, want: set, gid, scan: int) -> dict:
    folder = _dir(model)
    if not want and not gid:
        return {"records": [], "heads": {}, "missing": [], "more": False}
    born = [_born(x) for x in [*want, *([gid] if gid else [])]]
    floor = None if None in born else min(born) - 60     # (an id of another form: no early end)
    found, heads, need, ended, seen, past, more = {}, {}, set(), set(), 0, 0, False
    it = _records(folder)
    try:
        for r in it:
            kind, rid, k = r.get("kind"), r.get("id"), _key(r)
            if kind == "group":
                if rid and (rid not in heads or k > _key(heads[rid])):
                    heads[rid] = r
                    need.discard(rid)
            elif kind in ("change", "begin", "end"):
                if kind != "begin" and r.get("call"):
                    ended.add(r["call"])          # newest first: a call's end comes before its begin
                if rid not in found and (rid in want or (gid is not None and r.get("group") == gid)):
                    found[rid] = dict(r, open=r.get("call") not in ended) if kind == "begin" else r
                    g = r.get("group")
                    if g and g not in heads:
                        need.add(g)               # its header (the title) is older still
                    b = _born(g)
                    if floor is not None and b is not None:
                        floor = min(floor, b - 60)
            seen += 1
            if gid is None and not need and len(found) == len(want):
                break
            if floor is not None and k[0] < floor:
                past += 1
                if past >= SLACK:
                    break
            if seen >= scan:
                more = True
                break
    finally:
        it.close()
    recs = sorted(found.values(), key=_key)
    groups = {r.get("group") for r in recs if r.get("group")} | ({gid} if gid else set())
    return {"records": recs, "heads": {g: heads[g] for g in groups if g in heads},
            "missing": sorted(want - set(found)), "more": more}


# ---------------------------------------------------------------------------- the window's timeline
def _key(r: dict) -> tuple:
    t = r.get("t")
    return float(t) if isinstance(t, (int, float)) else 0.0, str(r.get("id") or "")


def _cursor(c, after: bool = False) -> tuple | None:
    """(t, id) of a page cursor: a record, a [t, id] pair or a time -- with ``after`` a bare
    time means records later than it, else records earlier than it. None stays None."""
    if c is None:
        return None
    if isinstance(c, dict):
        return float(c.get("t") or 0), str(c.get("id") or "")
    if isinstance(c, (list, tuple)) and len(c) > 1 and c[1] is not None:
        return float(c[0]), str(c[1])
    t = float(c[0] if isinstance(c, (list, tuple)) else c)
    return t, ("\U0010ffff" if after else "")


def _obj(obj) -> tuple | None:
    """(kind, NAME) of an object filter: ("block", "ESTCOL"), {"kind", "name"}, "block:ESTCOL"."""
    if obj is None or obj == "":
        return None
    if isinstance(obj, dict):
        kind, name = obj.get("kind"), obj.get("name")
    elif isinstance(obj, str):
        kind, _, name = obj.partition(":")
    else:
        kind, name = obj
    if not kind or not name:
        raise ValueError(f"not an object: {obj!r}")
    return str(kind).strip().lower(), str(name).strip().upper()


def _up(x) -> str:
    return "" if x is None else str(x).upper()


def _about(r: dict, kind: str, name: str) -> bool:
    """Whether record ``r`` concerns the object (kind, NAME): a field of it (target.block /
    target.stream ...), it added or removed (target.kind + name), a stream a connect record's
    port held before or after, a path a loop's or optimization's summary wrote."""
    tg = r.get("target")
    if isinstance(tg, dict):
        if _up(tg.get(kind)) == name or (tg.get("kind") == kind and _up(tg.get("name")) == name):
            return True
        if kind == "stream" and r.get("op") == "connect":
            for side in ("before", "after", "displaced"):
                v = r.get(side)
                if isinstance(v, list) and any(_up(x) == name for x in v):
                    return True
    ws = r.get("writes")
    return isinstance(ws, dict) and any(_up(label(split_key(p)[0]).get(kind)) == name for p in ws)


def _records(folder: Path):
    """Every record of a model, spilled ones first, then the files newest first (roughly by
    time: appends from several writers interleave). A file being renamed is retried."""
    yield from _pending(folder)
    yield from _scan(folder, retry=True)


def page(model: str, limit: int = 100, before=None, after=None, actors=None, obj=None,
         scan: int = 5000, note=None, group=None, note_group=None) -> dict:
    """A page of the model's timeline for the workbench window, newest first:
    {"records": up to ``limit`` change and begin records, "groups": {id: the newest header of
    each group those records belong to}, "more": bool, "scanned": n, "cursor": [t, id] | None}.
    A begin record carries ``open``: true when no later record of its call was seen (the call
    is still running, or the server died in it: "started, no end recorded"), else false.

    ``before`` / ``after`` (a record, [t, id] or a time) keep only records older / newer:
    pass the last page's ``cursor`` as ``before`` for the next page, the newest record shown
    as ``after`` for what came since (``more`` then: more new records than ``limit`` -- load
    the first page again). ``actors``: only these (a list or one); ``obj``: only records about
    ("block", "ESTCOL") / {"kind", "name"} / "stream:FEED" (see _about); ``group``: only
    records of this group (an id or a list); ``note``: only what an Ask AI note led to -- the
    records of the groups whose header names that note, and of the programs those groups
    started (header ``ai_group``), found among the newest ``scan`` records; ``note_group``: the
    group the server put on the note, counted with them even where no header names the note.
    Filters combine.
    At most ``scan`` records are examined: when that ends the search, ``more`` is true and
    ``cursor`` is where it stopped, so the next page searches on from there. A group's header
    on an earlier page is looked for up to ``scan`` records further. Reads only; never raises: a failure is
    {"error": why} with an empty page."""
    try:
        return _page(model, limit, before, after, actors, obj, scan, note, group, note_group)
    except Exception as exc:
        logger.warning("journal: page of %r failed: %r", model, exc)
        return {"records": [], "groups": {}, "more": False, "scanned": 0, "cursor": None,
                "error": f"{type(exc).__name__}: {exc}"}


def _ids(x) -> set | None:
    return None if x is None else {str(x)} if isinstance(x, (str, int)) else {str(g) for g in x}


def _noted(folder: Path, note: str, scan: int, also=None) -> set:
    """The groups an Ask AI note led to, by the headers among the newest ``scan`` records:
    those naming the note (and ``also``, the group the server put on it), and the programs
    they started (``ai_group``)."""
    heads, it = {}, _records(folder)
    try:
        for i, r in enumerate(it):
            gid = r.get("id") if r.get("kind") == "group" else None
            if gid and (gid not in heads or _key(r) > _key(heads[gid])):
                heads[gid] = r
            if i + 1 >= scan:
                break
    finally:
        it.close()
    out = {g for g, h in heads.items() if str(h.get("note") or "") == note} | ({str(also)} if also else set())
    more = {g for g, h in heads.items() if h.get("ai_group") in out}
    while more - out:
        out |= more
        more = {g for g, h in heads.items() if h.get("ai_group") in out}
    return out


def _page(model, limit, before, after, actors, obj, scan, note=None, group=None, note_group=None) -> dict:
    folder = _dir(model)
    limit, scan = max(1, int(limit)), max(1, int(scan))
    hi, lo = _cursor(before), _cursor(after, after=True)
    who = None if not actors else {actors} if isinstance(actors, str) else {str(a) for a in actors}
    o = _obj(obj)
    gids = _ids(group)
    nids = None if note is None else _noted(folder, str(note), scan, note_group)
    heads, hits, seen, past, low, stop, ended = {}, [], 0, 0, None, None, set()
    it = _records(folder)
    try:
        for r in it:
            k, kind = _key(r), r.get("kind")
            if kind == "group":                   # headers from anywhere: a retitle is newer than its group
                gid = r.get("id")
                if gid and (gid not in heads or k > _key(heads[gid])):
                    heads[gid] = r
            elif kind in ("change", "end") and r.get("call"):
                ended.add(r["call"])              # (also past the page: a call's end is newer than its begin)
            if hi is not None and k >= hi:
                continue
            seen += 1
            low = k if low is None or k < low else low
            if lo is not None and k <= lo:
                past += 1
                if past >= SLACK:                 # well past the newest one shown: nothing new left
                    stop = "past"
                    break
            elif kind in PAGE_KINDS and (who is None or r.get("actor") in who) and (o is None or _about(r, *o)) \
                    and (gids is None or r.get("group") in gids) and (nids is None or r.get("group") in nids):
                hits.append(r)
                if len(hits) >= limit + SLACK:
                    stop = "full"
                    break
            if seen >= scan:
                stop = "cap"
                break
        hits.sort(key=_key, reverse=True)
        recs = hits[:limit]
        for r in recs:
            if r.get("kind") == "begin":
                r["open"] = r.get("call") not in ended
        if len(hits) > limit:
            cursor = _key(recs[-1])
        elif stop == "cap":
            cursor = low
        else:
            cursor = _key(recs[-1]) if recs else None
        want = {r.get("group") for r in recs if r.get("group")}
        need, extra = want - set(heads), 0
        if need:
            for r in it:
                extra += 1
                if r.get("kind") == "group" and r.get("id") in need:
                    heads[r["id"]] = r
                    need.discard(r["id"])
                if not need or extra >= scan:
                    break
    finally:
        it.close()
    return {"records": recs, "groups": {g: heads[g] for g in want if g in heads},
            "more": len(hits) > limit or stop == "cap", "scanned": seen,
            "cursor": list(cursor) if cursor else None}


_HEAD = ("v", "kind", "id", "t", "srv", "model", "session", "actor", "via", "group", "call", "tool",
         "op", "do", "reason")


@_safe(dict)
def latest_by_path(model: str, obj, per: int = 5, scan: int = 2000) -> dict:
    """The inspector's history of one object: {lower-cased path: [its newest ``per`` changes,
    newest first]} among the model's last ``scan`` change records (Aspen paths are
    case-insensitive: look a row up by its path in lower case). A value change as recorded;
    a loop's or an optimization's write to a field as a record of its own (op "summary", with
    that field's target, before and after, and ``n`` writes)."""
    o, out = _obj(obj), {}
    for r in read(model, limit=scan, kinds=("change",)):
        if r.get("status") != "changed" or not _about(r, *o):
            continue
        tg = r.get("target") if isinstance(r.get("target"), dict) else {}
        if r.get("op") == "value" and tg.get("path"):
            items = [(tg["path"], r)]
        elif isinstance(r.get("writes"), dict):
            head = {k: r[k] for k in _HEAD if k in r}
            items = []
            for p, w in r["writes"].items():
                t = label(p)
                if split_key(p)[1] is None and isinstance(w, dict) and w.get("status") == "changed" \
                        and _up(t.get(o[0])) == o[1]:
                    items.append((p, {**head, "target": t, "before": w.get("before"), "after": w.get("after"),
                                      "n": w.get("n")}))
        else:
            continue
        for p, rec in items:
            lst = out.setdefault(str(p).lower(), [])
            if len(lst) < per:
                lst.append(rec)
    return out


NET_SCAN, NET_TOP = 5000, 20           # records net() reads at most; inputs and results it lists at most


@_safe(dict)
def net(model: str, after=None, group=None, scan: int = NET_SCAN) -> dict:
    """Before -> now over part of a model's timeline: the records newer than ``after`` (a page
    cursor), or of ``group``; see ``net_of``. The window's "while you were away" line and a
    change group's card say with it what a stretch of work did to the results."""
    p = page(model, limit=scan, scan=scan, after=after, group=group)
    out = net_of(p.get("records") or [])
    if p.get("more"):
        out["partial"] = True
    return out


def net_of(records) -> dict:
    """What some records did, net: {"inputs": [{"target": {"path"}, "before" (the first
    change's), "after" (the last's), "actor" (the last), "n", "back": it ended where it began}],
    "results": [{"path", "b" (the earliest measured run's before), "a" (the latest one's after),
    "u", "runs" (runs that moved it), "cut": a run in between listed less than moved (runlog
    keeps the ITEMS_MAX that moved most), so it may have moved there too, "back": b equals a,
    "small": within Aspen's tolerances every time}], "runs": runs measured, "seqs": [first, last],
    "partial": a result may be off (a cut, a run with no delta)}. Values, and the fields loops
    and optimizations left changed, count as inputs; the results chain the runs' deltas, the
    latest run's order first (products first, most moved first). NET_TOP of each."""
    recs = sorted((r for r in records or () if isinstance(r, dict) and r.get("kind", "change") == "change"), key=_key)
    ins: dict = {}

    def put(path, b, a, actor):
        k = str(path).lower()
        e = ins.get(k)
        if e is None:
            e = ins[k] = {"target": {"path": str(path)}, "before": _copy(b), "after": None, "actor": None, "n": 0}
        e["after"], e["actor"], e["n"] = _copy(a), actor, e["n"] + 1

    runs, seqs, partial = [], [], False
    for r in recs:
        op, st, tg = r.get("op"), r.get("status"), r.get("target") if isinstance(r.get("target"), dict) else {}
        if op in ("value", "attr") and st == "changed" and tg.get("path") and "before" in r:
            put(tg["path"], r.get("before"), r.get("after"), r.get("actor"))
        elif op in ("summary", "restore") and isinstance(r.get("writes"), dict):
            for p, w in r["writes"].items():
                if split_key(p)[1] is None and isinstance(w, dict) and w.get("status") == "changed" and "before" in w:
                    put(p, w.get("before"), w.get("after"), r.get("actor"))
        elif op == "run" and st in RAN:
            d = r.get("delta")
            if isinstance(r.get("seq"), int):
                seqs.append(r["seq"])
            if not isinstance(d, dict):
                partial = True                     # a run nothing measured: the chain has a gap
            elif not d.get("first"):
                runs.append(d)
    res, first, cuts = {}, {}, []
    for i, d in enumerate(runs):
        items = [x for x in d.get("items") or [] if isinstance(x, dict) and x.get("path")]
        cuts.append(int(d.get("n") or 0) > len(items) or bool(d.get("partial")))
        listed = set()
        for x in items:
            k = str(x["path"]).lower()
            listed.add(k)
            e = res.get(k)
            if e is None:
                e = res[k] = {"path": str(x["path"]), "b": x.get("b"), "a": None, "runs": 0, "small": True, "cut": False}
                first[k] = i
            e["a"], e["runs"], e["small"] = x.get("a"), e["runs"] + 1, e["small"] and bool(x.get("small"))
            if x.get("u"):
                e["u"] = x["u"]
        if cuts[-1]:
            for k, e in res.items():               # moved before, maybe again here, not listed
                if k not in listed:
                    e["cut"] = True
    for k, e in res.items():                       # a cut run before it first shows: it may have moved there
        e["cut"] = e["cut"] or any(cuts[:first[k]])
    order: dict = {}
    for d in reversed(runs):                       # the latest run's order first
        for x in d.get("items") or []:
            if isinstance(x, dict) and x.get("path"):
                order.setdefault(str(x["path"]).lower(), len(order))
    results = []
    for k in sorted(res, key=lambda k: order.get(k, len(order))):
        e = res[k]
        e["back"] = _same(e["b"], e["a"])
        if not e["small"]:
            del e["small"]
        results.append(e)
    inputs = []
    for e in ins.values():                         # (in the order first changed)
        b, a = e["before"], e["after"]
        vb, va = (b.get("value") if isinstance(b, dict) else b), (a.get("value") if isinstance(a, dict) else a)
        ub, ua = (b.get("unit") if isinstance(b, dict) else None), (a.get("unit") if isinstance(a, dict) else None)
        e["back"] = _same(vb, va) and ub == ua
        inputs.append(e)
    partial = partial or any(e["cut"] for e in results)
    return {"inputs": inputs[:NET_TOP], "results": results[:NET_TOP], "runs": len(runs),
            "seqs": [min(seqs), max(seqs)] if seqs else [], "partial": partial}


SUS_SCAN, SUS_MAX = 5000, 20           # records suspects() reads at most; items (and struct) it lists at most
GOOD = frozenset({"ok", "warn"})       # a run record's status when the run ran and succeeded


def _good(r: dict) -> bool:
    return r.get("op") == "run" and r.get("status") in GOOD


def _brief(r: dict | None) -> dict | None:
    return None if r is None else {k: r[k] for k in ("id", "t", "op", "status", "seq", "actor", "via", "first_error",
                                                     "first_warn") if r.get(k) is not None}


def _objs_of(e: dict) -> list:
    """(kind, NAME) of the objects a _Net entry is about: a field's block or stream, the object
    added or removed, a port's block and the streams it held before or after."""
    op, tg = e["op"], e.get("tg") or {}
    if op in ("value", "attr"):
        lab = label(e["path"])
        return [(k, _up(lab[k])) for k in ("block", "stream") if lab.get(k)]
    if op in _OBJ_OPS:
        return [(str(tg["kind"]).lower(), _up(tg["name"]))] if tg.get("kind") and tg.get("name") else []
    out = [("block", _up(tg["block"]))] if tg.get("block") else []
    for side in (e.get("first"), e.get("last")):
        out += [("stream", _up(s)) for s in side] if isinstance(side, list) else []
    return out


def suspects(model: str, run=None, on=None, upstream=None, scan: int = SUS_SCAN, limit: int = SUS_MAX) -> dict:
    """What changed since the model's last good run (the failure card's
    suspects): the records after the newest run that ran and ended ok / warn -- not a loop's or an
    optimization's runs, their summary counts as its net writes -- up to run record ``run`` (an
    id: the failed or refused run the card is about; None: up to now), folded net per target as
    ``stale`` does (``_args`` / ``_writes`` / ``_differs``: changed and changed back is no change;
    changes made in Aspen's window count, actor ``external``).

    {"state": "ok" | "none_since" (a good run, nothing changed since) | "never_ok" (no good run
    among the newest ``scan`` records: the changes since the model was last opened, or all of
    them; ``partial`` when the scan ended first) | "journal_off", "since": the good run's (or
    that open's) {"id", "t", "op", "status", "seq", "actor", "via"} | None, "run": that of
    ``run``, else of the newest run after ``since`` (and its ``first_error``, tools/probes) |
    None, "items": value / attribute changes
    [{"rec": the latest record's id, "path", "op", "attr"?, "before" (before the first change),
    "after" (after the last), "actor", "t", "n", "on_block", "upstream"}], "struct": structure
    changes [{"rec", "op" add | remove | connect | restore, "path", "kind", "name", "type" |
    "block", "port", "before", "after", "actor", "t", "n", "on_block", "upstream"}], "more": how
    many past ``limit`` each were left out, "scanned"}.

    ``on``: the failing blocks' names; ``upstream``: the objects upstream of them, ("block",
    "B1") / "stream:FEED" / {"kind", "name"} (tools/diagnose.upstream) -- the changes on a failing
    block first, then those upstream, then the rest, each part newest first. Reads only; stdlib;
    never raises (a failure is {"state": "error", "error"})."""
    empty = {"since": None, "run": None, "items": [], "struct": [], "more": 0}
    if not enabled():
        return {"state": "journal_off", **empty}
    try:
        return _suspects(model, str(run) if run else None, on, upstream, max(1, int(scan)), max(1, int(limit)))
    except Exception as exc:
        logger.warning("journal: suspects of %r failed: %r", model, exc)
        return {"state": "error", **empty, "error": f"{type(exc).__name__}: {exc}"}


def _suspects(model, rid, on, upstream, scan, limit) -> dict:
    recs, anchor, stop, n, capped = [], None, None, 0, False
    it = _records(_dir(model))
    try:
        for r in it:
            n += 1
            if r.get("kind") == "change":
                recs.append(r)
                if rid is not None and anchor is None and r.get("id") == rid:
                    anchor = r
                if stop is None and _good(r) and (rid is None or (anchor is not None and _key(r) < _key(anchor))):
                    stop = n + SLACK               # appends interleave: read a little past it
            if stop is not None and n >= stop:
                break
            if n >= scan:
                capped = True
                break
    finally:
        it.close()
    recs.sort(key=_key)
    if anchor is not None:
        recs = [r for r in recs if _key(r) < _key(anchor)]
    good = [i for i, r in enumerate(recs) if _good(r)]
    if good:
        i0 = good[-1]
    else:
        opens = [i for i, r in enumerate(recs) if r.get("op") == "open" and r.get("status") not in _NO_CHANGE]
        i0 = opens[-1] if opens else -1
    since, window = (recs[i0] if i0 >= 0 else None), recs[i0 + 1:]
    last_run = anchor or next((r for r in reversed(window) if r.get("op") == "run"), None)
    net, restores = _Net(), []
    for r in window:
        t = r.get("t") if isinstance(r.get("t"), (int, float)) else None
        if _put_back(r):
            restores.append({"rec": r.get("id"), "op": "restore", "kind": "checkpoint",
                             "name": _dict(r, "target").get("checkpoint"), "actor": r.get("actor"), "t": t, "n": 1})
            continue
        if r.get("op") in ("summary", "restore"):
            puts = list(_writes(r, t))
        elif r.get("status") in _NO_CHANGE:
            continue
        else:
            args, gone = _args(r, t)
            if args is None:
                continue
            if gone:
                net.drop(gone)
            puts = [args]
        for args in puts:
            net.put(*args)
            e = net.d.get(args[0])
            if e is not None:
                e["rec"] = r.get("id")
    fail = {("block", _up(x)) for x in on or ()}
    up = set()
    for x in upstream or ():
        try:
            o = _obj(x)
        except (ValueError, TypeError):
            continue
        if o:
            up.add(o)
    items, struct = [], []
    for key, e in net.changes():
        objs = _objs_of(e)
        x = {"rec": e.get("rec"), "path": e["path"], "op": e["op"], "actor": e.get("actor"), "t": e.get("t"),
             "n": e["n"], "on_block": any(o in fail for o in objs), "upstream": any(o in up for o in objs)}
        if e["op"] in ("value", "attr"):
            if e["op"] == "attr" and split_key(key)[1] is not None:
                x["attr"] = str(split_key(key)[1])
            x.update(before=e["first"], after=e["last"])
            items.append(x)
        else:
            x.update(e.get("tg") or {})
            if e["op"] == "connect":
                x.update(before=e["first"], after=e["last"])
            struct.append(x)
    struct += [dict(x, on_block=False, upstream=False) for x in reversed(restores)]

    def rank(x):
        return 0 if x["on_block"] else 1 if x["upstream"] else 2

    items.sort(key=rank)
    struct.sort(key=rank)
    more = max(0, len(items) - limit) + max(0, len(struct) - limit)
    state = ("ok" if items or struct else "none_since") if good else "never_ok"
    out = {"state": state, "since": _brief(since), "run": _brief(last_run), "items": items[:limit],
           "struct": struct[:limit], "more": more, "scanned": n}
    if capped and not good:
        out["partial"] = True
    return json.loads(json.dumps(out, default=str))


@_safe(None)
def digest(model: str, limit: int = 3, per: int = 20, cap: int = DIGEST_MAX, name=None) -> dict | None:
    """The newest ``limit`` change groups of a model as short lines for the AI (workbench_read's
    ``changes``): {"model", "total", "groups": [{"id", "actor", "title", "t0", "t1", "n",
    "lines"}], "note"}, newest group first, each group's lines oldest first; past ``cap``
    characters of lines a group's oldest go first (counted in a "..." line), and no group
    starts once the cap is reached. ``name(path)``: a field in words (else its owner and code)."""
    out = {"model": model, "total": (summary(model) or {}).get("n", 0), "groups": [],
           "note": "values measured by the server; reason = the AI's own words"}
    left = cap
    for g in groups(model, limit=limit, per=per, scan=1000):
        recs, keep = g["lines"], []
        for r in reversed(recs):
            s = line(r, name)
            if keep and len(s) > left:
                break
            keep.append(s)
            left -= len(s)
        shown = sum(r.get("kind") == "change" for r in recs[len(recs) - len(keep):])
        keep.reverse()
        if g["n"] > shown:
            keep.insert(0, f"... {g['n'] - shown} earlier change(s) not shown")
        who = str(g.get("actor") or "?") + (", started by the AI" if g.get("ai_group") else "")
        out["groups"].append({"id": g["id"], "actor": who, "title": g.get("title") or _auto_title(g["ops"]),
                              "t0": _clock(g["t0"], "%Y-%m-%d %H:%M"), "t1": _clock(g["t1"], "%Y-%m-%d %H:%M"),
                              "n": g["n"], "lines": keep})
        if left <= 0:
            break
    return out


_NOUNS = {"value": "value", "attr": "attribute", "add": "addition", "remove": "removal", "connect": "connection",
          "run": "run", "reinit": "reinit", "save": "save", "patch": "file edit", "open": "open", "close": "close",
          "summary": "loop", "restore": "restore", "analysis": "analysis", "call": "call", "checkpoint": "checkpoint"}


def _auto_title(ops: dict) -> str:
    """A group without a note or reason: what it did, e.g. "3 values, 1 addition"."""
    parts = [f"{n} {_NOUNS.get(op, str(op))}{'s' * (n != 1)}" for op, n in (ops or {}).items() if op]
    return ", ".join(parts) or "no changes"


def _secs(s) -> str:
    """A duration as people say it: "3 s", "2 min" (None: "?")."""
    if not isinstance(s, (int, float)):
        return "?"
    return f"{max(1, round(s))} s" if s < 90 else f"{round(s / 60)} min"


def _clock(t, fmt="%H:%M") -> str | None:
    return time.strftime(fmt, time.localtime(t)) if isinstance(t, (int, float)) else None


def _val(x) -> str:
    """A measured {"value", "unit"} as text."""
    if not isinstance(x, dict):
        return "?" if x is None else _cut(str(x), 60)
    v = x.get("value")
    s = f"{v:.6g}" if isinstance(v, float) else "(empty)" if v is None else _cut(str(v), 60)
    return f"{s} {x['unit']}" if x.get("unit") else s


def _where(t, name=None) -> str:
    """A record's target as people say it: ESTCOL BASIS_RR -- with ``name(path)``, e.g.
    ESTCOL › Reflux ratio [BASIS_RR] --, block B4 (RADFRAC), FL F(IN)."""
    if not isinstance(t, dict):
        return ""
    if t.get("kind") and t.get("name"):
        return f"{t['kind']} {t['name']}" + (f" ({t['type']})" if t.get("type") else "")
    field = t.get("field")
    if name is not None and field and t.get("attr") is None and str(t.get("path") or "").lower().startswith("\\data\\"):
        return name(t["path"])
    if t.get("attr") is not None:
        field = f"{field} attribute {t['attr']}"
    owner = next((t[k] for k in ("block", "stream", "rxnset", "chemistry", "name", "component") if t.get(k)), None)
    text = " ".join(str(x) for x in (owner, field) if x)
    return text or _base(t.get("path") or t.get("file"))


def _base(path) -> str:
    return re.split(r"[\\/]", str(path or ""))[-1]


@_safe(lambda *a, **k: "(a record that could not be shown)")
def line(r: dict, name=None) -> str:
    """One record as a line for the AI: when, who (actor and tool), what -- before -> after as
    measured -- and the reason the AI gave. ``name(path)``: a field in words."""
    who = " ".join(str(x) for x in (r.get("actor"), r.get("tool")) if x)
    text = f"{_clock(r.get('t')) or '--:--'} {who} {what(r, name)}"
    if r.get("reason"):
        text += f" · reason: {_cut(str(r['reason']), 160)}"
    return _cut(text, 320)


def is_disconnect(r: dict) -> bool:
    """A ``connect`` record that took its stream off the port: ``target.stream`` on the port
    before, not after (disconnect_stream, a program's disconnect, an undo's) -- not ``detached``,
    which a refused connect did."""
    tg = r.get("target") if isinstance(r.get("target"), dict) else {}
    s = str(tg.get("stream") or "").upper()

    def on(k):
        v = r.get(k)
        return {str(x).upper() for x in v if x is not None} if isinstance(v, list) else set()
    return bool(s) and r.get("op") == "connect" and not r.get("detached") and s in on("before") \
        and s not in on("after")


def what(r: dict, name=None) -> str:
    """What a record did, as line() says it after who did it."""
    op, st, tg = r.get("op"), r.get("status"), r.get("target")
    where, bad = _where(tg, name), st in ("failed", "refused", "error")
    if r.get("kind") == "begin":
        return _began(r, where)
    elif op in ("value", "attr"):
        if st == "changed" and "before" in r:
            did = f"{where} {_val(r['before'])} → {_val(r.get('after'))}"
        else:
            did = f"{where} = {_val(r.get('after') if st != 'failed' else r.get('req'))}" + \
                  (" (new)" if r.get("created") else " (unchanged)" if st == "unchanged" else "")
    elif op in ("add", "remove"):
        did = f"{'added' if op == 'add' else 'removed'} {where}"
    elif op == "connect" and r.get("detached"):        # probes: a refused connect took it off anyway (V15)
        asked = r.get("asked") if isinstance(r.get("asked"), dict) else {}
        to = " ".join(str(asked[k]) for k in ("block", "port") if asked.get(k))
        did = f"took {(tg or {}).get('stream') or '?'} off {where}" + \
              (f" (connect to {to} refused)" if to else "")
    elif op == "connect" and is_disconnect(r):         # disconnect_stream, a program's, an undo's
        did = f"took {tg['stream']} off {where}"
    elif op == "connect":
        did = f"connected {(tg or {}).get('stream') or ', '.join(map(str, r.get('after') or []))} to {where}" + \
              (f" (took {', '.join(map(str, r['displaced']))} off)" if r.get("displaced") else "")
    elif op in RUN_OPS:
        counts = [f"{r[k]} {k}" for k in ("errors", "warnings") if r.get(k)]
        did, bad = f"{op}: {st}" + (f" ({', '.join(counts)})" if counts else ""), st in ("failed", "refused")
    elif op == "checkpoint" and st == "skipped":       # tools/restore_points.py: none made
        why = {"slow": f"saving one takes about {_secs(r.get('est_s'))}", "failed": "it could not be saved",
               "no_session": "the model is not open"}.get(r.get("why"), str(r.get("why") or "?"))
        did = f"no restore point before this: {why}"
    elif op == "checkpoint" and r.get("reuse"):
        did = f"restore point {r['reuse']} still holds the model (nothing changed since)"
    elif op in ("save", "checkpoint"):
        did = f"{'saved' if op == 'save' else 'checkpoint of'} {where}".rstrip()
    elif op == "patch":
        did = ("redrew the flowsheet drawing" if r.get("tool") == "layout_flowsheet" else "edited the model file") \
            + (", Aspen reopened" if r.get("reopened") else "")
    elif op in ("open", "close"):
        did = ("opened " if op == "open" else "closed ") + _base(r.get("file") or r.get("session"))
    elif op == "restore" and isinstance(tg, dict) and tg.get("checkpoint"):
        did, bad = _restored(r, tg), False
    elif op in ("summary", "restore"):
        did = _loop(r, where, name)
    elif op == "proposal" and r.get("status") == "deleted":   # its record deleted from History
        did = f"deleted the record of the AI's proposal '{r.get('title')}' (tab {r.get('tab')})"
    elif op == "proposal" and r.get("proposal"):     # the user sent the AI's proposal back
        c = " ".join(str(r.get("comment") or "").split())
        did = f"sent back the AI's proposal '{r.get('title')}' (tab {r.get('tab')})" + \
            (f": \"{_cut(c, 120)}\"" if c else "")
    else:                          # "call": the tool's own record (nothing measured), or another op
        did = (where if op in (None, "call") else f"{op} {where}").strip() + \
            (" (no change)" if st == "unchanged" else "")
    if bad:
        did += f" -- {st}" + (f": {_cut(' '.join(str(r['result']).split()), 120)}" if r.get("result") else "")
    return did


# what a restore point was kept before (tools/restore_points.py ``reason``), as a line says it
CP_REASONS = {"before-structure": "before a structural change", "before-optimize": "before an optimization",
              "before-proposal": "before a proposal ran", "before-restore": "saved before a restore",
              "before-patch": "before a file edit", "before-overwrite": "the file before it was overwritten",
              "manual": "a restore point"}


def _restored(r: dict, tg: dict) -> str:
    """A restore of the whole model to a restore point: which one, and that what came after
    it is gone -- or, failed, that the model was put back as it was."""
    name = tg.get("name") or CP_REASONS.get(tg.get("reason"), "a restore point")
    when = _clock(tg.get("t"), "%m-%d %H:%M")
    point = f'restore point "{_cut(str(name), 60)}"' + (f" ({when})" if when else "")
    if r.get("status") == "changed":
        return f"restored the whole model to {point}: blocks, streams and inputs as they were then; " \
               "later changes are gone"
    err = f": {_cut(' '.join(str(r['result']).split()), 100)}" if r.get("result") else ""
    now = {"before_cp": "the point saved just before", "original": "its file"}.get(r.get("now"))
    return f"could not restore the model to {point}{err}" + (f" -- reopened from {now}, as it was" if now else "")


def _began(r: dict, where: str) -> str:
    """A begin record: what started ("sweep of FEED TEMP", "program "Heat it""), and, marked
    ``open`` by the reader, that nothing ended it: still running when this process wrote it
    (it is alive, so the end is still to come), else no end recorded (the server that wrote it
    died, or another one is still running it)."""
    do = r.get("do") if r.get("do") not in (None, r.get("tool")) else None   # (optimizer optimize ...)
    text = " ".join(x for x in (do, f'"{_cut(str(r["title"]), 60)}"' if r.get("title") else None) if x)
    if where:
        text = f"{text} of {where}".strip()
    text = f"{text} started".strip()
    if r.get("open"):
        text += ", still running" if r.get("srv") == srv() else ", no end recorded"
    return text


def _loop(r: dict, where: str, name=None) -> str:
    """A summary record (a loop, an optimize, a program's restore)."""
    do, n, rep, runs = r.get("do") or r.get("op"), r.get("n"), r.get("report") or {}, r.get("runs") or {}
    if r.get("op") == "restore":
        text = f"restored {n or 0} value(s)"
    else:
        text = f"{do} of {where}" if where else str(do)
        text += f": {n} writes" if n else ""
        if isinstance(r.get("range"), list) and len(r["range"]) == 2:
            text += f" over {_val({'value': r['range'][0]})}..{_val({'value': r['range'][1]})}"
    if runs.get("n"):
        text += f", {runs['n']} runs ({runs.get('ok', 0)} ok)"
    if rep.get("evaluations") is not None:
        text += f"; {rep['evaluations']} evaluations, {rep.get('feasible', '?')} feasible"
        if rep.get("finish"):
            text += f", finished at {rep['finish']}"
    ws = r.get("writes") if isinstance(r.get("writes"), dict) else {}
    if len(ws) == 1:
        (path, w), = ws.items()
        text += f"; {_where(label(path), name)} {_val(w.get('before'))} → {_val(w.get('after'))}"
    elif ws:
        text += f"; {len(ws)} fields"
    return text


@_safe(dict)
def usage() -> dict:
    """{"root", "models", "bytes", "on"} of the journal folder, for ``aspen-mcp --check``."""
    base = Path(ROOT) / "journal"
    dirs = [d for d in base.iterdir() if d.is_dir()] if base.is_dir() else []
    return {"root": str(base), "models": len(dirs), "on": enabled(),
            "bytes": sum(max(0, _size(f)) for d in dirs for f in d.iterdir())}


# ---------------------------------------------------------------------------- groups
_SPLIT: list = []                      # fn(new group id, the AI's group it split off): on_split


def on_split(fn) -> None:
    """Have ``fn(new, old)`` called when a failed run's diagnose group splits the AI's live group
    ``old`` (Groups.ai), so what was granted for ``old`` -- the user's mute of a stuck rule, a
    class of risky calls let through -- goes on for ``new``: it is the same request."""
    if fn not in _SPLIT:
        _SPLIT.append(fn)


def _note(x):
    if isinstance(x, dict):
        return None if x.get("id") is None else \
            {"id": str(x["id"]), "text": x.get("text"), "session": x.get("session")}
    return {"id": str(x), "text": None, "session": None} if isinstance(x, (str, int)) and str(x) else None


class Groups:
    """Which change group a record joins, in memory, one per server process.

    ai: a new group when the Ask AI note changes, when the AI was idle more than IDLE_S
    since its last tool call *ended* (a long run does not split a group), or once its note
    was answered ``done`` (``close``); titled by the note, else by the first ``reason``.
    user: a new group after IDLE_S between hand edits. own: a group for one action on its own
    (a named restore point, a restore). revert: a group for one undo, ``of`` what it takes back.
    program: one group per run.
    external (changes found made in Aspen's own window): as user, per session.
    The optimizer has none: its records join the AI's or the program's group.
    diagnose: a run that failed or was refused (``after_run``, from the run records
    append writes) has the AI's next change -- not a read, not another run -- start a group of
    its own, source "diagnose", titled "Diagnose and fix: <the failing blocks>" (``label`` those names;
    ``diag`` {"run", "status", "from": the group it split off}) -- the AI's corrections, apart,
    with what the user granted that group (``on_split``). It ends at the next run that ends ok /
    warn, or idle as any. An Ask AI note comes first: while one is open the AI's changes stay in
    its group."""

    def __init__(self):
        self._lock = threading.RLock()
        self._diag = None                                 # a failed run the AI's next call is for
        self._ai, self._ref, self._busy, self.note = None, 0.0, 0, None
        self._user, self._user_t = None, 0.0
        self._ext: dict = {}                              # session -> [group, time of its last change]
        self._runs, self._all, self._told = {}, {}, {}   # run -> group; id -> group; id -> {model: title}

    def _new(self, actor, t, **f):
        g = {"id": new_id("g", t), "actor": actor, "t0": t, "title": None, "source": "auto",
             "note": None, "session": None, **f}
        self._all[g["id"]] = g
        while len(self._all) > 256:
            old = next(iter(self._all))
            self._all.pop(old)
            self._told.pop(old, None)
        return g

    @_safe(None)
    def ai(self, t=None, note=None, reason=None, change=True) -> dict | None:
        """The AI's group for a tool call starting at ``t``; call ``end()`` when it ends.
        ``note``: the open Ask AI note ({"id", "text", "session"} or its id), else the last
        one ``note_seen``. ``change``: the call changes the model (tools/intercept: a value,
        structure or batch tool) -- only such a call opens the diagnose group a failed run left
        waiting (a read or another run stays in the group it is in); a split mid-request tells
        ``on_split``'s functions, which carry that group's allowances over."""
        t = now() if t is None else t
        split = None
        with self._lock:
            n, g = _note(note) or self.note, self._ai
            idle = not self._busy and t - self._ref > IDLE_S
            d = self._diag
            if d is not None and (n or t - d["t"] > DIAG_TTL_S):
                d = self._diag = None                     # a note comes first; a stale failure is none
            if not change:
                d = None
            elif d is not None:
                self._diag = None
            if g is None or g.get("closed") or idle or (n and n["id"] != g["note"]) or d is not None:
                prev = g["id"] if g is not None and not g.get("closed") and not idle else None
                g = self._ai = self._new("ai", t, note=n and n["id"], session=n and n.get("session"))
                if n and str(n.get("text") or "").strip():
                    g.update(title=_cut(str(n["text"]).strip(), TITLE_MAX), source="note")
                elif d is not None:
                    label = ", ".join(d["blocks"]) or None
                    g.update(title=_cut(DIAG_TITLE + (f": {label}" if label else ""), TITLE_MAX), source="diagnose",
                             label=label, session=d.get("session"),
                             diag={k: v for k, v in (("run", d.get("run")), ("status", d.get("status")),
                                                     ("from", prev)) if v} or None)
                    split = (g["id"], prev) if prev else None
            if not g["title"] and reason is not None and str(reason).strip():
                g.update(title=_cut(str(reason).strip(), TITLE_MAX), source="reason")
            self._busy += 1
            self._ref = max(self._ref, t)
        if split is not None:
            for fn in list(_SPLIT):
                try:
                    fn(*split)
                except Exception as exc:
                    logger.warning("journal: split listener %s failed: %r", getattr(fn, "__name__", fn), exc)
        return g

    @_safe(None)
    def end(self, t=None) -> None:
        """An AI tool call ended at ``t``: idle time counts from here."""
        t = now() if t is None else t
        with self._lock:
            self._busy = max(0, self._busy - 1)
            self._ref = max(self._ref, t)

    @_safe(None)
    def after_run(self, status, blocks=None, session=None, t=None, run=None) -> None:
        """A run record was written (``append``; any actor's: the AI's, the window's, a
        program's, one found made in Aspen's window). ``status`` error | refused: the AI's next
        call starts a diagnose group (``ai``; ``blocks`` the failing ones, first first, name it)
        -- unless the AI is in one already, or in an open note's group. ok | warn: a diagnose
        group ends (the AI's next call starts another) and a failure still waiting is dropped."""
        t = now() if t is None else t
        with self._lock:
            g = self._ai
            live = g is not None and not g.get("closed") and (self._busy or t - self._ref <= IDLE_S)
            if status in GOOD:
                self._diag = None
                if live and g.get("source") == "diagnose":
                    g["closed"] = True
                return
            if status not in ("error", "refused"):
                return
            if live and (g.get("source") == "diagnose" or (g.get("note") and self.note
                                                             and self.note["id"] == g["note"])):
                return
            names = list(dict.fromkeys(str(b) for b in blocks or () if b))[:DIAG_NAMES]
            self._diag = {"t": t, "blocks": names, "session": session, "run": run, "status": status}

    def current(self) -> dict | None:
        """The AI's group now, changing nothing (e.g. for a refused call's record)."""
        return self._ai

    @_safe(None)
    def note_seen(self, note_id, text=None, session=None) -> None:
        """An Ask AI note was pushed to the AI (or shown by workbench_read)."""
        with self._lock:
            self.note = _note({"id": note_id, "text": text, "session": session})

    @_safe(False)
    def close(self, note_id=None) -> bool:
        """The note was answered done: the AI's next call starts a new group."""
        nid = None if note_id is None else str(note_id)
        with self._lock:
            if self.note and nid in (None, self.note["id"]):
                self.note = None
            g = self._ai
            if g and not g.get("closed") and (nid is None or g["note"] == nid):
                g["closed"] = True
                return True
            return False

    @_safe(None)
    def user(self, t=None, session=None) -> dict | None:
        """The group of a hand edit at ``t``."""
        t = now() if t is None else t
        with self._lock:
            if self._user is None or t - self._user_t > IDLE_S:
                self._user = self._new("user", t, session=session)
            self._user_t = max(self._user_t, t)
            return self._user

    @_safe(None)
    def own(self, session=None, title=None, source=None, actor="user", t=None) -> dict | None:
        """A new group for one action taken on its own (the window's named restore point, a
        restore): nothing else joins it, and the user's next hand edit starts another. ``title``
        (cut to TITLE_MAX) and ``source`` say what it was."""
        t = now() if t is None else t
        with self._lock:
            g = self._new(actor, t, session=session)
            if title is not None and str(title).strip():
                g["title"] = _cut(str(title).strip(), TITLE_MAX)
            if source:
                g["source"] = str(source)
            if actor == "user":
                self._user = None
            return g

    @_safe(None)
    def revert(self, of=None, session=None, actor="user", t=None, label=None) -> dict | None:
        """A new group for one undo (tools/undo_apply.py): source "revert", ``of`` the group
        it takes back (an id; the ids when it takes back records of several), ``label`` a short
        name of what that was (its title, as the undo found it). Untitled: the reader says
        "undo of <that group's title>" -- ``label`` when it does not have that group's header.
        Nothing else joins it."""
        t = now() if t is None else t
        with self._lock:
            g = self._new(actor, t, session=session, source="revert", of=of or None, label=label or None)
            if actor == "user":
                self._user = None
            return g

    @_safe(None)
    def external(self, t=None, session=None) -> dict | None:
        """The group of a change found made in Aspen's own window at ``t``: a new one
        after IDLE_S between such changes of the session; untitled -- the reader names it."""
        t = now() if t is None else t
        with self._lock:
            cur = self._ext.pop(session, None)
            if cur is None or t - cur[1] > IDLE_S:
                cur = [self._new("external", t, session=session), t]
            cur[1] = max(cur[1], t)
            self._ext[session] = cur                     # the most recent session last
            while len(self._ext) > 32:
                self._ext.pop(next(iter(self._ext)))
            return cur[0]

    @_safe(None)
    def program(self, run=None, title=None, ai_group=None, session=None, t=None, proposal=None,
                proposed_in=None) -> dict | None:
        """The group of one program run (``run`` None: always a new one). ``title``: the
        tab's; ``ai_group``: the AI's group when the AI started it (workbench_run);
        ``proposal``: the AI's proposal the user approved by running it (its
        ``proposed_in``: the AI's group it was written in) -- the user started it, so no
        ``ai_group``. Its end, ``outcome``, goes into the group and a header again
        (workbench_tools)."""
        t = now() if t is None else t
        with self._lock:
            g = self._runs.get(run) if run is not None else None
            if g is None:
                g = self._new("program", t, run=run, ai_group=ai_group, session=session)
                if proposal:
                    g.update(proposal=proposal, proposed_in=proposed_in)
                if title:
                    g.update(title=_cut(str(title), TITLE_MAX), source="tab")
                if run is not None:
                    self._runs[run] = g
                    while len(self._runs) > 32:
                        self._runs.pop(next(iter(self._runs)))
            return g

    def line(self, g: dict) -> dict:
        """The ``group`` header record of ``g``."""
        return entry("group", id=g["id"], t=g["t0"], actor=g["actor"], title=g.get("title"),
                     source=g.get("source"), note=g.get("note"), session=g.get("session"),
                     run=g.get("run"), ai_group=g.get("ai_group"), of=g.get("of"), label=g.get("label"),
                     proposal=g.get("proposal"), proposed_in=g.get("proposed_in"), outcome=g.get("outcome"),
                     diag=g.get("diag"))

    def known(self, gid) -> dict | None:
        """The header of this process's group ``gid`` (one of its last 256), else None."""
        with self._lock:
            g = self._all.get(gid)
            return self.line(g) if g is not None else None

    @_safe(list)
    def headers(self, model: str, recs) -> list[dict]:
        """Headers ``recs`` need in ``model``: groups it has not seen, or retitled since."""
        with self._lock:
            ids = dict.fromkeys(r.get("group") for r in recs if r.get("group"))
            return [self.line(self._all[i]) for i in ids if i in self._all
                    and self._told.get(i, {}).get(model, _UNSEEN) != self._all[i]["title"]]

    @_safe(None)
    def mark(self, model: str, heads) -> None:
        """``heads`` are written (or spilled) in ``model``."""
        with self._lock:
            for h in heads:
                self._told.setdefault(h["id"], {})[model] = h.get("title")


GROUPS = Groups()
