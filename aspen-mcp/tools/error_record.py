"""record_error: append a confirmed fix to this machine's error history.

The entry goes to ``<user data>/error-history.md`` in the format of the shipped
``docs/error-history.md`` (an ``## ERROR KEYWORD`` heading, then one ``### <block> — <cause>``
case with ``- **Key**: value`` lines), so tools/diagnose.py reads it back in later sessions.
Nothing leaves the machine.
"""

from __future__ import annotations

import logging
import os
import re
import threading

log = logging.getLogger("tools")

FIELD_MAX = 300          # characters kept of each field
FILE_NAME = "error-history.md"

_HEADER = (
    "# Error History (this machine)\n\n"
    "Errors met and fixed on this machine, recorded by record_error. Same format as the shipped\n"
    "docs/error-history.md: `## ` is the error keyword, `### ` one case. Treat entries as hints.\n"
)

# Windows paths (C:\..., \\server\share\...), home-relative (~/...) and absolute Unix paths
# under common roots. Aspen tree paths (Data.Blocks.{name}... or \Data\Blocks\...) are kept.
_PATHS = re.compile(
    r"(?:[A-Za-z]:[\\/][^\s`'\"<>|]*"
    r"|\\\\[^\s`'\"<>|]+"
    r"|~[\\/][^\s`'\"<>|]*"
    r"|/(?:home|Users|usr|var|tmp|opt|mnt|etc|root|srv|private)/[^\s`'\"<>|]*)"
)
_H2 = re.compile(r"^##\s+(.+?)\s*#*\s*$")
_lock = threading.Lock()


def _clean(text, limit: int = FIELD_MAX) -> str:
    """One line of ``text``: file paths replaced by <path>, whitespace collapsed, capped."""
    s = _PATHS.sub("<path>", str(text or ""))
    s = " ".join(s.split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def _insert(text: str, keyword: str, entry: str) -> str:
    """``text`` with ``entry`` added at the end of the ``## keyword`` section, or under a new
    heading at the end of the file when there is none."""
    lines = text.splitlines()
    start = None
    for i, raw in enumerate(lines):
        m = _H2.match(raw)
        if m and " ".join(m.group(1).split()).upper() == keyword:
            start = i
            break
    if start is None:
        body = text.rstrip("\n")
        return f"{body}\n\n## {keyword}\n\n{entry}"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("#") and not lines[j].startswith("###"):
            end = j
            break
    head = "\n".join(lines[:end]).rstrip("\n")
    tail = "\n".join(lines[end:])
    return f"{head}\n\n{entry}" + (f"\n{tail}\n" if tail else "")


def record_error(
    error_keyword: str,
    block_type: str,
    property_method: str,
    cause: str,
    fix_direction: str,
    fix_path: str,
    tried_failed: str = "",
    *,
    root: str,
) -> str:
    """Append one entry to ``<root>/error-history.md``; the result names the file written."""
    keyword = _clean(error_keyword).upper().strip("# ")
    block = _clean(block_type)
    cause_s = _clean(cause)
    fix = _clean(fix_direction)
    path = _clean(fix_path)
    method = _clean(property_method)
    tried = _clean(tried_failed)
    if not keyword:
        return "Not recorded: error_keyword is empty."
    if not (cause_s or fix):
        return "Not recorded: give at least a cause or a fix."

    fix_line = fix + (f" (path `{path}`)" if path else "")
    lines = [f"### {block or 'Unknown block'} — {cause_s or 'cause not given'}", ""]
    lines.append(f"- **Block type**: {block or 'not given'}")
    if method:
        lines.append(f"- **Property method**: {method}")
    lines.append(f"- **Cause**: {cause_s or 'not given'}")
    lines.append(f"- **Fix**: {fix_line or 'not given'}")
    if tried:
        lines.append(f"- **Tried, did not work**: {tried}")
    entry = "\n".join(lines) + "\n"

    target = os.path.join(root, FILE_NAME)
    with _lock:
        try:
            os.makedirs(root, exist_ok=True)
            try:
                with open(target, encoding="utf-8") as f:
                    text = f.read()
            except FileNotFoundError:
                text = _HEADER
            new = _insert(text, keyword, entry)
            tmp = target + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(new)
            os.replace(tmp, target)
        except OSError as exc:
            log.error("record_error: %s not written (%s)", target, exc)
            return f"Not recorded: {target} could not be written ({exc})."
    return f"Recorded under ## {keyword} in {target}."
