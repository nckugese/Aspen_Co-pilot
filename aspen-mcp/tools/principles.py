"""The principle library: ``docs/principles/<key>.md`` cards, their
``index.md`` and the ``rules.md`` fallback, read from the package (never Aspen, never the AI).

    keys()               the library's keys: listed in index.md and with a card file (None: no library)
    index()              [{key, title {en, zh}}] in index.md's order (catalog.principles)
    card(key)            {key, title {en, zh}, idea, eq, sym {en, zh} each, related [keys], ref} or None
    rules()              [{types [block types], fields [paths under the block], key}] (rules.md's table)
    infer(type, path)    the key the rules give a field of a block of that type, else None

A key is lower-case letters, digits and _ and must be in the index: a card is read only by a name
the index lists, so no request reaches a file outside the folder. Everything is cached by the
files' modification times; the window's Api.principle and the server's catalog share it.
Stdlib only, no I/O at import.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "docs" / "principles"
KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")
_IDX_RE = re.compile(r"^- `([a-z0-9_]+)` -- ([^/\n]+?) / (.+?) --", re.M)
_HEAD_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
_LANG_RE = re.compile(r"^## (zh|en)\n(.*?)(?=^## |\Z)", re.S | re.M)
_LOCK = threading.Lock()
_CACHE: dict = {"idx": None, "cards": {}, "rules": None}


def _mtime(p: Path):
    try:
        return p.stat().st_mtime_ns
    except OSError:
        return None


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def index() -> list[dict]:
    """[{key, title {en, zh}}] of index.md's key lines whose card file exists, in its order."""
    p = ROOT / "index.md"
    t = (_mtime(p), _mtime(ROOT))
    with _LOCK:
        c = _CACHE["idx"]
        if c and c[0] == t:
            return c[1]
        out = []
        if t[0] is not None:
            seen = set()
            for m in _IDX_RE.finditer(_read(p)):
                key, zh, en = m.group(1), m.group(2).strip(), m.group(3).strip()
                if key in seen or not KEY_RE.match(key) or not (ROOT / f"{key}.md").is_file():
                    continue
                seen.add(key)
                out.append({"key": key, "title": {"en": en, "zh": zh}})
        _CACHE["idx"] = (t, out)
        return out


def keys() -> set | None:
    """The library's keys; None when there is no library (a check then judges no key)."""
    if not (ROOT / "index.md").is_file():
        return None
    return {e["key"] for e in index()}


def _fields(text: str) -> dict:
    out = {}
    for line in text.strip().splitlines():
        k, sep, v = line.partition(": ")
        if sep and k.strip():
            out[k.strip()] = v.strip()
    return out


def card(key) -> dict | None:
    """The card of ``key``: {key, title {en, zh}, idea {en, zh}, eq {en, zh}, sym {en, zh},
    related [keys of the library, at most 3], ref (one line, "" none)}; None for a key that is not
    well formed or not in the index (never a file read by any other name)."""
    key = str(key or "")
    if not KEY_RE.match(key) or key not in (keys() or ()):
        return None
    p = ROOT / f"{key}.md"
    t = _mtime(p)
    with _LOCK:
        c = _CACHE["cards"].get(key)
        if c and c[0] == t:
            return c[1]
    m = _HEAD_RE.match(_read(p)) if t is not None else None
    if not m:
        return None
    meta = _fields(m.group(1))
    langs = {g: _fields(body) for g, body in _LANG_RE.findall(m.group(2))}
    lib = keys() or set()
    rel = [k.strip() for k in meta.get("related", "").split(",") if k.strip() in lib and k.strip() != key][:3]
    out = {"key": key, "title": {"en": meta.get("title_en", key), "zh": meta.get("title_zh", key)},
           "related": rel, "ref": meta.get("ref", "")}
    for f in ("idea", "eq", "sym"):
        out[f] = {g: (langs.get(g) or {}).get(f, "") for g in ("en", "zh")}
    with _LOCK:
        _CACHE["cards"][key] = (t, out)
    return out


def rules() -> list[dict]:
    """rules.md's table: [{types, fields, key}] -- a block type and the field set map to one key.
    Fields are the paths under ``\\Data\\Blocks\\{name}\\`` (``Input\\NSTAGE``)."""
    p = ROOT / "rules.md"
    t = _mtime(p)
    with _LOCK:
        c = _CACHE["rules"]
        if c and c[0] == t:
            return c[1]
    out = []
    lib = keys() or set()
    if t is not None:
        for line in _read(p).splitlines():
            cells = [x.strip() for x in line.strip().strip("|").split("|")] if line.startswith("|") else []
            if len(cells) != 3:
                continue
            key = cells[2].strip("` ")
            if key not in lib:
                continue                                  # (the header and the rule line)
            types = [x.strip() for x in cells[0].split(",") if x.strip()]
            fields = [x.strip("` ") for x in cells[1].split(",") if x.strip("` ")]
            if types and fields:
                out.append({"types": types, "fields": fields, "key": key})
    with _LOCK:
        _CACHE["rules"] = (t, out)
    return out


_BLOCK_PATH = re.compile(r"^\\Data\\Blocks\\([^\\]+)\\(.+)$", re.I)


def infer(btype, path) -> str | None:
    """The key rules.md gives a field: its block's type and its path under the block (the field
    itself or a row under it, ``Input\\FRAC\\PURGE``), nothing else; None when none matches."""
    m = _BLOCK_PATH.match(str(path or ""))
    if not m or not btype:
        return None
    field, bt = m.group(2).upper(), str(btype).upper()
    for r in rules():
        if bt in (x.upper() for x in r["types"]) and any(
                field == f.upper() or field.startswith(f.upper() + "\\") for f in r["fields"]):
            return r["key"]
    return None
