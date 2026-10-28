"""The proposal archive (workbench): proposals kept out of state.json, per model.

A model's tab (state.json ``tabs``, kind "model") holds its proposals as sub-tabs while they
are loaded. One the window no longer shows -- the model's tab closed, shelved to History, past
the loaded cap -- is kept here whole, and comes back as it was (tools/workbench_tools.py
``archive_tab`` / ``load_tab``). The model tab's chat is kept here too when it closes, for the
next time that model's tab opens.

    ~/.aspen-mcp/workbench/proposals/<model dir>/
      <tab id>.json   the proposal's tab as state.json held it
      index.json      {"v": 1, "mkey", "entries": [entry], "deleted": [{"tab", "pid", "t"}]}
      model.json      {"v": 1, "mkey", "t", "messages": [...]}: the model tab's chat when it closed

``mkey`` is the model's id (tools/model_registry.py) -- the folder's name -- or "s:<session>"
for a session whose model has no id yet (folder "s-" + 10 hex of its sha1); ``rekey`` moves
those once the id is known. An entry is the caller's (proposals.history_entry: "tab", "pid",
"title", "status", ...); this module keeps it and reads only its "tab". Records go only on
``delete`` (the user's "delete the record"), which leaves a tombstone so a later call naming
the tab can say so. Stdlib only; every write is atomic (a tmp file, then os.replace, retried
while a reader holds the old one) and a failed one raises OSError, so the caller keeps the tab.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
DELETED_KEEP = 200       # tombstones an index keeps
CHAT_KEEP = 50           # chat lines model.json keeps (a tab keeps as many)


def dirname(mkey: str) -> str:
    """The folder a model's records go in: its id, or "s-" + 10 hex for anything else."""
    mkey = str(mkey or "")
    if _SAFE.match(mkey) and not mkey.startswith("s-"):
        return mkey
    return "s-" + hashlib.sha1(mkey.encode("utf-8")).hexdigest()[:10]


def _write(path: Path, data) -> None:
    """``data`` as JSON at ``path``, atomically. OSError when it could not be put in place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for _ in range(20):                                  # the window may be reading it
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    tmp.unlink(missing_ok=True)
    raise OSError(f"could not replace {path}")


def _read(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


class Archive:
    """One workspace's archive under ``root`` (``<workbench>/proposals``)."""

    def __init__(self, root):
        self.root = Path(root)
        self._idx: dict[str, dict] = {}                  # mkey -> its index.json, as read / written
        self._map: dict[str, str] | None = None          # tab id -> mkey (archived)
        self._dead: dict[str, str] = {}                  # tab id -> mkey (deleted)

    # -- reading ---------------------------------------------------------------
    def _dir(self, mkey: str) -> Path:
        return self.root / dirname(mkey)

    def _index(self, mkey: str) -> dict:
        idx = self._idx.get(mkey)
        if idx is None:
            got = _read(self._dir(mkey) / "index.json")
            idx = {"v": 1, "mkey": mkey, "entries": [], "deleted": []}
            if isinstance(got, dict):
                idx["entries"] = [e for e in got.get("entries") or [] if isinstance(e, dict) and _SAFE.match(str(e.get("tab")))]
                idx["deleted"] = [e for e in got.get("deleted") or [] if isinstance(e, dict) and e.get("tab")]
            self._idx[mkey] = idx
        return idx

    def scan(self) -> None:
        """Build the tab id -> model map from every index (once; later writes keep it)."""
        self._map, self._dead = {}, {}
        if not self.root.is_dir():
            return
        for d in self.root.iterdir():
            got = _read(d / "index.json") if d.is_dir() else None
            mkey = got.get("mkey") if isinstance(got, dict) else None
            if not isinstance(mkey, str) or dirname(mkey) != d.name:
                continue
            idx = self._index(mkey)
            for e in idx["entries"]:
                self._map[e["tab"]] = mkey
            for e in idx["deleted"]:
                self._dead[str(e["tab"])] = mkey

    def _m(self) -> dict:
        if self._map is None:
            self.scan()
        return self._map

    def index(self, mkey: str) -> list[dict]:
        """The model's entries, as kept (do not change them)."""
        return self._index(mkey)["entries"]

    def has(self, mkey: str) -> bool:
        self._m()
        return bool(self._index(mkey)["entries"]) or (self._dir(mkey) / "model.json").exists()

    def find(self, tid) -> str | None:
        """The model a tab is archived under, or None."""
        return self._m().get(str(tid or ""))

    def deleted(self, tid) -> str | None:
        """The model whose record of this tab the user deleted, or None."""
        self._m()
        return self._dead.get(str(tid or ""))

    def entry(self, tid) -> dict | None:
        mkey = self.find(tid)
        return next((e for e in self.index(mkey) if e["tab"] == tid), None) if mkey else None

    def load(self, mkey: str, tid: str) -> dict | None:
        """The archived tab, or None (no record, or its file unreadable)."""
        if not _SAFE.match(str(tid or "")):
            return None
        got = _read(self._dir(mkey) / f"{tid}.json")
        return got if isinstance(got, dict) and got.get("id") == tid else None

    # -- writing ---------------------------------------------------------------
    def _put_index(self, mkey: str, idx: dict) -> None:
        _write(self._dir(mkey) / "index.json", idx)
        self._idx[mkey] = idx

    def save(self, mkey: str, tab: dict, entry: dict) -> None:
        """Keep ``tab`` (its file, then its index entry, replacing an older one). OSError."""
        tid = str(tab.get("id") or "")
        if not _SAFE.match(tid):
            raise OSError(f"bad tab id {tid!r}")
        self._m()
        _write(self._dir(mkey) / f"{tid}.json", tab)
        idx = dict(self._index(mkey))
        idx["entries"] = [e for e in idx["entries"] if e["tab"] != tid] + [dict(entry, tab=tid)]
        idx["deleted"] = [e for e in idx["deleted"] if e.get("tab") != tid]
        self._put_index(mkey, idx)
        self._map[tid] = mkey
        self._dead.pop(tid, None)

    def update(self, mkey: str, tid: str, fn, entry_of) -> dict | None:
        """``fn(tab)`` on an archived tab, then kept again (``entry_of(tab)``: its new entry)."""
        tab = self.load(mkey, tid)
        if tab is None:
            return None
        fn(tab)
        self.save(mkey, tab, entry_of(tab))
        return tab

    def remove(self, mkey: str, tid: str, tomb: dict | None = None) -> bool:
        """Take the tab out of the archive (its index entry, then its file): loaded again, or --
        ``tomb`` given -- deleted for good, a tombstone left. Returns whether it was there; an
        id that is not a safe file name (``_SAFE``, as load and save require) is never there."""
        if not _SAFE.match(str(tid or "")):
            return False
        self._m()
        idx = dict(self._index(mkey))
        had = any(e["tab"] == tid for e in idx["entries"])
        idx["entries"] = [e for e in idx["entries"] if e["tab"] != tid]
        if tomb is not None:
            idx["deleted"] = (idx["deleted"] + [dict(tomb, tab=tid)])[-DELETED_KEEP:]
        if had or tomb is not None:
            self._put_index(mkey, idx)
        try:
            (self._dir(mkey) / f"{tid}.json").unlink(missing_ok=True)
        except OSError:
            pass                                          # (not in the index: no longer found)
        if self._map.get(tid) == mkey:
            del self._map[tid]
        if tomb is not None:
            self._dead[tid] = mkey
        return had

    def delete(self, mkey: str, tid: str, pid=None) -> bool:
        return self.remove(mkey, tid, tomb={"pid": pid, "t": time.time()})

    # -- the model tab's chat ------------------------------------------------------
    def chat(self, mkey: str) -> list[dict]:
        got = _read(self._dir(mkey) / "model.json")
        msgs = got.get("messages") if isinstance(got, dict) and got.get("mkey") == mkey else None
        return [m for m in msgs if isinstance(m, dict)][-CHAT_KEEP:] if isinstance(msgs, list) else []

    def save_chat(self, mkey: str, messages: list) -> None:
        _write(self._dir(mkey) / "model.json", {"v": 1, "mkey": mkey, "t": time.time(),
                                                 "messages": list(messages or [])[-CHAT_KEEP:]})

    # -- a model that got its id ---------------------------------------------------
    def rekey(self, old: str, new: str) -> int:
        """Everything kept under ``old`` moves to ``new`` (an untitled session's model got its id):
        records not there already, the tombstones, the chat unless ``new`` has one. Returns how
        many records moved."""
        if old == new or dirname(old) == dirname(new):
            return 0
        self._m()
        src = self._dir(old)
        if not src.is_dir():
            return 0
        a, b = self._index(old), dict(self._index(new))
        have, moved = {e["tab"] for e in b["entries"]}, 0
        for e in a["entries"]:
            if e["tab"] in have:
                continue
            tab = self.load(old, e["tab"])
            if tab is None:
                continue
            _write(self._dir(new) / f"{e['tab']}.json", tab)
            b["entries"] = b["entries"] + [e]
            self._map[e["tab"]] = new
            moved += 1
        b["deleted"] = (b["deleted"] + a["deleted"])[-DELETED_KEEP:]
        for e in a["deleted"]:
            self._dead[str(e["tab"])] = new
        b["mkey"] = new
        self._put_index(new, b)
        chat = src / "model.json"
        if chat.exists() and not (self._dir(new) / "model.json").exists():
            self.save_chat(new, self.chat(old))
        shutil.rmtree(src, ignore_errors=True)
        self._idx.pop(old, None)
        return moved
