"""A help card for one field: what your Aspen says the field is,
what it holds now, what it can be set to, which completeness rules may be about it, and where
the docs talk about it. The workbench window's Api.fieldhelp answers with it.

    card(req)        the card, at most CARD_MAX bytes of JSON; {"error": why} on a bad request
    passage(ref)     the docs passage a card's docs entry points at (its ``ref``)
    options_of(scope, rel, now)     every option of a field, as the card lists them
    warm()           read what the first card reads (the window's warm-up thread)

AspenTech's text in a card -- the prompt, option names and descriptions, rule texts -- is read
at run time from the user's own Aspen: the inspector row or the window's field_info job
(attribute 19), learned.json and the local extraction (tools/aspen_strings.py). None of it is in
this file. Our own words -- names, zh-TW glosses and hints, basis names -- come from
tools/aspen_labels.py and BASES. No COM, no AI call: ``ask`` is what the page's Ask AI sends (a
field target). Tree paths in any text are written with ›, never a backslash.

req (all optional but ``path``, or a ``record`` / ``stmt`` that has one):
    path      the field's tree path (\\Data\\Blocks\\C1\\Input\\BASIS_RR)
    type      the block's type (RadFrac); or ``types`` {block name: type}
    row       the inspector's row of it: its prompt (attribute 19, raw; "" = Aspen has none),
              value, unit, units, basis, enterable
    info      the tab's ``field_info`` for it (the field_info event's answer), same keys, "live"
    prompt, now   a prompt and {value, unit, units, basis, enterable} from elsewhere
    record    a journal record (its target.path / block / type); stmt  a program statement
    lang      "zh" (default) | "en": the ``where`` line's words
    options   "all": only {"key", "options"} with every option (the card's filter box)
    ref       a docs entry's ref: only passage(ref)

Pure stdlib + tools.*; no I/O at import; nothing here raises.
"""
from __future__ import annotations

import json
import logging
import re
import time

from tools import aspen_labels, aspen_strings, doc_index, gui_rules

logger = logging.getLogger(__name__)

CARD_MAX = 4096          # bytes of the card's JSON (UTF-8)
PROMPT_MAX = 600         # characters of the prompt
RULE_MAX = 300           # ... of a rule
DOCS_MAX = 3             # docs entries (one per section)
OPTIONS_MAX = 12         # options listed; the rest counted in options_more
OPTION_DESC = 160        # characters of an option's description
UNITS_MAX = 24           # units listed; the rest counted in units_more
LABEL_MAX = 200          # the ask target's label

# Basis codes (attribute 13) and our words for them: what a field with a basis can be switched to.
BASES = {"MOLE": ("Mole", "莫耳"), "MASS": ("Mass", "質量"), "STDVOL": ("Std. liquid volume", "標準液體積"),
         "MOLE-FLOW": ("Mole flow", "莫耳流量"), "MASS-FLOW": ("Mass flow", "質量流量"),
         "STDVOL-FLOW": ("Std. liquid volume flow", "標準液體積流量"), "MOLE-FRAC": ("Mole fraction", "莫耳分率"),
         "MASS-FRAC": ("Mass fraction", "質量分率"), "STDVOL-FRAC": ("Std. liquid volume fraction", "標準液體積分率")}
_BASIS_FAMILIES = (("MOLE", "MASS", "STDVOL"),
                   ("MOLE-FLOW", "MASS-FLOW", "STDVOL-FLOW", "MOLE-FRAC", "MASS-FRAC", "STDVOL-FRAC"))

_LEAD = re.compile(r"^lets? you (?:(?:type|enter)(?: in)?(?: the)?\s+)?", re.I)
_ESC = re.compile(r"\\([|*_`#\[\]<>])")
_DATA = re.compile(r"\\?\bData\\")


def _unslash(text) -> str:
    """A text with its tree paths in words: `\\Data\\Blocks\\{name}\\Input\\X` -> Blocks › {name} ›
    Input › X; a Markdown escape (\\|) its character; no backslash is left."""
    s = _ESC.sub(r"\1", str(text or ""))
    return _DATA.sub("", s).replace("\\", " › ")


def _cut(text, n: int) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def show_prompt(text) -> str:
    """A prompt as the card shows it: whitespace folded, a leading "Lets you type (the)" dropped
    ("Lets you select X" -> "Select X"), the first letter upper case, at most PROMPT_MAX."""
    s = _LEAD.sub("", " ".join(str(text or "").split()))
    return _cut(_unslash(s[:1].upper() + s[1:]), PROMPT_MAX)


# ------------------------------------------------------------------------------ the field
def _where(path, type_=None) -> tuple:
    """(loc, w) of a tree path: aspen_labels' loc, and w {"obj", "kind" (block | stream | None),
    "scope" (the labels' scope: TYPE, "*", STREAM, a section's), "io", "code", "rel" (the
    segments after Input / Output), "type"}."""
    segs = [s for s in str(path or "").split("\\") if s]
    if segs and segs[0].lower() == "data":
        segs = segs[1:]
    io_i = next((i for i, s in enumerate(segs) if s in ("Input", "Output")), None)
    head, rel = (segs[:io_i], segs[io_i + 1:]) if io_i is not None else (segs, [])
    kind = {"Blocks": "block", "Streams": "stream"}.get(head[0] if head else None)
    t = str(type_ or "").strip() or None
    try:
        loc, scope = aspen_labels._resolve(path, t)     # noqa: SLF001 -- the scope learned.json keys by
    except Exception:  # noqa: BLE001
        loc = aspen_labels.loc(path, t)
        scope = (t or "*").upper() if kind == "block" else "STREAM" if kind == "stream" else (head[0] if head else "").upper()
    return loc, {"obj": head[1] if kind and len(head) > 1 else None, "kind": kind, "scope": scope,
                 "io": "out" if io_i is not None and segs[io_i] == "Output" else "in", "rel": rel,
                 "code": rel[0].upper() if rel else None, "type": t}


def _target(req: dict) -> tuple:
    """(path, block type) the request is about: path, else a record's target, else a statement's."""
    path, typ = req.get("path"), req.get("type")
    rec, st = req.get("record"), req.get("stmt")
    if not path and isinstance(rec, dict) and isinstance(rec.get("target"), dict):
        tg = rec["target"]
        path, typ = tg.get("path"), typ or tg.get("type")
        if not typ and tg.get("block") and isinstance(req.get("types"), dict):
            typ = req["types"].get(tg["block"])
    if not path and isinstance(st, dict):
        path = st.get("path")
    path = str(path or "").strip()
    segs = [s for s in path.split("\\") if s]
    if not typ and isinstance(req.get("types"), dict) and len(segs) > 2 and segs[1] == "Blocks":
        typ = req["types"].get(segs[2])
    return path, (str(typ) if typ else None)


def _learned(key: str):
    try:
        return aspen_labels._learned().get(key)       # noqa: SLF001 -- the labels' own cached read
    except Exception:  # noqa: BLE001
        return None


def _extracted() -> dict:
    try:
        return aspen_labels._labels() or {}           # noqa: SLF001 -- labels.json, cached by mtime
    except Exception:  # noqa: BLE001
        return {}


def _prompt(req: dict, w: dict) -> tuple:
    """(raw prompt, src): the inspector row's, the field_info answer's, one given, learned.json's,
    labels.json's variable description (a block's results only: Aspen gives them no prompt, and
    the description is keyed by the variable's name alone, so an input's could be another block
    type's -- RadFrac's stage TEMP for a Heater's), else ("", "none")."""
    for src, d in (("row", req.get("row")), ("live", req.get("info"))):
        if isinstance(d, dict) and isinstance(d.get("prompt"), str) and d["prompt"].strip():
            return d["prompt"], src
    if isinstance(req.get("prompt"), str) and req["prompt"].strip():
        return req["prompt"], str(req.get("prompt_src") or "row")[:8]
    if w["code"]:
        text = _learned(f"{w['scope']}|{w['io']}|{w['code']}")
        if isinstance(text, str) and text.strip():
            return text, "learned"
        if w["kind"] == "block" and w["io"] == "out":
            v = _extracted().get("vars") or {}
            text = v.get(w["code"]) or v.get(re.sub(r"[^A-Z0-9]", "_", w["code"]))
            if isinstance(text, str) and text.strip():
                return text, "vars"
    return "", "none"


def _now(req: dict) -> dict | None:
    """What the field holds now, from the field_info answer, the row, or ``now``."""
    for d in (req.get("info"), req.get("row"), req.get("now")):
        if isinstance(d, dict) and ("value" in d or "unit" in d or "found" in d):
            units = [str(u) for u in d.get("units") or [] if u][:200]
            out = {"value": d.get("value"), "unit": d.get("unit") or None, "units": units[:UNITS_MAX],
                   "basis": str(d["basis"]) if d.get("basis") else None,
                   "enterable": d.get("enterable") if isinstance(d.get("enterable"), bool) else None}
            if len(units) > UNITS_MAX:
                out["units_more"] = len(units) - UNITS_MAX
            if d.get("found") is False:
                out["found"] = False
            return out
    return None


def _basis(now: dict | None) -> dict | None:
    """{"now", "choices": [{"code", "name", "gl", "now"}]} of a field that has a basis."""
    b = (now or {}).get("basis")
    if not b:
        return None
    fam = next((f for f in _BASIS_FAMILIES if b.upper() in f), (b.upper(),))
    return {"now": b, "choices": [{"code": c, "name": BASES.get(c, (None, None))[0], "gl": BASES.get(c, (None, None))[1],
                                   "now": c == b.upper()} for c in fam]}


def options_of(scope, rel, now=None) -> list:
    """Every option of the field ``rel`` (its segments after Input, ``TEMP\\MIXED``) on ``scope``
    (a block type, STREAM, ...): the docs' in their order (doc_index.options; not while the field
    holds a number that is none of them: a basis, not an option), then the ones only this Aspen's
    extraction lists; each {"code", "name", "desc", "now"} (aspen_labels.option), the
    description cut to OPTION_DESC."""
    T = str(scope or "").upper()
    F = re.sub(r"[^A-Z0-9]", "_", str(rel or "").split("\\")[0].upper())
    codes = doc_index.options(T, f"Input\\{rel}")
    if isinstance(now, (int, float)) and not isinstance(now, bool) and str(now).removesuffix(".0") not in codes:
        codes = []
    ext = ((_extracted().get("options") or {}).get(T) or {}).get(F) or {}
    have = {c.upper() for c in codes}
    codes += [c for c in ext if c.upper() not in have]
    cur = str(now).removesuffix(".0").upper() if now not in (None, "") else None
    out = []
    for c in codes:
        o = aspen_labels.option(T, F, c)
        out.append({"code": c, "name": o.get("name"), "desc": _cut(o["desc"], OPTION_DESC) if o.get("desc") else None,
                    "now": cur is not None and c.upper() == cur})
    return out


def _shown_options(opts: list) -> tuple:
    """(the first OPTIONS_MAX, with the current one kept when it comes later; how many left out)."""
    if len(opts) <= OPTIONS_MAX:
        return opts, 0
    shown = opts[:OPTIONS_MAX]
    cur = next((o for o in opts[OPTIONS_MAX:] if o["now"]), None)
    if cur is not None:
        shown = shown[:-1] + [cur]
    return shown, len(opts) - len(shown)


def _docs(path, w: dict) -> list:
    """The docs entries: table rows first, this machine's files first (doc_index.lookup), one
    per section, at most DOCS_MAX; texts in words."""
    hits = doc_index.lookup(w["type"] or ("*" if w["kind"] == "block" else ""), path, w["io"], limit=12)
    out, seen = [], set()
    for x in hits:
        k = (x.get("src"), x.get("file"), x.get("heading"))
        if k in seen:
            continue
        seen.add(k)
        e = {"src": x.get("src"), "file": x.get("file"), "heading": _unslash(x.get("heading") or "") or None,
             "line": x.get("line"), "kind": x.get("kind"), "ref": f"{x.get('src')}|{x.get('file')}|{x.get('line')}"}
        if x.get("kind") == "row":
            e["row"] = _cut(_unslash(x.get("row")), 300)
        else:
            e["text"] = _cut(_unslash(x.get("text")), 300)
        out.append(e)
        if len(out) >= DOCS_MAX:
            break
    return out


def _rules(raw: str, w: dict, loc: dict) -> tuple:
    """(rules, note): gui_rules.rules_for_field on the raw prompt with the field's names -- only
    once a catalog is loaded (a window must not start the extraction; gui_rules.load() reads one
    that appeared since); note "rules_unavailable" when there is none."""
    if not raw or w["io"] != "in":
        return [], None
    if gui_rules._SOURCE is None and not gui_rules.load():      # noqa: SLF001 -- never extracts
        return [], "rules_unavailable"
    words = [x for x in (loc.get("field"), w["code"]) if x]
    got = gui_rules.rules_for_field(raw, words, limit=3)
    return [{"text": _cut(_unslash(r["text"]), RULE_MAX), "score": r["score"]} for r in got], None


def _size(card) -> int:
    return len(json.dumps(card, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _fit(card: dict) -> dict:
    """Shrink a card over CARD_MAX: option descriptions, then fewer options, rules, docs, units,
    then a shorter prompt."""
    steps = [lambda c: [o.update(desc=_cut(o["desc"], 80)) for o in c["options"] if o.get("desc")],
             lambda c: _drop(c, "options", 8), lambda c: c.update(rules=c["rules"][:2]),
             lambda c: _drop(c, "options", 5), lambda c: c.update(docs=c["docs"][:2]),
             lambda c: c.update(rules=c["rules"][:1]), lambda c: c.update(docs=c["docs"][:1]),
             lambda c: c["now"] and c["now"].update(units=c["now"]["units"][:8]),
             lambda c: c["prompt"].update(text=_cut(c["prompt"]["text"], 300)),
             lambda c: [o.update(desc=None) for o in c["options"]]]
    for step in steps:
        if _size(card) <= CARD_MAX:
            break
        step(card)
    return card


def _drop(card: dict, key: str, n: int) -> None:
    opts = card[key]
    if len(opts) > n:
        keep = opts[:n]
        cur = next((o for o in opts[n:] if o.get("now")), None)
        if cur is not None:
            keep = keep[:-1] + [cur]
        card["options_more"] += len(opts) - len(keep)
        card[key] = keep


def _strings_note() -> str | None:
    st = str(aspen_strings.status().get("state") or "none")
    return None if st == "ok" else "strings_failed" if st == "failed" else "strings_loading"


def card(req) -> dict:
    """The help card of the field ``req`` names (see the module's docstring):
    {"v": 1, "key": TYPE|io|REL -- the same for every object of that type, "path", "io",
     "result": an Output field (no options, no rules), "loc" (aspen_labels.loc), "where" / "short"
     (its breadcrumb in words, ``lang``), "prompt": {"text", "src": row | live | learned | vars |
     none}, "now": {value, unit, units, units_more?, basis, enterable, found?} | None, "basis":
     {"now", "choices"} | None, "options", "options_more", "rules": [{"text", "score"}], "docs":
     [{"src", "file", "heading", "line", "kind", "row" | "text", "ref"}], "need_prompt": an input
     no source had a prompt for -- post {type: "field_info", tab, path}, then ask again with the
     tab's field_info as ``info`` (results never: Aspen gives them no prompt),
     "ask": {"kind": "field", "path", "label", "obj", "name"}, "notes", "ms"}."""
    t0 = time.perf_counter()
    try:
        req = dict(req or {})
        if req.get("ref"):
            return passage(req["ref"])
        path, typ = _target(req)
        if not path.lower().startswith("\\data\\"):
            return {"error": "no field path"}
        loc, w = _where(path, typ)
        rel = "/".join(s.upper() for s in w["rel"])
        key = f"{w['scope']}|{w['io']}|{rel}"
        now = _now(req)
        if req.get("options") == "all":
            cur = (now or {}).get("value")
            return {"v": 1, "key": key, "options": options_of(w["scope"], "\\".join(w["rel"]), cur) if w["io"] == "in" else []}
        lang = "en" if req.get("lang") == "en" else "zh"
        raw, src = _prompt(req, w)
        notes = [n for n in (_strings_note(),) if n]
        info = req.get("info") if isinstance(req.get("info"), dict) else None
        if info and info.get("status") == "waiting":
            notes.append("aspen_busy")
        if now and now.get("found") is False:
            notes.append("not_found")
        result = w["io"] == "out"
        opts, more = ([], 0)
        rules, rn = [], None
        if not result and w["code"]:
            opts, more = _shown_options(options_of(w["scope"], "\\".join(w["rel"]), (now or {}).get("value")))
            rules, rn = _rules(raw, w, loc)
        if rn:
            notes.append(rn)
        read = src in ("row", "live") or (isinstance(req.get("row"), dict) and "prompt" in req["row"]) or info is not None
        if not raw and read:
            notes.append("no_prompt")
        label = aspen_labels.text(loc, "short", "en")
        c = {"v": 1, "key": key, "path": path, "io": w["io"], "result": result, "loc": loc,
             "where": aspen_labels.text(loc, "full", lang), "short": aspen_labels.text(loc, "short", lang),
             "prompt": {"text": show_prompt(raw) if raw else "", "src": src}, "now": now, "basis": _basis(now),
             "options": opts, "options_more": more, "rules": rules, "docs": _docs(path, w),
             "need_prompt": not result and src not in ("row", "live", "learned") and not read,
             "ask": {"kind": "field", "path": path, "label": _cut(label, LABEL_MAX),
                     "obj": w["kind"] if w["kind"] in ("block", "stream") else None, "name": w["obj"]},
             "notes": notes}
        c = _fit(c)
        c["ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return c
    except Exception as exc:  # noqa: BLE001 -- a card never takes the window down
        logger.warning("fieldhelp: card for %r failed", req, exc_info=True)
        return {"error": f"{type(exc).__name__}: {exc}"}


def passage(ref) -> dict:
    """{"src", "file", "heading", "section"}: the part of the docs file a card's docs entry
    (``ref`` "src|file|line") is in, at most doc_index.SECTION_MAX characters, paths in words."""
    try:
        src, file, line = str(ref).split("|", 2)
        hit = {"src": src, "file": file, "line": int(line)}
    except (TypeError, ValueError):
        return {"error": "bad ref"}
    text = doc_index.section(hit)
    if not text:
        return {"error": "not found", "src": src, "file": file}
    head = text.splitlines()[0].lstrip("#").strip() if text.startswith("#") else None
    return {"src": src, "file": file, "heading": _unslash(head) if head else None, "section": _unslash(text)}


def warm() -> dict:
    """What the first card reads, read now: the docs index, labels.json and learned.json, the
    rule catalog if it appeared since import. {"docs": build(), "ms"}."""
    t0 = time.perf_counter()
    out = {"docs": doc_index.build()}
    _extracted()
    _learned("")
    if gui_rules._SOURCE is None:                    # noqa: SLF001
        gui_rules.load()
    out["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out
