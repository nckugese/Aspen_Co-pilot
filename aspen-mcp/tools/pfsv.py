"""Aspen's own flowsheet drawing, read for the workbench's "Aspen layout".

A .bkp file keeps the drawing in its ``PFSVData`` section: a BLOCK record per icon (its
position, y up, in Aspen's units) and a STREAM record per stream (its label position and the
points of its route). The workbench reads the live model's drawing without Save or Save As:
``export_text`` has Aspen export a backup copy of the model as it is in memory, and
``parse_pfsvdata`` reads that text. Nothing here touches the model or its file: ``place``
edits the .bkp bytes it is given (layout_flowsheet's arrangement, tools/flowsheet_tools.py).

  parse_pfsvdata(text) -> {"found": bool, "blocks": {id: {"x", "y", "scale"}},
                           "streams": {id: {"at": [x, y], "pts": [[x, y], ...]}}}
  aspen_layout(parsed, flowsheet, req, model) -> what a session keeps as "aspen_layout"
  model_id(path) -> "m" + 10 hex digits naming the model file, or None
  export_text(app, folder) -> the live model as .bkp text
  to_aspen(nodes, old) -> the window's block centres (px) in Aspen's units, its scale and place
  place(data, blocks, ends) -> the .bkp bytes with its blocks there and their streams moved along

The parser is pure (no COM): only ``export_text`` touches Aspen, through the app it is given.
The format, as far as it matters here::

    PFSVData                          (or "PFSVData {GUID}" in older files)
    BLOCK
    ID: MIXER1
    At 2.493118 -1.511337             icon position
    Scale 8.500000 Modifier 0         icon scale (first number)
    STREAM
    ID: MIX1
    At 3.459050 -1.489405             label position, or the free end of a feed or product
    ROUTE 0 0                         side 0 (label back to the source port), view 0
    r r 3.459050 -1.489405 0          a point: code, code, x, y, flag
    $ D ...                           a "$" line ends the point list
    ROUTE 1 0                         side 1 (label on to the destination port), view 0
    LEGEND                            end of the top level (or #HIERPFSVDATA, or a "$_" line)

Only the top level is read: hierarchy drawings follow it and are left out, so a hierarchy
block is one block, as the workbench draws it.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time

_NUM = r"-?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?"
_PT = re.compile(rf"^[a-z]\s+\S\s+({_NUM})\s+({_NUM})\s+\d+\s*$")
_PREFIX = "aspen_wb_layout_"
_LEFTOVER_S = 3600          # an export file older than this was left by a crash


def _top_section(text: str) -> list[str] | None:
    """The top-level PFSVData lines, up to LEGEND, the hierarchy drawings or the next "$_"
    block; None when the text has no drawing. The header is the first line whose first word
    is PFSVData."""
    lines = text.splitlines()
    g0 = next((i for i, line in enumerate(lines) if line.split()[:1] == ["PFSVData"]), None)
    if g0 is None:
        return None
    g1 = next((i for i in range(g0 + 1, len(lines)) if lines[i].startswith("$_")), len(lines))
    sec = lines[g0 + 1:g1]
    end = next((i for i, line in enumerate(sec) if line.strip() in ("LEGEND", "#HIERPFSVDATA")), len(sec))
    return sec[:end]


def _f(s: str, default: float = 0.0) -> float:
    try:
        v = float(s)
    except ValueError:
        return default
    return v if v == v and abs(v) < 1e9 else default


def parse_pfsvdata(text: str) -> dict:
    """Every top-level BLOCK and STREAM record of the drawing. A stream's ``pts`` run from
    its source end to its destination end (``[]`` without a route). A line that does not
    parse is skipped, never the whole drawing."""
    top = _top_section(text)
    out = {"found": top is not None, "blocks": {}, "streams": {}}
    if top is None:
        return out
    recs, cur = [], None
    for raw in top:
        line = raw.strip()
        if line in ("BLOCK", "STREAM"):
            cur = [line]
            recs.append(cur)
        elif cur is not None:
            cur.append(line)
    for rec in recs:
        kind, body = rec[0], rec[1:]
        rid = next((line[3:].strip() for line in body if line.startswith("ID:")), "")
        if not rid:
            continue
        if kind == "BLOCK":
            at = next((line.split() for line in body if line.startswith("At ")), None)
            if not at or len(at) < 3:
                continue
            sc = next((line.split() for line in body if line.startswith("Scale ")), None)
            scale = _f(sc[1], 1.0) if sc and len(sc) > 1 else 1.0
            out["blocks"][rid] = {"x": round(_f(at[1]), 4), "y": round(_f(at[2]), 4),
                                  "scale": round(scale if scale > 0 else 1.0, 3)}
            continue
        at, r0, r1, pts = None, None, None, None
        for line in body:
            if at is None and line.startswith("At "):
                p = line.split()
                if len(p) >= 3:
                    at = [round(_f(p[1]), 4), round(_f(p[2]), 4)]
            elif line.startswith("ROUTE "):
                p = line.split()
                side, view = (p[1] if len(p) > 1 else ""), (p[2] if len(p) > 2 else "0")
                pts = [] if view == "0" and side in ("0", "1") else None     # other views: ignored
                if pts is not None and side == "0" and r0 is None:
                    r0 = pts
                elif pts is not None and side == "1" and r1 is None:
                    r1 = pts
                else:
                    pts = None
            elif line.startswith("$"):
                pts = None
            elif pts is not None:
                m = _PT.match(line)
                if m:
                    pts.append([round(_f(m.group(1)), 4), round(_f(m.group(2)), 4)])
        if at is None:
            continue
        r0, r1 = r0 or [], r1 or []
        # both halves start at the label: source end -> ... -> label -> ... -> destination end
        out["streams"][rid] = {"at": at, "pts": r0[::-1] + r1[1:] if r0 and r1 else (r0[::-1] or r1)}
    return out


def aspen_layout(parsed: dict, flowsheet: dict | None, req: str | None = None,
                 model: str | None = None) -> dict:
    """What an import keeps: the model's own blocks and streams only (a record whose name
    matches, exactly or else ignoring case), and only blocks with a place of their own. A
    block at exactly (0, 0), or at exactly another block's position, was put there by Aspen
    (blocks added over COM while its window shows are stacked so) and counts as missing.

    ``status``: "no_graphics" when there is no drawing or none of the model's blocks is in
    it; "stacked" when they are, but none has a place of its own; "ok" otherwise."""
    base = {"v": 1, "req": req, "at": time.time(), "model": model}
    fs = flowsheet or {}
    bnames = [b["name"] for b in fs.get("blocks") or []]
    snames = [s["name"] for s in fs.get("streams") or []]
    if not parsed.get("found"):
        return dict(base, status="no_graphics", blocks={}, streams={}, missing=bnames)
    upper_b = {k.upper(): k for k in parsed["blocks"]}
    upper_s = {k.upper(): k for k in parsed["streams"]}
    got = {}
    for n in bnames:
        k = n if n in parsed["blocks"] else upper_b.get(n.upper())
        if k is not None:
            got[n] = dict(parsed["blocks"][k])
    at: dict = {}
    for n, b in got.items():
        at.setdefault((b["x"], b["y"]), []).append(n)
    blocks = {n: b for n, b in got.items()
              if not (b["x"] == 0 and b["y"] == 0) and len(at[(b["x"], b["y"])]) == 1}
    streams = {}
    for n in snames:
        k = n if n in parsed["streams"] else upper_s.get(n.upper())
        if k is not None:
            streams[n] = parsed["streams"][k]
    status = "ok" if blocks else "stacked" if got else "no_graphics"
    return dict(base, status=status, blocks=blocks, streams=streams,
                missing=[n for n in bnames if n not in blocks])


def model_id(path: str | None) -> str | None:
    """A model's identity from the file it lives in (Aspen's FullName is the program's path,
    not the model's, so the caller passes the file). The workbench takes the manager's own
    model id, which a Save As keeps; this is its fallback, the same formula as
    ``model_registry.legacy_id``, so ids stored for a file that never moved still match."""
    if not path:
        return None
    key = os.path.normcase(os.path.abspath(path)).encode("utf-8")
    return "m" + hashlib.sha1(key).hexdigest()[:10]


def export_text(app, folder) -> str:
    """The live model as .bkp text, drawing included, without Save or Save As: Aspen
    exports a backup copy (Export 1, HAPEXP_BACKUP) into a file of our own in ``folder``,
    which is read and deleted. Dialogs are suppressed around the call and the setting put
    back. Export files an earlier crash left behind (over an hour old) are removed first.

    Aspen counts the model as changed afterwards (closing its window by hand asks to save),
    though the export changed nothing in it; no COM call avoids that."""
    folder = os.fspath(folder)
    os.makedirs(folder, exist_ok=True)
    now = time.time()
    for name in os.listdir(folder):
        if name.startswith(_PREFIX):
            p = os.path.join(folder, name)
            try:
                if now - os.path.getmtime(p) > _LEFTOVER_S:
                    os.remove(p)
            except OSError:
                pass
    fd, path = tempfile.mkstemp(prefix=_PREFIX, suffix=".bkp", dir=folder)
    os.close(fd)
    os.remove(path)                          # Export writes a new file
    try:
        try:
            old = app.SuppressDialogs
        except Exception:
            old = 0
        app.SuppressDialogs = 1
        try:
            app.Export(1, path)
        finally:
            try:
                app.SuppressDialogs = old
            except Exception:
                pass
        if not os.path.exists(path):
            raise RuntimeError("Aspen wrote no file")
        with open(path, encoding="latin-1") as f:
            return f.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------- writing positions
# The one writer here (layout_flowsheet with an arrangement, tools/flowsheet_tools.py, which
# hands it the .bkp bytes): the drawing as Aspen wrote it, only coordinates changed. Each block
# moved gets its "At"; each stream touching a moved block keeps its route's shape, each half
# moved with the block at its end (side 0 with its source, side 1 with its destination; a feed
# or a product's one half, its free end included, with its one block), and where the two halves
# no longer meet at the label, one bend is put in so the route stays orthogonal. No record is
# added or removed and no other line changes, so what Aspen reads is what it wrote.

_SCALE_PX = 70.0         # window px per Aspen unit when the drawing gives no scale (flowsheet.js S_ONE)
_ROUTE_PT = re.compile(rf"^(\s*)([a-z])\s+(\S)\s+({_NUM})\s+({_NUM})\s+(\S+)\s*$")


def _eol(raw: bytes) -> bytes:
    return raw[len(raw.rstrip(b"\r\n")):]


def _records(lines: list[bytes]) -> list[dict] | None:
    """The top-level records with line numbers: [{"kind", "id", "at": line of the first At,
    "sides": {0: [point line numbers], 1: [...]}}] (view 0 only); None without a drawing."""
    txt = [ln.decode("latin-1") for ln in lines]
    g0 = next((i for i, ln in enumerate(txt) if ln.split()[:1] == ["PFSVData"]), None)
    if g0 is None:
        return None
    recs, cur, side = [], None, None
    for i in range(g0 + 1, len(txt)):
        s = txt[i].strip()
        if txt[i].startswith("$_") or s in ("LEGEND", "#HIERPFSVDATA"):
            break
        if s in ("BLOCK", "STREAM"):
            cur, side = {"kind": s, "id": "", "at": None, "sides": {0: [], 1: []}}, None
            recs.append(cur)
        elif cur is None:
            continue
        elif s.startswith("ID:") and not cur["id"]:
            cur["id"] = s[3:].strip()
        elif s.startswith("At ") and cur["at"] is None:
            cur["at"] = i
        elif s.startswith("ROUTE "):
            p = s.split()
            ok = len(p) > 2 and p[2] == "0" and p[1] in ("0", "1") and not cur["sides"][int(p[1])]
            side = int(p[1]) if ok else None
        elif s.startswith("$"):
            side = None
        elif side is not None and _ROUTE_PT.match(txt[i].rstrip("\r\n")):
            cur["sides"][side].append(i)
    return recs


def _pt(line: bytes):
    """A line's (lead, code, code, x, y, flag) for a route point, or (None, "At", "", x, y, "")."""
    raw = line.decode("latin-1").rstrip("\r\n")
    m = _ROUTE_PT.match(raw)
    if m:
        return m.group(1), m.group(2), m.group(3), _f(m.group(4)), _f(m.group(5)), m.group(6)
    p = raw.split()
    return raw[:len(raw) - len(raw.lstrip())], "At", "", _f(p[1]), _f(p[2]), ""


def _line(old: bytes, x: float, y: float, c1: str | None = None, c2: str | None = None) -> bytes:
    lead, a, b, _, _, flag = _pt(old)
    if a == "At":
        return f"{lead}At {x:.6f} {y:.6f}".encode("latin-1") + _eol(old)
    return f"{lead}{c1 or a} {c2 or b} {x:.6f} {y:.6f} {flag}".encode("latin-1") + _eol(old)


def to_aspen(nodes: dict, old: dict) -> dict:
    """The window's block centres (``nodes`` {name: [x, y]}, px, y down) in Aspen's units (y up):
    scaled so its blocks lie as far apart as they do in Aspen's drawing now (``old``: parse_pfsvdata
    blocks; the median nearest-neighbour distance, both sides, over the blocks in both that Aspen
    has placed), else _SCALE_PX px to a unit, and centred where those blocks are now (else at 0, 0)."""
    names = [n for n in nodes if n in old]
    spot = [(old[n]["x"], old[n]["y"]) for n in names]
    placed = [n for n, p in zip(names, spot) if p != (0, 0) and spot.count(p) == 1]

    def nn(pts):
        out = sorted(min(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** .5 for j, q in enumerate(pts) if j != i)
                     for i, p in enumerate(pts))
        out = [d for d in out if d > 0]
        return out[len(out) // 2] if out else None
    k = 1.0 / _SCALE_PX
    if len(placed) >= 2:
        a, w = nn([(old[n]["x"], old[n]["y"]) for n in placed]), nn([tuple(nodes[n]) for n in placed])
        if a and w:
            k = a / w
    cx = sum(old[n]["x"] for n in placed) / len(placed) if placed else 0.0
    cy = sum(old[n]["y"] for n in placed) / len(placed) if placed else 0.0
    base = placed or list(nodes)
    wx = sum(nodes[n][0] for n in base) / len(base) if base else 0.0
    wy = sum(nodes[n][1] for n in base) / len(base) if base else 0.0
    return {n: [round(cx + k * (p[0] - wx), 6), round(cy - k * (p[1] - wy), 6)] for n, p in nodes.items()}


def place(data: bytes, blocks: dict, ends: dict) -> tuple[bytes, dict] | None:
    """The .bkp ``data`` with its drawing's blocks at ``blocks`` ({name: [x, y]}, Aspen's units)
    and the routes of the streams on them moved along (``ends`` {stream: [source block | None,
    destination block | None]}, the model's topology). Names match exactly, else ignoring case.
    Returns (the new bytes, {"moved": [blocks], "streams": [streams], "missing": [blocks named but
    not in the drawing]}), or None when the file has no drawing."""
    lines = data.splitlines(keepends=True)
    recs = _records(lines)
    if recs is None:
        return None
    brec = {r["id"]: r for r in recs if r["kind"] == "BLOCK" and r["id"] and r["at"] is not None}
    upper = {k.upper(): k for k in brec}
    delta, moved, missing = {}, [], []
    for name, p in blocks.items():
        k = name if name in brec else upper.get(str(name).upper())
        if k is None:
            missing.append(name)
            continue
        _, _, _, x0, y0, _ = _pt(lines[brec[k]["at"]])
        delta[k.upper()] = (p[0] - x0, p[1] - y0)
        lines[brec[k]["at"]] = _line(lines[brec[k]["at"]], p[0], p[1])
        moved.append(k)
    uends = {str(s).upper(): [str(b).upper() if b else None for b in list(e or [])[:2] + [None, None]][:2]
             for s, e in (ends or {}).items()}
    touched, bends = [], {}                              # bends: {line number: line put in before it}
    for r in recs:
        if r["kind"] != "STREAM" or not r["id"] or r["at"] is None:
            continue
        src, dst = uends.get(r["id"].upper()) or [None, None]
        d0 = delta.get(src) if src else delta.get(dst)   # (a feed's free half moves with its one block)
        d1 = delta.get(dst) if dst else delta.get(src)
        if d0 is None and d1 is None:
            continue
        d0, d1 = d0 or (0.0, 0.0), d1 or (0.0, 0.0)
        s0, s1 = r["sides"][0], r["sides"][1]
        was1 = _pt(lines[s1[1]]) if len(s1) >= 2 else None
        for idx, d in ((s0, d0), (s1, d1)):
            for i in idx:
                _, _, _, x, y, _ = _pt(lines[i])
                lines[i] = _line(lines[i], x + d[0], y + d[1])
        lab = d0 if s0 or not s1 else d1
        _, _, _, x, y, _ = _pt(lines[r["at"]])
        lines[r["at"]] = _line(lines[r["at"]], x + lab[0], y + lab[1])
        if s0 and was1 is not None and d0 != d1:
            # the halves part at the label: side 1 starts there again and reaches its next point by
            # one bend, its last move along the axis it had (a port is met from the side it was)
            _, _, _, lx, ly, _ = _pt(lines[s0[0]])
            _, c1, c2, qx, qy, _ = _pt(lines[s1[1]])
            lines[s1[0]] = _line(lines[s1[0]], lx, ly)
            ox, oy = lx - d0[0], ly - d0[1]                  # (the label and that point as they were)
            horiz = c1 == "x" or (c1 == "t" and c2 in ("l", "r")) or (
                c1 not in ("y", "t") and abs(was1[4] - oy) <= abs(was1[3] - ox))
            cx, cy = (lx, qy) if horiz else (qx, ly)
            if abs(cx - lx) > 1e-9 or abs(cy - ly) > 1e-9:
                bends[s1[1]] = _line(lines[s1[1]], cx, cy, "y" if horiz else "x", "0")
        touched.append(r["id"])
    if bends:
        lines = [b for i, ln in enumerate(lines) for b in ((bends[i], ln) if i in bends else (ln,))]
    return b"".join(lines), {"moved": moved, "streams": touched, "missing": missing}
