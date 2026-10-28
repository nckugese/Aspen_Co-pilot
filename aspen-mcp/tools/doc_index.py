"""Where the docs talk about a field (for the field help cards).

    lookup(type, rel, io=None)   [hit]: the table rows and the mentions of a field
    rows_for(type, kind=None)    [group]: an object type's rows, by file and heading
    scope_of(path)               the scope of a model object's path (SETUP, REACTIONS, ...)
    options(type, rel)           the option codes a field's row lists
    section(hit)                 the text of the part of its file a hit is in (SECTION_MAX)
    palette()                    [(heading, [TYPE])]: blocks/index.md's sections, as Aspen's palette groups them
    build()                      read what changed since the last call (lookup does it too)

Files: the docs shipped with the server -- ``blocks/*.md`` and the object folders (OBJECT_DIRS:
``streams/*.md``, ``reactions/*.md``, ``convergence/*.md``, ...) under DOCS, plus a top-level
TOP_FILES name when one is there -- and what this machine learned, ``~/.aspen-mcp/blocks/*.md``
(USER; src "user", listed first).

A table row whose first cell is a tree path is a template: ``\\Data\\Blocks\\{name}\\Input\\BASIS_RR``,
``\\Data\\Streams\\{name}\\Input\\FLOW\\MIXED\\{comp}``, ``Input\\X`` / ``Output\\X`` inside a block's
file, or a path relative to an object file's ``Root: `\\Data\\...\\{id}` `` line (``Input\\X``,
``Global\\Input\\X``); ``{...}`` and ``#n`` segments match any one segment. A root with ``{kind}``
(flowsheeting.md) stands for every kind SHARED_KINDS lists. Its scope: a block file's type from
the part of its name before the first hyphen (``radfrac.md``, ``radfrac-internals.md`` -> RADFRAC;
``common.md`` -> ``*``, any block), STREAM for a stream path, else the object the path is under
(_split: REACTIONS, CHEMISTRY, DESIGN-SPEC, SENSITIVITY, DATA-FIT-SET, CONVERGENCE, CONV-OPTIONS,
TEAR, SEQUENCE, PROP-SETS, HENRY-COMPS, UTILITIES, SETUP, PROPERTIES, ...). A mention is a line
with a backticked upper-case code (`` `BASIS_RR` ``), kept per (file scope, CODE), at most
MENTION_MAX a file; an object file's scope is its root's, else its folder's (OBJECT_DIRS).

A hit: {"src": "user" | "docs", "file": "blocks/radfrac.md", "heading": the nearest heading
above, "line", "kind": "row" | "mention", "io": "in" | "out" | None, "row": the row's
description, "vtype": its type column and "rel": its path under the object (``Input\\X\\{id}``)
(rows), "text": the line (mentions)}.

Stdlib only; no I/O at import; each file is parsed on first use and again when its mtime or
size changes; nothing here raises -- a file that cannot be read is left out.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DOCS = Path(__file__).resolve().parent.parent / "docs"
USER = None                     # ~/.aspen-mcp at call time (a module attribute so it can be overridden)
TOP_FILES = ("streams.md", "properties.md", "reactions.md")   # the old flat layout, read when present
OBJECT_DIRS = {"setup": "SETUP", "utilities": "UTILITIES", "properties": "PROPERTIES",
               "streams": "STREAM", "reactions": "REACTIONS", "convergence": "CONVERGENCE",
               "flowsheeting": "FLOWSHEETING OPTIONS", "analysis": "MODEL ANALYSIS TOOLS"}
# A root's {kind}: the containers and kinds whose objects share that file's rows (flowsheeting.md's
# define and vary rows work on all of these; analysis/*.md links them).
SHARED_KINDS = {"Flowsheeting Options": (("Flowsheeting Options", ("Design-Spec", "Calculator", "Transfer", "Balance")),
                                         ("Model Analysis Tools", ("Sensitivity", "Optimization", "Constraint"))),
                "Model Analysis Tools": (("Model Analysis Tools", ("Sensitivity", "Optimization", "Constraint")),)}
MENTION_MAX = 5                 # mentions kept per code per file
LOOKUP_MAX = 6                  # hits lookup() returns by default
SECTION_MAX = 1500              # characters section() returns
TEXT_MAX = 300                  # characters of a mention's line / a row's description
STREAM_TYPES = frozenset({"STREAM", "STREAMS", "MATERIAL", "HEAT", "WORK"})
NOT_BLOCKS = frozenset({"STREAM", "REACTIONS", "CHEMISTRY", "PROPERTIES", "COMPONENTS", "SETUP",
                        "CONVERGENCE", "UTILITIES", "FLOWSHEETING OPTIONS", "MODEL ANALYSIS TOOLS",
                        "CONV-OPTIONS", "TEAR", "CONV-ORDER", "SEQUENCE", "PROP-SETS", "PROP-METHODS",
                        "HENRY-COMPS", "COMP-GROUPS", "DESIGN-SPEC", "CALCULATOR", "TRANSFER", "BALANCE",
                        "SENSITIVITY", "OPTIMIZATION", "CONSTRAINT", "DATA-FIT-SET", "DATA-FIT-REGRESSION"})
# (head, second segment) -> (scope, segments before the object's own Input / Output): containers
# whose second level names the object kind; an {id} segment follows when that count is 3.
_KINDS2 = {("Reactions", "Reactions"): ("REACTIONS", 3), ("Reactions", "Chemistry"): ("CHEMISTRY", 3),
           ("Convergence", "Convergence"): ("CONVERGENCE", 3), ("Convergence", "Sequence"): ("SEQUENCE", 3),
           ("Convergence", "Conv-Options"): ("CONV-OPTIONS", 2), ("Convergence", "Tear"): ("TEAR", 2),
           ("Convergence", "Conv-Order"): ("CONV-ORDER", 2),
           ("Components", "Henry-Comps"): ("HENRY-COMPS", 3), ("Components", "Comp-Groups"): ("COMP-GROUPS", 3),
           ("Properties", "Prop-Sets"): ("PROP-SETS", 3), ("Properties", "Property Methods"): ("PROP-METHODS", 3)}

_HEAD = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_CODE = re.compile(r"`([A-Z](?:[A-Z0-9_:\-]*[A-Z0-9])?)`")
_FENCE = re.compile(r"^\s*(```|~~~)")
_ROOT = re.compile(r"^\s*Root:\s*`([^`]+)`")
_OPT = re.compile(r"`([^`\s]+)`")
_IDX = re.compile(r"^#\d+$")
_lock = threading.Lock()
_files: dict = {}               # path -> (stat key, parsed)
_merged: dict = {"key": None, "rows": {}, "mentions": {}, "files": {}}


def _user() -> Path:
    return Path(USER) if USER else Path.home() / ".aspen-mcp"


def _scope(type_) -> str:
    t = str(type_ or "").strip().upper()
    return "STREAM" if t in STREAM_TYPES else t


def _ftype(name: str) -> str:
    """A block file's type: the part before the first hyphen -- radfrac.md / radfrac-internals.md /
    heater-phases.md -> RADFRAC / RADFRAC / HEATER; common.md -> * (no block type has a hyphen)."""
    t = name[:-3] if name.lower().endswith(".md") else name
    t = t.split("-", 1)[0].upper()
    return "*" if t == "COMMON" else t


def _split(path: str, ftype: str | None) -> tuple | None:
    """(scope, io, [segments after Input / Output]) of a tree path or template, as a file of
    type ``ftype`` (a block type, "*", or None) means it; None when it is not a path of a field."""
    segs = [s for s in str(path or "").strip().strip("`").strip().split("\\") if s]
    if not segs:
        return None
    if segs[0].lower() == "data":
        segs = segs[1:]
        if len(segs) < 2:
            return None
        head, k2 = segs[0], _KINDS2.get((segs[0], segs[1]))
        if head == "Blocks":
            scope, rest = (ftype or "*"), segs[2:]
        elif head == "Streams":
            scope, rest = "STREAM", segs[2:]
        elif k2:
            scope, rest = k2[0], segs[k2[1]:]
        elif head == "Model Analysis Tools" and segs[1] == "Data-Fit" and len(segs) >= 4 \
                and segs[2] in ("Data-Set", "Regression"):
            scope, rest = ("DATA-FIT-SET" if segs[2] == "Data-Set" else "DATA-FIT-REGRESSION"), segs[4:]
        elif head in ("Flowsheeting Options", "Model Analysis Tools") and len(segs) >= 3:
            scope, rest = segs[1].upper(), segs[3:]
        elif head == "Utilities":
            scope, rest = "UTILITIES", segs[2:]
        else:
            scope, rest = head.upper(), segs[1:]
    elif segs[0] in ("Input", "Output") and ftype:
        scope, rest = ftype, segs
    else:
        return None
    io_i = next((i for i, s in enumerate(rest) if s in ("Input", "Output")), None)
    io = None if io_i is None else ("in" if rest[io_i] == "Input" else "out")
    tail = rest if io_i is None else rest[io_i + 1:]
    return (scope, io, tail) if tail else None


def _roots(text: str) -> list:
    """An object file's Root line as root templates ("\\Data\\..."), a {kind} one expanded to
    every SHARED_KINDS kind; [] when the file has none."""
    fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            fence = not fence
            continue
        m = None if fence else _ROOT.match(line)
        if not m:
            continue
        segs = [x for x in m.group(1).strip().split("\\") if x]
        if not segs or segs[0].lower() != "data":
            return []
        if len(segs) > 2 and segs[2].lower() == "{kind}":
            return ["\\" + "\\".join([segs[0], cont, kind] + segs[3:])
                    for cont, kinds in SHARED_KINDS.get(segs[1], ()) for kind in kinds]
        return ["\\" + "\\".join(segs)]
    return []


def _absolute(cell: str) -> bool:
    return cell.strip().strip("`").strip().lstrip("\\").lower().startswith("data\\")


def _pattern(tail) -> tuple:
    return tuple("*" if (s.startswith("{") and s.endswith("}")) or _IDX.match(s) else s.upper() for s in tail)


def _cells(line: str) -> list:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _parse(text: str, src: str, rel: str, ftype: str | None, fscope: str) -> dict:
    """{"rows": [(scope, io, pattern, hit)], "mentions": {(scope, CODE): [hit]}, "lines", "heads",
    "scopes": the objects the file is about (its block type, its root's scopes)}.
    An object file (no ``ftype``) with a Root line: its relative rows are read under that root and
    its mentions kept under the root's scope(s) instead of ``fscope``."""
    lines = text.splitlines()
    roots = [] if ftype else _roots(text)
    fscopes = []
    for r in roots:
        sp = _split(r + "\\Input\\X", None)
        if sp and sp[0] not in fscopes:
            fscopes.append(sp[0])
    fscopes = fscopes or [fscope]
    rows, mentions, heads, heading, fence = [], {}, [], None, False
    for i, line in enumerate(lines, 1):
        if _FENCE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        m = _HEAD.match(line)
        if m:
            heading = m.group(2).strip()
            heads.append((i, len(m.group(1))))
            continue
        base = {"src": src, "file": rel, "heading": heading, "line": i}
        cells = _cells(line) if line.lstrip().startswith("|") else []
        first = cells[0] if cells else ""
        if first.startswith("`") and first.endswith("`") and "\\" in first:
            inner = first.strip("`").strip().lstrip("\\")
            if roots and not _absolute(first):
                sps = [_split(r + "\\" + inner, None) for r in roots]
            else:
                sps = [_split(first, ftype)]
            # its path under the object: as written, or an absolute block / stream path's rest
            segs = inner.split("\\")
            orel = (inner if not _absolute(first) else "\\".join(segs[3:])
                    if len(segs) > 3 and segs[1] in ("Blocks", "Streams") else None)
            done = set()
            for sp in sps:
                if not sp or (sp[0], sp[1], tuple(sp[2])) in done:
                    continue
                done.add((sp[0], sp[1], tuple(sp[2])))
                scope, io, tail = sp
                hit = dict(base, kind="row", io=io, row=(cells[-1] if len(cells) > 1 else "")[:TEXT_MAX])
                if io and orel:
                    hit["rel"] = orel
                if len(cells) > 2:
                    hit["vtype"] = cells[1][:TEXT_MAX]
                rows.append((scope, io, _pattern(tail), hit))
            if done:
                continue
        for code in dict.fromkeys(_CODE.findall(line)):
            for fs in fscopes:
                lst = mentions.setdefault((fs, code), [])
                if len(lst) < MENTION_MAX:
                    lst.append(dict(base, kind="mention", io=None, text=line.strip()[:TEXT_MAX]))
    return {"rows": rows, "mentions": mentions, "lines": lines, "heads": heads, "scopes": [ftype] if ftype else fscopes}


def _md_names(folder: Path) -> list:
    try:
        return sorted(e.name for e in os.scandir(folder) if e.is_file() and e.name.lower().endswith(".md")
                      and e.name.lower() != "index.md")
    except OSError:
        return []


def _sources() -> list:
    """[(src, file, relative name, block type or None, mention scope)], this machine's first; the
    shipped object files before the block files, so a stream or Setup row comes from its own doc
    before a block doc that names it."""
    out = []
    for src, root in (("user", _user()), ("docs", Path(DOCS))):
        if src == "docs":
            for d, scope in OBJECT_DIRS.items():
                for n in _md_names(root / d):
                    out.append((src, root / d / n, f"{d}/{n}", None, scope))
            for n in TOP_FILES:
                p = root / n
                if p.is_file():
                    out.append((src, p, n, None, _scope(n[:-3])))
        blocks = root / "blocks"
        for n in _md_names(blocks):
            t = _ftype(n)
            out.append((src, blocks / n, f"blocks/{n}", t, t))
    return out


def _stat(p: Path):
    try:
        st = os.stat(p)
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None


def build() -> dict:
    """Read the files that changed since the last call and merge the index again when any did:
    {"files", "rows", "mentions", "ms", "changed"}."""
    t0 = time.perf_counter()
    with _lock:
        srcs, keys, changed = _sources(), [], 0
        for src, p, rel, ftype, fscope in srcs:
            k = _stat(p)
            keys.append((str(p), k))
            if k is None:
                continue
            hit = _files.get(str(p))
            if hit is None or hit[0] != k:
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    logger.info("doc_index: %s not read (%s)", p, exc)
                    continue
                _files[str(p)] = (k, _parse(text, src, rel, ftype, fscope))
                changed += 1
        key = tuple(keys)
        if key != _merged["key"]:
            rows, mentions, files = {}, {}, {}
            for src, p, rel, _, _ in srcs:
                ent = _files.get(str(p))
                if ent is None:
                    continue
                files[(src, rel)] = ent[1]
                for scope, io, pat, hit in ent[1]["rows"]:
                    rows.setdefault(scope, []).append((io, pat, hit))
                for k2, lst in ent[1]["mentions"].items():
                    mentions.setdefault(k2, []).extend(lst)
            live = {str(p) for _, p, *_ in srcs}
            for gone in [k2 for k2 in _files if k2 not in live]:
                _files.pop(gone, None)
            _merged.update(key=key, rows=rows, mentions=mentions, files=files)
        return {"files": len(_merged["files"]), "rows": sum(len(v) for v in _merged["rows"].values()),
                "mentions": sum(len(v) for v in _merged["mentions"].values()),
                "ms": round((time.perf_counter() - t0) * 1000, 2), "changed": changed}


def _query(type_, rel, io) -> tuple:
    """(scope, io, segments, block): ``block`` when the field is a block's, so the rows of any
    block (common.md, scope "*") count too."""
    t = _scope(type_)
    raw = str(rel or "").strip()
    if raw.lstrip("\\").lower().startswith("data\\"):
        sp = _split(raw, t if t and t not in NOT_BLOCKS else None)
        if not sp:
            return t, None, (), False
        scope, qio, tail = sp
        block = [x for x in raw.split("\\") if x][1:2] == ["Blocks"]
    else:
        tail = [s for s in raw.split("\\") if s]
        qio = None
        if tail and tail[0] in ("Input", "Output"):
            qio, tail = ("in" if tail[0] == "Input" else "out"), tail[1:]
        scope, block = t, t not in NOT_BLOCKS
    if io:
        s = str(io).lower()
        qio = "out" if s.startswith("out") else "in" if s.startswith("in") else qio
    return scope, qio, tuple(x.upper() for x in tail), block


def _fits(pat: tuple, segs: tuple) -> bool:
    return len(pat) == len(segs) and all(p == "*" or p == s for p, s in zip(pat, segs))


def lookup(type, rel, io=None, limit: int = LOOKUP_MAX) -> list:  # noqa: A002 -- the plan's name
    """The docs about a field: ``type`` a block type (RadFrac), a stream's (MATERIAL / STREAM) or
    an object's scope (DESIGN-SPEC, REACTIONS, ...); ``rel`` its path after Input / Output
    (``BASIS_RR``, ``FLOW\\MIXED\\WATER``), optionally led by ``Input\\`` / ``Output\\``, or a whole
    tree path; ``io`` "in" / "out" narrows to that side. Table rows first (a block type's own, then
    those of any block), then mentions of its code; this machine's files before the shipped ones;
    at most ``limit``. [] when nothing matches or on any failure."""
    try:
        build()
        scope, qio, segs, block = _query(type, rel, io)
        if not segs or not scope:
            return []
        scopes = [scope] + (["*"] if block and scope != "*" else [])
        rows, seen = [], set()
        for sc in scopes:
            for rio, pat, hit in _merged["rows"].get(sc, ()):
                if (qio is None or rio is None or rio == qio) and _fits(pat, segs):
                    rows.append(hit)
                    seen.add((hit["src"], hit["file"], hit["line"]))
        code = segs[0]
        ments = []
        for sc in scopes:
            for hit in _merged["mentions"].get((sc, code), ()):
                k = (hit["src"], hit["file"], hit["line"])
                if k not in seen:
                    seen.add(k)
                    ments.append(hit)
        out = sorted(rows, key=lambda h: h["src"] != "user") + sorted(ments, key=lambda h: h["src"] != "user")
        return [dict(h) for h in out[:max(0, int(limit))]]
    except Exception as exc:
        logger.warning("doc_index: lookup(%r, %r) failed: %r", type, rel, exc)
        return []


def rows_for(type, kind: str | None = None) -> list:  # noqa: A002 -- the plan's name
    """The rows of one object type as its own files group them: [{"scope", "src", "file", "head",
    "adv", "rows": [{"rel", "io", "vtype", "options"?, "row", "line"}]}] -- a block type's from its
    files (``radfrac.md`` the general one, ``radfrac-*.md`` advanced: ``adv``), a stream's (MATERIAL
    / STREAM) or another object's from the files whose Root is under it; only rows written under
    the object itself (``rel``), in file order. The general files first; ``kind`` "general" /
    "advanced" keeps one; ``type`` None: every object type's at once. ``options``: the codes the
    Type cell lists (`TOTAL`, `PARTIAL-V`). [] when nothing matches or on any failure."""
    try:
        build()
        scope = None if type is None else _scope(type)
        with _lock:
            files = list(_merged["files"].items())
        out = []
        for (src, rel), ent in files:
            own = ent.get("scopes", ())
            adv = "-" in rel.rsplit("/", 1)[-1]
            if (scope is not None and scope not in own) or (kind and adv != (kind == "advanced")):
                continue
            groups: dict = {}
            for sc, io, _pat, hit in ent["rows"]:
                if sc in own and (scope is None or sc == scope) and io and hit.get("rel"):
                    r = {k: hit[k] for k in ("rel", "io", "vtype", "row", "line") if k in hit}
                    codes = _OPT.findall(hit.get("vtype") or "")
                    if codes:
                        r["options"] = codes
                    groups.setdefault((sc, hit["heading"]), []).append(r)
            out += [{"scope": sc, "src": src, "file": rel, "head": h, "adv": adv, "rows": rs}
                    for (sc, h), rs in groups.items()]
        return sorted(out, key=lambda g: g["adv"])
    except Exception as exc:
        logger.warning("doc_index: rows_for(%r) failed: %r", type, exc)
        return []


def scope_of(path) -> str | None:
    r"""The docs scope of a model object's tree path (\Data\Setup -> SETUP, a reaction's ->
    REACTIONS, a design spec's -> DESIGN-SPEC); None for one no file could be about."""
    sp = _split(str(path or "").rstrip("\\") + "\\Input\\X", None)
    return sp[0] if sp and sp[0] != "*" else None


def options(type, rel) -> list:  # noqa: A002
    """The option codes the docs list for a field (lookup's first row whose Type cell has some);
    [] when none does."""
    for h in lookup(type, rel, "in", limit=LOOKUP_MAX):
        codes = _OPT.findall(h.get("vtype") or "") if h.get("kind") == "row" else []
        if codes:
            return codes
    return []


def section(hit, limit: int = SECTION_MAX) -> str:
    """The part of the file a hit (or {"src", "file", "line"}) is in: from the nearest heading
    above its line to the next heading of the same or a higher level, at most ``limit``
    characters (cut at a line where it can be). "" when the file is not indexed."""
    try:
        with _lock:
            ent = _merged["files"].get((hit.get("src"), hit.get("file")))
        if ent is None:
            build()
            with _lock:
                ent = _merged["files"].get((hit.get("src"), hit.get("file")))
        if ent is None:
            return ""
        line, lines, heads = int(hit.get("line") or 0), ent["lines"], ent["heads"]
        start, level = next(((i, lv) for i, lv in reversed(heads) if i <= line), (1, 0))
        end = next((i for i, lv in heads if i > start and (level == 0 or lv <= level)), len(lines) + 1)
        text = "\n".join(lines[start - 1:end - 1]).strip()
        if len(text) > limit:
            cut = text.rfind("\n", 0, limit)
            text = text[:cut if cut > limit // 2 else limit].rstrip() + "\n…"
        return text
    except Exception as exc:
        logger.warning("doc_index: section of %r failed: %r", hit, exc)
        return ""


_LINK = re.compile(r"^\[[^\]]*\]\(([A-Za-z0-9]+)\.md\)$")


def palette() -> list:
    """[(heading, [TYPE])]: the ``##`` sections of ``blocks/index.md`` (the Aspen model palette's
    tabs) in file order, each with the blocks its table lists, named by their general file
    (``[radfrac.md](radfrac.md)`` -> RADFRAC); a section that lists none left out, [] when the file
    cannot be read."""
    try:
        text = (Path(DOCS) / "blocks" / "index.md").read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        m = _HEAD.match(line)
        if m and len(m.group(1)) == 2:
            out.append((m.group(2), []))
        cells = _cells(line) if out and line.lstrip().startswith("|") else []
        link = _LINK.match(cells[1]) if len(cells) > 1 else None
        if link:
            out[-1][1].append(link.group(1).upper())
    return [(h, ts) for h, ts in out if ts]


def _reset() -> None:
    """Forget every parsed file (the next build is a cold one)."""
    with _lock:
        _files.clear()
        _merged.update(key=None, rows={}, mentions={}, files={})
