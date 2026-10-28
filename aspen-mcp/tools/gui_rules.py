"""GUI completeness-rule catalog lookup.

The Aspen Plus GUI decides "what is missing" by evaluating hand-written rules
whose message texts live in AspenTech.AspenPlus.Localization.dll, keyed
FILEPNUM_<table>_Prompt_<id> (one table per block/form family).  Those
~50,000 texts belong to AspenTech, so the repo does not ship them:
tools/aspen_strings.py extracts them from the user's own Aspen
into ~/.aspen-mcp/aspen-strings/<version>/prompts.tsv.gz, and this module
reads that file (catalog_file()).  See docs/mcp/check-inputs.md.

check_inputs uses this module to attach candidate rule texts to each
incomplete object: detect which table the object belongs to (its field
prompts are exact catalog texts), then rank that table's rule-type messages
by overlap with the object's set values and unset-field prompts.  The final
"which rule is violated" call is made by the LLM reading the candidates.

The catalog is parsed at import when it is on disk (~0.3 s).  Until it is
(a first run: the extraction takes a few seconds in the background), every
lookup finds no rules and state() says why; the first lookup starts the
extraction, and a later one loads the file once it is there -- no restart.
"""

import gzip
import logging
import os
import re
import threading
from collections import Counter, defaultdict

from tools import aspen_strings

logger = logging.getLogger(__name__)

_DATA_FILE = None          # a catalog file to read instead of looking (a module attribute so it can be overridden); see catalog_file()
_ENV = "ASPEN_GUI_PROMPTS"   # the same, from the environment

_RULE_PAT = re.compile(
    r"must be|must match|must have|must not|cannot|can not|not allowed"
    r"|only if|is required|are required|required when|required if"
    r"|at least one|do not specify|may not", re.IGNORECASE)

_STOPWORDS = frozenset(
    "the for with when must greater less than sheet option value number this "
    "that are is not and or of in on to a an be if only allowed required "
    "specify specified setup specifications".split())

_WORD = re.compile(r"[a-z0-9]+")
_PAREN = re.compile(r"\([^()]*\)")

_LOCK = threading.RLock()
_TEXT2FP: dict = {}        # normalized text -> {filepnum}
_RULES_BY_FP: dict = {}    # filepnum -> [(pid, text)]
_SOURCE = None             # the file loaded; None while there is no catalog


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().rstrip(". ").casefold()


def _explicit():
    return _DATA_FILE or os.environ.get(_ENV) or None


def catalog_file():
    """Where the catalog is read from: _DATA_FILE, else env ASPEN_GUI_PROMPTS, else the
    local extraction's prompts.tsv.gz (aspen_strings.prompts_file()); None when neither."""
    explicit = _explicit()
    if explicit:
        return str(explicit)
    f = aspen_strings.prompts_file()
    return str(f) if f else None


def _parse(path):
    """(prompt-text index, per-table rule lists) of one <filepnum>TAB<pid>TAB<text> file."""
    text2fp = defaultdict(set)
    rules_by_fp = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3 or not (parts[0].isdigit() and parts[1].isdigit()):
                continue
            fp, pid, text = int(parts[0]), int(parts[1]), parts[2]
            text2fp[_norm(text)].add(fp)
            if _RULE_PAT.search(text):
                rules_by_fp[fp].append((pid, text))
    return dict(text2fp), dict(rules_by_fp)


def load(path=None) -> bool:
    """(Re)read the catalog from ``path``, else catalog_file().  Nothing readable leaves the
    tables empty.  Returns whether a catalog is loaded.  Never starts the extraction:
    importing this module (``aspen-mcp --check`` does) must not leave one half done."""
    global _TEXT2FP, _RULES_BY_FP, _SOURCE
    with _LOCK:
        f = path or catalog_file()
        text2fp, rules, src = {}, {}, None
        if f:
            try:
                text2fp, rules = _parse(f)
                src = str(f)
            except (OSError, EOFError, UnicodeDecodeError) as exc:
                logger.warning("GUI rule catalog unreadable at %s: %s", f, exc)
        else:
            logger.info("GUI rule catalog not extracted yet (%s)", aspen_strings.status().get("state"))
        _TEXT2FP, _RULES_BY_FP, _SOURCE = text2fp, rules, src
        return src is not None


def _current() -> bool:
    """Whether a catalog is loaded -- else look again (the extraction may have finished since)
    and, still none and no explicit file, start the extraction (aspen_strings.ensure())."""
    if _SOURCE is not None:
        return True
    with _LOCK:
        if _SOURCE is not None or load():
            return True
    if not _explicit():
        aspen_strings.ensure()
    return False


def state() -> str:
    """The catalog's state: "ok" -- loaded; "loading" -- the extraction is running or about
    to (a lookup started it); "unavailable" -- it failed, or an explicit file is unreadable."""
    if _current():
        return "ok"
    if _explicit():
        return "unavailable"
    return "loading" if aspen_strings.status().get("state") in ("none", "running") else "unavailable"


load()


def _detect(field_prompts) -> list[int]:
    votes = Counter()
    for p in field_prompts:
        fps = _TEXT2FP.get(_norm(p))
        if fps and len(fps) <= 4:      # ignore boilerplate shared texts
            votes.update(fps)
    if not votes:
        return []
    top = votes.most_common()
    best = top[0][1]
    return [fp for fp, n in top if n == best]


def detect_table(field_prompts) -> list[int]:
    """Vote the object's form table(s) from its field prompt texts.

    Prompts are shown by the GUI from the same catalog, so exact matches
    identify the FILEPNUM.  Returns tables sorted by vote count (ties kept).
    """
    _current()
    return _detect(field_prompts)


def rules_for_field(prompt: str, words=(), limit: int = 3) -> list[dict]:
    """The rules most likely about one field: [{"text", "score"}], at most ``limit``.

    The field's own prompt (attribute 19) names its form table; that table's rule texts are
    scored 4 per name of the field in ``words`` they contain (e.g. "Reflux ratio", "NSTAGE")
    plus 1 per content word of the prompt's subject -- its first sentence without the
    "(Main Column)" qualifiers.  A prompt no table claims gives [] -- never the whole catalog."""
    _current()
    tables = _detect([prompt]) if prompt else []
    if not tables:
        return []
    subject = re.split(r"\.\s", _PAREN.sub(" ", prompt) + " ", maxsplit=1)[0]
    content = {w for w in _WORD.findall(_norm(subject)) if len(w) >= 4 and w not in _STOPWORDS}
    names = [n for n in (_norm(w) for w in words if w) if len(n) >= 3]
    scored, seen = [], set()
    for fp in tables:
        for pid, text in _RULES_BY_FP.get(fp, []):
            text = text.strip()
            t = text.casefold()
            score = 4 * sum(1 for n in names if n in t) + len(content & set(_WORD.findall(t)))
            if score > 0 and text not in seen:
                seen.add(text)
                scored.append((score, fp, pid, text))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    return [{"text": t, "score": s} for s, _, _, t in scored[:limit]]


_REQ_SUBJECT_PAT = re.compile(
    r"^([A-Za-z][A-Za-z0-9 /+-]{2,50}?)\s+(?:must be specified|is required)")
_CONDITIONAL_PAT = re.compile(r"\bwhen\b|\bif\b|\bunless\b", re.IGNORECASE)
# single-word subjects too generic to name a field reliably -- many subforms
# have a TYPE/STAGE/... and the rule only applies inside that subform
_GENERIC_SUBJECTS = frozenset(
    "TYPE STAGE PHASE VALUE OPTION BASIS ID NAME NUMBER UNIT MODEL METHOD"
    " LOCATION SPEC COMPONENT STREAM PROPERTY".split())


def diagnose(field_prompts, set_values, unset_fields, probe=None,
             limit: int = 8):
    """Diagnose one incomplete object against the catalog.

    unset_fields -- [(label, prompt)] for the object's empty and zero fields.
    probe        -- callable(NAME) -> 'empty' | 'set' | None, checking the
                    object's Input node NAME directly over COM.
    Returns (violated, candidates):
      violated -- [(field, rule_text)] *unconditional* "X must be specified"
        rules whose field exists on the object and is empty -- asserted
        directly, no condition to check
      candidates -- scored rule texts; the reader checks each condition
        against the object's reported values
    """
    tables = detect_table(field_prompts)      # loads a catalog extracted since, if any
    scope = []
    for fp in tables:
        scope.extend(_RULES_BY_FP.get(fp, []))
    if not scope:      # unknown table: search the whole catalog
        for lst in _RULES_BY_FP.values():
            scope.extend(lst)

    # --- unconditional required-rules: guess the COM node from the subject
    # ("Condenser must be specified." -> Input\CONDENSER) and probe it
    likely = []
    if probe is not None:
        seen = set()
        for pid, text in scope:
            if len(likely) >= 6:
                break
            if _CONDITIONAL_PAT.search(text):
                continue
            m = _REQ_SUBJECT_PAT.match(text.strip())
            if not m:
                continue
            guess = "".join(m.group(1).split()).upper()
            if not guess or guess in seen or guess in _GENERIC_SUBJECTS:
                continue
            seen.add(guess)
            if probe(guess) == "empty":
                likely.append((guess, text.strip()))

    # --- keyword-overlap ranking of the remaining rules
    values = {v.casefold() for v in set_values if len(v) >= 3 and v.isalpha()}
    phrases = [_norm(p) for _, p in unset_fields if p]
    words = {w for p in phrases for w in p.split()
             if len(w) >= 4 and w not in _STOPWORDS}
    promoted = {text for _, text in likely}

    scored = []
    for pid, text in scope:
        if text.strip() in promoted:
            continue
        t = text.casefold()
        score = 0
        score += 3 * sum(1 for v in values if v in t)
        score += 4 * sum(1 for p in phrases if p and p in t)
        score += sum(1 for w in words if w in t)
        if score > 0:
            scored.append((score, pid, text.strip()))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return likely, [f"[{s}] {t}" for s, _, t in scored[:limit]]
